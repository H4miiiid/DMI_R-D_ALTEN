"""Find a newly downloaded, stable image without mistaking old photos for a result."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path


class PhotoError(RuntimeError):
    pass


EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}


@dataclass(frozen=True)
class Photo:
    path: Path
    preview: bytes
    width: int
    height: int


def snapshot_images(folder: Path, recursive: bool = False) -> dict[Path, tuple[int, int, int]]:
    if not folder.is_dir():
        raise PhotoError(f"Cartella foto non trovata: {folder}")
    snapshots = {}
    try:
        paths = folder.rglob("*") if recursive else folder.iterdir()
        for path in paths:
            if path.suffix.lower() not in EXTENSIONS:
                continue
            try:
                if path.is_file():
                    stat = path.stat()
                    snapshots[path] = (stat.st_mtime_ns, stat.st_size, stat.st_ctime_ns)
            except FileNotFoundError:
                continue  # A downloader may atomically replace a file while scanning.
    except OSError as exc:
        raise PhotoError(f"Impossibile leggere la cartella foto: {exc}") from exc
    return snapshots


def load_photo(path: Path) -> Photo:
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise PhotoError("Installa le dipendenze aggiornate: python -m pip install -r requirements.txt") from exc
    try:
        before = path.stat()
        with Image.open(path) as source:
            source.load()  # Reject incomplete files even when their header is readable.
            width, height = source.size
            display = ImageOps.exif_transpose(source).convert("RGB")
            display.thumbnail((1800, 1200))
            encoded = BytesIO()
            display.save(encoded, format="PNG")
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise PhotoError("La foto è ancora in scrittura.")
        return Photo(path, encoded.getvalue(), width, height)
    except PhotoError:
        raise
    except Exception as exc:
        raise PhotoError(f"Immagine non leggibile: {path.name}: {exc}") from exc


def latest_photo(folder: Path, recursive=False) -> Photo:
    candidates = snapshot_images(folder, recursive)
    if not candidates:
        raise PhotoError(f"Nessuna immagine nella cartella {folder}.")
    latest = max(candidates, key=lambda path: (candidates[path][0], str(path)))
    return load_photo(latest)


async def wait_for_new_photo(folder: Path, before: dict, *, timeout: float = 15,
                             recursive=False, interval: float = 0.3) -> Photo:
    deadline = asyncio.get_running_loop().time() + timeout
    previous = {}
    last_error = "Nessuna nuova immagine ricevuta."
    while asyncio.get_running_loop().time() < deadline:
        try:
            current = await asyncio.to_thread(snapshot_images, folder, recursive)
        except PhotoError as exc:
            # An asynchronous downloader may not have created its folder yet.
            last_error = str(exc)
            await asyncio.sleep(interval)
            continue
        changed = {path: stamp for path, stamp in current.items()
                   if before.get(path) != stamp and stamp[1] > 0}
        if changed:
            latest = max(changed, key=lambda path: (changed[path][0], str(path)))
            if previous.get(latest) == changed[latest]:
                try:
                    return await asyncio.to_thread(load_photo, latest)
                except PhotoError as exc:
                    last_error = str(exc)
        previous = changed
        await asyncio.sleep(interval)
    raise PhotoError(f"Foto non disponibile dopo {timeout:g} s. {last_error} "
                     "Verifica la cartella utilizzata da GET_PICTURES.")
