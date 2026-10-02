"""Source-independent compact state, recursive updates and flushed JSONL output."""
from copy import deepcopy
import json
import math
import sys
import time


def write_record(stream, record):
    # Encode before writing, so invalid values cannot leave a partial JSON line.
    stream.write(json.dumps(record, separators=(",", ":"), ensure_ascii=False,
                            allow_nan=False) + "\n")
    stream.flush()


def geometry(region):
    return None if region is None else {key: region[key] for key in ("center", "corners")}


def compact_state(result):
    """Project existing detections; never infer missing screen content."""
    left, right = result["left_display"], result["right_display"]
    field = right["data_field"]
    field_name = {"Driver ID": "driver_id", "Level": "level",
                  "Train Running Number": "train_running_number",
                  "Train Data": "train_type", "Validate Train Data": "validation"}.get(
                      right["state"], "input")
    return deepcopy({
        "left_display": {
            "geometry": geometry(left["geometry"]),
            "boxes": {name: {"center": box["center"], "icon": box["icon"]}
                      for name, box in left["boxes"].items()},
            "speed_indicator": geometry(left["speed_indicator"]),
        },
        "right_display": {
            "geometry": geometry(right["geometry"]), "state": right["state"],
            "visibility": right["visibility"],
            "title": right["title"]["text"] if right["title"] else None,
            "title_geometry": geometry(right["title"]),
            "fields": {} if field is None else {
                field_name: {"value": field["value"], **geometry(field)}},
            "buttons": {name: button["center"] for name, button in right["buttons"].items()},
        },
    })


def layout_changed(old, new):
    if isinstance(old, dict) or isinstance(new, dict):
        if not isinstance(old, dict) or not isinstance(new, dict) or old.keys() != new.keys():
            return True
        return any(layout_changed(old[key], new[key]) for key in old)
    return False


def close_coordinates(old, new, tolerance):
    if isinstance(old, list) and isinstance(new, list):
        return len(old) == len(new) and all(close_coordinates(a, b, tolerance)
                                           for a, b in zip(old, new))
    return (type(old) in (int, float) and type(new) in (int, float)
            and abs(old - new) <= tolerance)


_UNCHANGED = object()


def difference(old, new, tolerance):
    if isinstance(old, dict) and isinstance(new, dict):
        changes = {}
        for key, value in new.items():
            delta = difference(old[key], value, tolerance)
            if delta is not _UNCHANGED:
                changes[key] = delta
        return changes if changes else _UNCHANGED
    if isinstance(new, list) and close_coordinates(old, new, tolerance):
        return _UNCHANGED
    return _UNCHANGED if old == new else deepcopy(new)


def apply_update(state, update):
    """Recursively merge object keys; lists/scalars/null replace their old value."""
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(state.get(key), dict):
            apply_update(state[key], value)
        else:
            state[key] = deepcopy(value)
    return state


class CompactWriter:
    def __init__(self, stream, metadata, *, geometry_tolerance=5.0):
        if (type(geometry_tolerance) not in (int, float)
                or not math.isfinite(geometry_tolerance) or geometry_tolerance < 0):
            raise ValueError("geometry_tolerance must be a finite nonnegative number")
        self.stream, self.tolerance = stream, geometry_tolerance
        self.state = None
        self.last_frame = -1
        self.last_timestamp = None
        self.records = 0
        self.emit({**metadata, "type": "session_start", "schema_version": 1,
                   "geometry_tolerance_px": geometry_tolerance})

    def emit(self, record):
        write_record(self.stream, record)
        self.records += 1

    def process(self, result, *, force_snapshot=False, context=None):
        index, timestamp = result["frame_index"], result["timestamp"]
        if (type(index) is not int or index <= self.last_frame
                or not math.isfinite(timestamp) or timestamp < 0
                or (self.last_timestamp is not None and timestamp <= self.last_timestamp)):
            raise ValueError("frame indices and finite timestamps must increase")
        current = compact_state(result)
        snapshot = (self.state is None or force_snapshot or layout_changed(self.state, current)
                    or any(self.state["right_display"][key] != current["right_display"][key]
                           for key in ("state", "visibility")))
        delta = current if snapshot else difference(self.state, current, self.tolerance)
        if delta is not _UNCHANGED:
            self.emit({"type": "snapshot" if snapshot else "update", "frame": index,
                       "timestamp": timestamp, **(context or {}), **delta})
            self.state = current if snapshot else apply_update(self.state, delta)
        self.last_frame, self.last_timestamp = index, timestamp

    def finish(self, **summary):
        self.emit({**summary, "type": "session_end", "last_frame": self.last_frame,
                   "last_timestamp": self.last_timestamp,
                   "records": self.records + 1})


class ProgressReporter:
    def __init__(self, label, total=None):
        self.label, self.total = label, total
        self.started = self.last = time.monotonic()

    def report(self, count, *, force=False):
        now = time.monotonic()
        if force or count == 1 or now - self.last >= 5:
            elapsed = now - self.started
            total = f" / {self.total}" if self.total else ""
            print(f"{self.label}: {count}{total} frames | {elapsed:.1f}s | "
                  f"{count / max(elapsed, 1e-9):.2f} processed FPS", file=sys.stderr, flush=True)
            self.last = now
