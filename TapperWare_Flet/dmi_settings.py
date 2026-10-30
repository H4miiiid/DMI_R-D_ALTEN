"""Persistent operator options; never rewrites the DMI coordinate database."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
import json
from pathlib import Path
import os
import tempfile

from dmi_runtime import ValidationError, integer

PANELS = ("inferiore", "superiore")


@dataclass(frozen=True)
class AppSettings:
    photo_directory: str = ""
    photo_wait_seconds: int = 15
    photo_recursive: bool = False
    y_offset_mm: int = 0
    offset_panel: str = "superiore"
    selected_panel: str = "inferiore"

    def validate(self):
        if not isinstance(self.photo_directory, str) or "\x00" in self.photo_directory:
            raise ValidationError("La cartella foto deve essere un percorso.")
        if self.offset_panel not in PANELS or self.selected_panel not in PANELS:
            raise ValidationError("Scegli Pannello superiore o Pannello inferiore.")
        offset = integer(self.y_offset_mm, "offset Y")
        timeout = integer(self.photo_wait_seconds, "attesa foto")
        if not 1 <= timeout <= 120:
            raise ValidationError("L'attesa della foto deve essere fra 1 e 120 secondi.")
        if not isinstance(self.photo_recursive, bool):
            raise ValidationError("Il valore Includi sottocartelle non è valido.")
        return replace(self, y_offset_mm=offset, photo_wait_seconds=timeout)

    def offset_for(self, panel: str) -> int:
        if panel not in PANELS:
            raise ValidationError("Pannello non valido.")
        return integer(self.y_offset_mm, "offset Y") if panel == self.offset_panel else 0

    def photo_path(self, directory: Path) -> Path | None:
        if not self.photo_directory.strip():
            return None
        path = Path(self.photo_directory).expanduser()
        return path if path.is_absolute() else directory / path


def load_settings(path: Path) -> AppSettings:
    if not path.exists():
        return AppSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("è richiesto un oggetto JSON")
        known = {field.name for field in fields(AppSettings)}
        return AppSettings(**{key: value for key, value in data.items() if key in known}).validate()
    except (OSError, ValueError, TypeError) as exc:
        raise ValidationError(f"Impossibile caricare le impostazioni: {exc}") from exc


def save_settings(path: Path, settings: AppSettings):
    settings = settings.validate()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
            temp_path = Path(stream.name)
            json.dump(asdict(settings), stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()
