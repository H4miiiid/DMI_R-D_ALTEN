"""Event-driven execution animation. Display only: never schedules robot actions."""
from __future__ import annotations

import math
import time

import flet as ft

TEXT, MUTED = "#EEF3FA", "#9AAABD"
ACCENT, BLUE, AMBER, RED = "#9BE9C5", "#91BFFF", "#F2BE73", "#FF8F98"
LINE = "#263D4B"


def motion(duration=260):
    return ft.Animation(duration, ft.AnimationCurve.EASE_OUT_CUBIC)


class ExecutionActivity:
    """Compact schematic, step rail and phase indicator shared by all UI states.

    Coordinates are fitted to the plan, including its panel offset and origin.
    The diagram shows requested commands, never measured motion or click success.
    Native Flet tweens interpolate between updates; tick() only drives the pulse.
    """
    WIDTH, HEIGHT, MARGIN = 210, 124, 26

    def __init__(self):
        self.total = self.completed = 0
        self.step = None
        self.active = False
        self.phase = "idle"
        self._bounds = (0, 1, 0, 1)
        self._pulse_started = None
        self._hold_until = 0.0
        self._settle_until = 0.0
        self._last_tick = 0.0
        self._color = BLUE
        self.phase_text = ft.Text("In attesa", size=11, color=MUTED, weight=ft.FontWeight.W_600)
        self.phase_icon = ft.Icon(ft.Icons.PAUSE_CIRCLE_OUTLINE_ROUNDED, size=16, color=MUTED)
        self.phase_switch = ft.AnimatedSwitcher(
            ft.Row([self.phase_icon, self.phase_text], spacing=7, tight=True),
            duration=180, reverse_duration=100,
            transition=ft.AnimatedSwitcherTransition.FADE)
        self.phase_badge = ft.Container(self.phase_switch, bgcolor="#182B38", border_radius=7,
            padding=ft.Padding.symmetric(horizontal=10, vertical=6), animate=motion())
        self.step_text = ft.Text("SEQUENZA NON CARICATA", size=10, color=MUTED,
                                 weight=ft.FontWeight.W_600)
        self.target_text = ft.Text("In attesa di una sequenza", size=19, color=TEXT,
            weight=ft.FontWeight.W_600, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        self.detail_text = ft.Text("Caricamento e validazione dello script richiesti.", size=12,
            color=MUTED, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)
        self.counter = ft.Text("0 / 0", size=11, color=MUTED, font_family="Consolas")
        self.segments = [ft.Container(height=4, bgcolor=LINE, border_radius=3, expand=True,
                                      animate=motion(300)) for _ in range(20)]
        self.rail = ft.Row(self.segments, spacing=4)

        grid = [ft.Container(left=x, top=0, width=1, height=self.HEIGHT, bgcolor="#172C39")
                for x in range(0, self.WIDTH, 21)]
        grid += [ft.Container(left=0, top=y, width=self.WIDTH, height=1, bgcolor="#172C39")
                 for y in range(0, self.HEIGHT, 21)]
        self.targets = ft.Stack(width=self.WIDTH, height=self.HEIGHT)
        self.cross_x = ft.Container(left=self.MARGIN, top=0, width=1, height=self.HEIGHT,
                                    bgcolor="#294C5A", animate_position=motion(320))
        self.cross_y = ft.Container(left=0, top=self.HEIGHT-self.MARGIN, width=self.WIDTH, height=1,
                                    bgcolor="#294C5A", animate_position=motion(320))
        self.halo = ft.Container(left=2, top=self.HEIGHT-self.MARGIN-24, width=48, height=48,
            border_radius=30, border=ft.Border.all(1.5, ACCENT), opacity=0, scale=0.65,
            animate_position=motion(320), animate_scale=motion(240), animate_opacity=motion(200))
        self.pointer_icon = ft.Icon(ft.Icons.MY_LOCATION_ROUNDED, size=19, color=BLUE)
        self.pointer = ft.Container(self.pointer_icon, left=self.MARGIN-17,
            top=self.HEIGHT-self.MARGIN-17, width=34, height=34, border_radius=12,
            alignment=ft.Alignment.CENTER, bgcolor="#173C4B", border=ft.Border.all(1, "#4B8994"),
            shadow=ft.BoxShadow(blur_radius=15, spread_radius=1, color="#3036BBA0"),
            scale=1, animate_position=motion(320), animate_scale=motion(170), animate=motion(180))
        self.scan = ft.Container(left=0, top=0, width=self.WIDTH, height=2,
            bgcolor=ACCENT, opacity=0, animate_position=motion(340), animate_opacity=motion(200))
        self.map = ft.Container(ft.Stack(grid + [self.targets, self.cross_x, self.cross_y,
            self.halo, self.pointer, self.scan], width=self.WIDTH, height=self.HEIGHT,
            clip_behavior=ft.ClipBehavior.HARD_EDGE), bgcolor="#0B1723",
            border=ft.Border.all(1, LINE), border_radius=12, clip_behavior=ft.ClipBehavior.ANTI_ALIAS)
        self.coordinate_text = ft.Text("X —  /  Y —", size=10, color=MUTED, font_family="Consolas")
        self.control = ft.Container(ft.Column([
            ft.Row([ft.Text("MONITOR ESECUZIONE", size=10, color=MUTED, weight=ft.FontWeight.W_600),
                    ft.Container(expand=True), self.phase_badge]),
            ft.Row([
                ft.Column([self.step_text, self.target_text, self.detail_text], spacing=7, expand=True),
                ft.Column([self.map, self.coordinate_text], spacing=5,
                          horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            ], spacing=20, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Row([ft.Container(self.rail, expand=True), self.counter], spacing=14),
            ft.Text("Schema dei comandi richiesti · posizione reale non misurata", size=10, color=MUTED),
        ], spacing=12), padding=18, border_radius=14, border=ft.Border.all(1, "#2B4650"),
            gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                                       colors=["#142B31", "#101D2E"]), animate=motion())
        self.configure(None)

    def configure(self, script):
        self.total = len(script.commands) if script else 0
        self.completed, self.step = 0, None
        coordinates = {(0, 0)}
        if script:
            coordinates.update(op.args[:2] for cmd in script.commands for op in cmd.operations
                               if op.name in ("MOVE", "MOVE_AND_CLICK"))
        xs, ys = zip(*coordinates)
        self._bounds = (min(xs), max(xs), min(ys), max(ys))
        # At most 80 visual targets, even for very large XML files.
        ordered = sorted(coordinates)
        stride = max(1, math.ceil(len(ordered) / 80))
        self.targets.controls = [ft.Container(left=self.project(x, y)[0]-2,
            top=self.project(x, y)[1]-2, width=4, height=4, border_radius=3, bgcolor="#466777")
            for x, y in ordered[::stride]]
        self.move_to(0, 0)
        self.coordinate_text.value = "X —  /  Y —"
        self.step_text.value = f"{self.total:02d} STEP VALIDATI" if script else "SEQUENZA NON CARICATA"
        self.set_phase("ready" if script else "idle", "Sequenza validata" if script else "In attesa",
            title=script.name if script else "In attesa di una sequenza",
            detail="Esecuzione disponibile dopo l'inizializzazione." if script else
                   "Caricamento e validazione dello script richiesti.", active=False)
        self.update_rail()

    def project(self, x, y):
        low_x, high_x, low_y, high_y = self._bounds
        nx = (x-low_x) / max(1, high_x-low_x)
        ny = (y-low_y) / max(1, high_y-low_y)
        return (self.MARGIN + max(0, min(1, nx)) * (self.WIDTH-2*self.MARGIN),
                self.HEIGHT-self.MARGIN - max(0, min(1, ny)) * (self.HEIGHT-2*self.MARGIN))

    def move_to(self, x, y):
        px, py = self.project(x, y)
        self.pointer.left, self.pointer.top = px-17, py-17
        self.halo.left, self.halo.top = px-24, py-24
        self.cross_x.left, self.cross_y.top = px, py
        self.coordinate_text.value = f"X {x}  /  Y {y} mm"

    def set_phase(self, phase, caption, *, title=None, detail=None, active=True, color=None):
        self.phase, self.active = phase, active
        self._color = color or (ACCENT if phase in ("press", "complete", "ready") else BLUE)
        icons = {"press": ft.Icons.TOUCH_APP_ROUNDED, "move": ft.Icons.OPEN_WITH_ROUNDED,
                 "waiting": ft.Icons.HOURGLASS_TOP_ROUNDED, "parking": ft.Icons.HOME_OUTLINED,
                 "capture": ft.Icons.PHOTO_CAMERA_OUTLINED, "download": ft.Icons.DOWNLOAD_ROUNDED,
                 "complete": ft.Icons.CHECK_ROUNDED, "error": ft.Icons.ERROR_OUTLINE_ROUNDED,
                 "stopped": ft.Icons.STOP_ROUNDED, "stopping": ft.Icons.PAUSE_ROUNDED}
        icon = icons.get(phase, ft.Icons.MY_LOCATION_ROUNDED)
        if self.phase_text.value != caption:
            self.phase_text = ft.Text(caption, size=11, color=self._color, weight=ft.FontWeight.W_600)
            self.phase_icon = ft.Icon(icon, size=16, color=self._color)
            self.phase_switch.content = ft.Row([self.phase_icon, self.phase_text], spacing=7, tight=True)
        self.phase_text.color = self.phase_icon.color = self._color
        self.pointer_icon.icon, self.pointer_icon.color = icon, self._color
        if title is not None:
            self.target_text.value = title
        if detail is not None:
            self.detail_text.value = detail
        self.phase_badge.bgcolor = "#193D35" if self._color == ACCENT else "#1B2E43"
        self.halo.border = ft.Border.all(1.5, self._color)
        self.pointer.border = ft.Border.all(1, self._color)
        if phase != "press":
            self._hold_until = 0
        if not active:
            self._pulse_started = None
            self.halo.opacity = self.scan.opacity = 0
            self.pointer.scale = 1.12 if phase == "complete" else 1
            self._settle_until = time.monotonic() + 0.24 if phase == "complete" else 0
        self.update_rail()

    def start(self):
        self.completed, self.step = 0, None
        self.step_text.value = f"{self.total:02d} STEP DA ESEGUIRE"
        self.set_phase("sync", "Sincronizzazione", title="Avvio della sequenza",
                       detail="Verifica della connessione con il controller.")

    def start_command(self, index, command):
        self.step = index
        self.step_text.value = f"STEP {index+1:02d} / {self.total:02d} · {command.action}"
        self.set_phase("waiting" if command.action == "WAIT" else "move",
            "Attesa programmata" if command.action == "WAIT" else "Esecuzione step",
            title="Attesa programmata" if command.action == "WAIT" else command.target,
            detail=command.detail)

    def command_done(self, index):
        self.completed = index+1
        self.update_rail()

    def transmit(self, name, args, phase):
        if name in ("MOVE", "MOVE_AND_CLICK"):
            self.move_to(args[0], args[1])
        if name == "MOVE_AND_CLICK":
            self.set_phase("press", "Pressione in corso")
            now = time.monotonic()
            self._pulse_started = now
            self._hold_until = now + max(0.4, args[2]/1000)
            self.pointer.scale = 0.82
            self.halo.scale, self.halo.opacity = 0.65, 0.9
        elif name == "MOVE":
            if phase == "parking":
                self.set_phase("parking", "Rientro all'origine", title="Rientro della postazione",
                               detail="Comando richiesto: X 0 mm · Y 0 mm")
            else:
                self.set_phase("move", "Posizionamento")
        elif name == "INITIALIZE":
            self.set_phase("homing", "Inizializzazione", title="Inizializzazione degli assi",
                           detail="Attesa della conferma dal controller.")
        elif name == "TAKE_PICTURES":
            self.set_phase("capture", "Acquisizione foto", title="Acquisizione immagine",
                           detail="Attesa del completamento dell'acquisizione.")
        elif name == "GET_PICTURES":
            self.set_phase("download", "Ricezione foto", title="Ricezione immagine",
                           detail="Attesa del file nella cartella configurata.")

    def update_rail(self):
        self.counter.value = f"{self.completed:02d} / {self.total:02d}"
        for i, segment in enumerate(self.segments):
            done = self.total > 0 and (i+1)/len(self.segments) <= self.completed/self.total
            current = self.active and self.step is not None and i == min(19, int(self.step*20/max(1, self.total)))
            segment.bgcolor = ACCENT if done else self._color if current else LINE
            segment.opacity = 1

    def tick(self, now=None):
        now = time.monotonic() if now is None else now
        if not self.active:
            if self._settle_until and now >= self._settle_until:
                self._settle_until = 0
                self.pointer.scale = 1
                return True
            return False
        if now-self._last_tick < 0.12:
            return False
        self._last_tick = now
        wave = (math.sin(now*5)+1)/2
        pressing = self.phase == "press" and now < self._hold_until
        self.pointer.scale = 0.87 + 0.10*wave if pressing else 1
        pulse = ((now-(self._pulse_started or now)) % 0.75)/0.75
        if pressing:
            self.halo.scale, self.halo.opacity = 0.65 + 0.95*pulse, 0.8*(1-pulse)
        else:
            self.halo.scale, self.halo.opacity = 0.95+0.18*wave, 0.13+0.15*wave
        scanning = self.phase in ("capture", "download")
        self.scan.opacity = 0.55 if scanning else 0
        if scanning:
            self.scan.top = 8 + (self.HEIGHT-16)*wave
        if self.step is not None:
            index = min(19, int(self.step*20/max(1, self.total)))
            self.segments[index].opacity = 0.5+0.5*wave
        return True
