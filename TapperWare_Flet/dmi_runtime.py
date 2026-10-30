"""XML validation and sequential DMI execution, independent from the UI.

The real adapter preserves the project's Action/ComProtocol API. Every call to
that API runs on one dedicated worker; UI updates stay on the asyncio loop.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import math
from threading import RLock
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import xml.etree.ElementTree as ET

MODELS = ("SENSE TOUCHSCREEN", "SENSE SOFTKEY", "TWINS", "STEN")
T9 = {
    "1": "1.-+", "2": "2ABC", "3": "3DEF", "4": "4GHI",
    "5": "5JKL", "6": "6MNO", "7": "7PQRS", "8": "8TUV",
    "9": "9WXYZ", "0": "0 ",
}
MAX_XML_BYTES = 2 * 1024 * 1024


class ValidationError(ValueError):
    pass


class HardwareError(RuntimeError):
    pass


class Stopped(Exception):
    pass


@dataclass(frozen=True)
class Operation:
    name: str
    args: tuple = ()


@dataclass(frozen=True)
class Command:
    number: int
    action: str
    target: str
    detail: str
    operations: tuple[Operation, ...]


@dataclass(frozen=True)
class Script:
    name: str
    model: str
    commands: tuple[Command, ...]
    source: bytes
    y_offset_mm: int = 0


def load_database(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValidationError(f"Impossibile leggere {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValidationError("DmiPositions.json deve contenere un oggetto JSON.")
    return data


def model_data(database: dict, model: str) -> dict:
    data = database.get("DMI_" + model.replace(" ", "_"))
    if not isinstance(data, dict) or not data.get("screens"):
        raise ValidationError(f"{model}: coordinate non configurate in DmiPositions.json.")
    if not isinstance(data["screens"], dict):
        raise ValidationError("Il campo screens deve essere un oggetto.")
    return data


def integer(value, field: str) -> int:
    try:
        number = float(value)
        if isinstance(value, bool) or not math.isfinite(number) or not number.is_integer():
            raise ValueError
        return int(number)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValidationError(f"Valore non intero per {field}: {value!r}") from exc


def compile_script(source: bytes, name: str, model: str, database: dict, *, y_offset_mm: int = 0) -> Script:
    """Resolve the entire script before allowing any hardware movement."""
    y_offset_mm = integer(y_offset_mm, "offset Y")
    if not name.lower().endswith(".xml"):
        raise ValidationError("Seleziona un file con estensione .xml.")
    if len(source) > MAX_XML_BYTES:
        raise ValidationError("Lo script supera il limite di 2 MB.")
    if b"<!DOCTYPE" in source.upper() or b"<!ENTITY" in source.upper():
        raise ValidationError("Dichiarazioni DTD ed entità non sono ammesse negli script.")
    try:
        root = ET.fromstring(source)
    except ET.ParseError as exc:
        raise ValidationError(f"XML non valido: {exc}") from exc
    if root.tag != "sequence":
        raise ValidationError("La radice XML deve essere <sequence>.")
    if not len(root) or len(root) > 5000:
        raise ValidationError("La sequenza deve contenere da 1 a 5000 comandi.")
    data = model_data(database, model)
    screens = data["screens"]
    current = next(iter(screens))
    last_button = None
    compiled = []

    def lookup(target: str):
        nonlocal current
        active = screens.get(current, {})
        if isinstance(active, dict) and target in active.get("buttons", {}):
            button = active["buttons"][target]
        else:
            matches = [(key, screen["buttons"][target]) for key, screen in screens.items()
                       if isinstance(screen, dict) and isinstance(screen.get("buttons"), dict)
                       and target in screen["buttons"]]
            if not matches:
                raise ValidationError(f"Tasto {target!r} non mappato per {model}.")
            if len(matches) > 1:
                raise ValidationError(f"Tasto {target!r} ambiguo fuori dalla schermata corrente.")
            current, button = matches[0]
        if not isinstance(button, dict) or "x" not in button or "y" not in button:
            raise ValidationError(f"Coordinate mancanti per {target}.")
        x, y = integer(button["x"], f"{target}.x"), integer(button["y"], f"{target}.y")
        y += y_offset_mm
        duration = integer(button.get("click_duration_ms", data.get("click_duration_ms", 200)),
                           f"{target}.click_duration_ms")
        if duration <= 0:
            raise ValidationError(f"La durata di pressione di {target} deve essere positiva.")
        return button, x, y, duration

    def follow(button: dict):
        nonlocal current
        destination = button.get("leads_to")
        if not destination:
            return
        if destination in screens:
            current = destination
        else:
            matches = [key for key, screen in screens.items()
                       if isinstance(screen, dict) and screen.get("parent") == destination]
            current = matches[0] if len(matches) == 1 else destination

    for number, element in enumerate(root, 1):
        try:
            if element.tag != "command" or len(element):
                raise ValidationError("Sono ammessi solo elementi <command> senza figli.")
            action = element.get("action", "")
            target = element.get("target", "")
            operations = []
            if action in ("PRESS", "MOVE_TO"):
                if not target:
                    raise ValidationError("Attributo target mancante.")
                button, x, y, duration = lookup(target)
                operations.append(Operation("MOVE", (x, y, 0)))
                if action == "PRESS":
                    operations.append(Operation("MOVE_AND_CLICK", (x, y, duration)))
                    follow(button)
                detail = f"X {x} · Y {y}" + (f" · {duration} ms" if action == "PRESS" else "")
                last_button = target
            elif action == "WAIT":
                try:
                    duration = float(element.get("duration", "1000"))
                except ValueError as exc:
                    raise ValidationError("Durata WAIT non numerica.") from exc
                if not math.isfinite(duration) or duration < 0:
                    raise ValidationError("La durata WAIT deve essere finita e non negativa.")
                operations.append(Operation("WAIT", (duration / 1000,)))
                detail = f"{duration:g} ms"
                target = "Attesa"
            elif action == "WRITE_T9":
                if not target or len(target) > 4096:
                    raise ValidationError("WRITE_T9 richiede un target da 1 a 4096 caratteri.")
                for char in target.upper():
                    match = next(((key, chars.index(char) + 1)
                                  for key, chars in T9.items() if char in chars), None)
                    if match is None:
                        raise ValidationError(f"Carattere T9 non supportato: {char!r}.")
                    key, clicks = match
                    physical = "KEY_" + key
                    _, x, y, _ = lookup(physical)
                    if physical == last_button:
                        operations.append(Operation("WAIT", (0.3,)))
                    else:
                        operations.append(Operation("MOVE", (x, y, 0)))
                    for _ in range(clicks):
                        operations.extend((Operation("MOVE_AND_CLICK", (x, y, 40)),
                                           Operation("WAIT", (0.02,))))
                    last_button = physical
                detail = f"{len(target)} caratteri · multi-tap"
            else:
                raise ValidationError(f"Azione sconosciuta: {action!r}.")
            compiled.append(Command(number, action, target, detail, tuple(operations)))
        except ValidationError as exc:
            raise ValidationError(f"Comando {number}: {exc}") from exc
    return Script(name, model, tuple(compiled), source, y_offset_mm)


class RealBackend:
    """No protocol assumptions beyond those present in the original GUI."""
    def __init__(self, directory: Path):
        cfg_module = importlib.import_module("YamlCfg")
        protocol_module = importlib.import_module("ComProtocol")
        log_module = importlib.import_module("Logger")
        self.messages = importlib.import_module("DmiMessages").DmiMessages
        self.master = importlib.import_module("DmiControllerMaster").DmiControllerMaster
        cfg = cfg_module.YamlCfg(str(directory / "pc_cfg.yaml"))
        log_module.setup_logging(cfg.log_level, "DmiGUI")
        self.protocol = protocol_module.ComProtocol(cfg.address, cfg.remote_address)
        self.controller = self.master(self.protocol.put_data, self.protocol.get_data)

    def send(self, name: str, args: tuple) -> bool:
        message = getattr(self.messages, name)
        if name == "ACK":
            action = self.master.Action(message, [], self.messages.ACK, 0, 1)
        elif name == "GET_PICTURES":
            action = self.master.Action(message, [], self.messages.PICTURE)
        else:
            action = self.master.Action(message, list(args), self.messages.DONE, 0)
        success, _ = self.controller.manage_action(action)
        return bool(success)


class ObservationRuntime:
    """GUI owner of the reusable observation workers, separate from command Runner."""
    def __init__(self):
        self.observer = None
        self._lifecycle = RLock()
        self._generation = 0

    @property
    def running(self):
        return self.observer is not None and self.observer.running

    def start(self, kind, address, *, calibration_path=None, context_path=None, debug_jsonl=None):
        with self._lifecycle:
            generation = self._generation
            if self.running:
                raise RuntimeError("Stop the current vision session first")
        # Imported only on explicit observation start; demo startup needs no CV.
        from dmi_robot_master.integration.camera import ReplayCamera, RemoteCamera, RobotCamera
        from dmi_robot_master.integration.calibration import read_json
        from dmi_robot_master.integration.vision_observer import VisionObserver
        if kind == "recorded_replay":
            path = Path(address).expanduser().resolve()
            source, info = ReplayCamera(path), {"kind": kind, "path": str(path), "simulation": True}
        elif kind == "remote_bridge":
            source = RemoteCamera(address, timeout=1., request_fps=10.)
            info = {"kind": kind, "url": address, "simulation": False}
        elif kind == "local_camera":
            index = integer(address, "Camera index")
            if index < 0:
                raise ValueError("Camera index must be nonnegative")
            source = RobotCamera(index, timeout=1.)
            info = {"kind": kind, "index": index, "requested_size": [None, None], "simulation": False}
        else:
            raise ValueError("Unsupported vision source")
        info.update(rotation_clockwise=0, mirror_horizontal=False)
        context = read_json(context_path) if context_path else None
        observer = VisionObserver(source, info, calibration_path=calibration_path or None,
                                  context=context, debug_jsonl=debug_jsonl)
        with self._lifecycle:
            if generation != self._generation or self.running:
                raise RuntimeError("Vision start cancelled by session change")
            self.observer = observer
            observer.start()

    def invalidate(self):
        with self._lifecycle:
            self._generation += 1
            if self.observer:
                self.observer.invalidate()

    def close(self):
        self.invalidate()
        with self._lifecycle:
            observer = self.observer
        if observer:
            observer.close()


class Runner:
    def __init__(self, directory: Path, emit: Callable = lambda *a, **k: None):
        self.directory = directory
        self.emit = emit
        self.mode = "hardware"
        self.backend = None
        self.initialized = False
        self.busy = False
        self.phase = "idle"
        self.stop = asyncio.Event()
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="dmi-protocol")

    async def _worker_call(self, function, *args):
        return await asyncio.get_running_loop().run_in_executor(self.worker, function, *args)

    def set_mode(self, mode: str):
        if self.busy:
            raise HardwareError("Attendi il termine dell'operazione.")
        if mode not in ("demo", "hardware"):
            raise ValueError(mode)
        if mode != self.mode:
            self.mode = mode
            # Keep the real adapter alive so ComProtocol background resources are
            # not duplicated when the user switches to demo and back.
            self.initialized = False

    async def _send(self, name: str, args: tuple = ()):
        self.emit("transmit", name=name, args=args)
        if self.mode == "demo":
            delay = 0.08 if name == "ACK" else 0.22
            if name == "INITIALIZE":
                delay = 0.8
            elif name == "MOVE_AND_CLICK":
                delay = max(delay, args[2] / 1000)
            await asyncio.sleep(delay)
            return True
        try:
            return await self._worker_call(self.backend.send, name, args)
        except Exception as exc:
            raise HardwareError(f"{name}: {exc}") from exc

    async def _checked_send(self, name: str, args: tuple = ()):
        if not await self._send(name, args):
            raise HardwareError(f"{name}: errore o timeout restituito dal controller.")

    async def _handshake(self, interruptible=False):
        deadline = asyncio.get_running_loop().time() + 3
        while asyncio.get_running_loop().time() < deadline:
            if interruptible and self.stop.is_set():
                raise Stopped
            if await self._send("ACK"):
                return
            await asyncio.sleep(0.1)
        raise HardwareError("Nessun ACK dal Raspberry Pi. Controlla rete e processo Slave.")

    async def initialize(self):
        if self.busy:
            raise HardwareError("Un'operazione è già in corso.")
        self.busy, self.initialized, self.phase = True, False, "initializing"
        self.stop.clear()
        self.emit("status", text="Sincronizzazione con il controller…")
        try:
            if self.mode == "hardware" and self.backend is None:
                self.backend = await self._worker_call(RealBackend, self.directory)
            await self._handshake()
            self.emit("status", text="Inizializzazione degli assi in corso…")
            await self._checked_send("INITIALIZE")
            self.initialized = True
            self.emit("initialized")
        except Exception:
            self.initialized = False
            raise
        finally:
            self.busy, self.phase = False, "idle"

    def request_stop(self):
        if self.phase == "running":
            self.stop.set()
            self.emit("status", text="Arresto richiesto · attesa del comando in corso…")

    async def capture_pictures(self):
        """Run the exact camera actions supplied by the project author, in order."""
        if self.busy or not self.initialized:
            raise HardwareError("La postazione deve essere inizializzata e libera.")
        self.busy, self.phase = True, "capturing"
        try:
            self.emit("status", text="Acquisizione foto in corso…")
            await self._checked_send("TAKE_PICTURES", (0, 1, 1))
            self.emit("status", text="Ricezione foto in corso…")
            await self._checked_send("GET_PICTURES")
        finally:
            # A camera failure does not imply that axis homing has been lost.
            self.busy, self.phase = False, "idle"

    async def _wait(self, seconds: float):
        if self.stop.is_set():
            raise Stopped
        try:
            await asyncio.wait_for(self.stop.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            return
        raise Stopped

    async def run(self, script: Script) -> str:
        if self.busy or not self.initialized:
            raise HardwareError("Inizializza l'hardware prima di avviare.")
        if not script.commands:
            raise ValidationError("La sequenza è vuota.")
        self.busy, self.phase = True, "running"
        self.stop.clear()
        handshake_ok = False
        outcome = "completed"
        try:
            try:
                self.emit("status", text="Verifica connessione prima della sequenza…")
                await self._handshake(interruptible=True)
                handshake_ok = True
                for index, command in enumerate(script.commands):
                    if self.stop.is_set():
                        raise Stopped
                    self.emit("command_start", index=index, command=command)
                    for operation in command.operations:
                        if self.stop.is_set():
                            raise Stopped
                        if operation.name == "WAIT":
                            await self._wait(operation.args[0])
                        else:
                            await self._checked_send(operation.name, operation.args)
                            # Let queued UI stop events run even with an instant backend.
                            await asyncio.sleep(0)
                    self.emit("command_done", index=index, command=command)
                if self.stop.is_set():
                    outcome = "stopped"
            except Stopped:
                outcome = "stopped"
            if handshake_ok:
                self.phase = "parking"
                self.emit("status", text="Rientro all'origine [0, 0, 0]…")
                await self._checked_send("MOVE", (0, 0, 0))
            self.emit("finished", outcome=outcome)
            return outcome
        except Exception:
            # Position/connection is uncertain. Do not queue an automatic motion.
            self.initialized = False
            self.emit("fault")
            raise
        finally:
            self.busy, self.phase = False, "idle"

    def shutdown(self):
        # Never cancel a synchronous controller call: its physical outcome would
        # still be pending. Normal window-close is blocked while busy by the UI.
        self.worker.shutdown(wait=False, cancel_futures=False)
