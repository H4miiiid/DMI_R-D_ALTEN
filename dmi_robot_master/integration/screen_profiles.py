"""Editable SENSE lock profiles; vocabulary is bounded by the existing detector.

Profiles select evidence, never produce detections or grant action permissions.
Loaded once per observation session: stop/restart observation after editing JSON.
"""
from dataclasses import dataclass
import json
from pathlib import Path

from dmi_computer_vision.src.dmi.detection.title_ocr import title_state

PROFILE_PATH = Path(__file__).with_name('screen_profiles.json')
KEYPAD = {f'digit_{i}' for i in range(10)} | {'delete', 'decimal'}
ARROWS = {'left_arrow', 'right_arrow', 'close'}
# Supported identities, not required controls. Keep aligned with right_layout /
# right_display; JSON cannot teach the detector a new title or button identity.
RIGHT_BUTTONS = {
    'Main': {'start', 'driver_id', 'train_data', 'level', 'train_running_number',
             'shunting', 'non_leading', 'maintain_shunting', 'radio_data', 'close', 'empty_driver_id'},
    'Driver ID': KEYPAD | {'cancel', 'trn', 'settings', 'empty_action'},
    'Level': {f'level_{i}' for i in range(4)} | {'pzb', 'kvb', 'scmt', 'lzb', 'memor',
             'atc_2', 'tbl1_plus', 'more', 'close'},
    'Train Running Number': KEYPAD | {'close'},
    'Train Data': {'gamma', 'lambda', 'enter_data'} | ARROWS,
    'Train Data (1/2)': KEYPAD | {'select_type'} | ARROWS,
    'Train Data (2/2)': {'g1', 'ga', 'gb', 'gc', 'out_of_gc', 'select_type'} | ARROWS,
    'Validate Train Data': {'yes', 'no'} | ARROWS,
}
NORMAL_SCREENS = {'Main', 'Driver ID', 'Level', 'Train Running Number'}
FIELD_NAMES = {'Driver ID': 'driver_id', 'Level': 'level',
               'Train Running Number': 'train_running_number',
               'Train Data': 'train_type', 'Validate Train Data': 'confirmation'}


def region_at(result: dict, key: tuple[str, ...]) -> dict | None:
    value = result
    for part in key:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


@dataclass(frozen=True)
class ScreenProfile:
    title: str
    title_side: str
    required: frozenset[tuple[str, ...]]
    allowed: frozenset[tuple[str, ...]]
    dynamic_ocr: tuple[str, ...] | None
    field_name: str | None
    confirmation: tuple[str, ...] | None
    reuse_left_sidebar: bool

    @property
    def title_key(self) -> tuple[str, ...]:
        return (self.title_side + '_display', 'title')

    def matches(self, result: dict) -> bool:
        title = region_at(result, self.title_key)
        return bool(title and ' '.join((title.get('text') or '').casefold().split())
                    == self.title.casefold())

    def metadata(self) -> dict:
        return {'title_side': self.title_side,
                'dynamic_ocr': '/'.join(self.dynamic_ocr) if self.dynamic_ocr else None,
                'field_name': self.field_name,
                'confirmation': '/'.join(self.confirmation) if self.confirmation else None,
                'optional': sorted('/'.join(key) for key in self.allowed-self.required)}


def _supported(title: str, side: str) -> set[str]:
    if side == 'left':
        return ({f'boxes/box_{i}' for i in range(1, 23)} | {'speed_indicator'}
                if title in NORMAL_SCREENS else {'buttons/yes'})
    return {f'buttons/{name}' for name in RIGHT_BUTTONS[title]} | (
        {'data_field'} if title in FIELD_NAMES else set())


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key {key!r}')
        result[key] = value
    return result


def load_profiles(path: str | Path = PROFILE_PATH) -> dict[str, ScreenProfile]:
    """Fail clearly on typos/unsupported identities; never silently use defaults."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_unique_object)
        if not isinstance(data, dict) or set(data) != {'schema_version', 'screens'}:
            raise ValueError('expected schema_version and screens')
        if type(data['schema_version']) is not int or data['schema_version'] != 1:
            raise ValueError('schema_version must be 1')
        if not isinstance(data['screens'], list) or not data['screens']:
            raise ValueError('screens must be a nonempty list')
        profiles = {}
        for entry in data['screens']:
            keys = {'title', 'title_side', 'left', 'right', 'dynamic_ocr',
                    'confirmation', 'reuse_left_sidebar'}
            if not isinstance(entry, dict) or set(entry) != keys:
                raise ValueError(f'each screen needs exactly {sorted(keys)}')
            title = entry['title']
            if not isinstance(title, str) or title not in RIGHT_BUTTONS or title_state(title) != title:
                raise ValueError(f'unsupported exact detector title {title!r}')
            if title in profiles:
                raise ValueError(f'duplicate screen title {title!r}')
            side = 'right' if title in NORMAL_SCREENS else 'left'
            if entry['title_side'] != side:
                raise ValueError(f'{title}: detector title is on the {side}')
            if type(entry['reuse_left_sidebar']) is not bool or (
                    entry['reuse_left_sidebar'] and title not in NORMAL_SCREENS):
                raise ValueError(f'{title}: sidebar reuse is supported only on normal screens')
            required, allowed = {(side + '_display', 'title')}, {(side + '_display', 'title')}
            for panel in ('left', 'right'):
                controls = entry[panel]
                if not isinstance(controls, dict) or set(controls) != {'required', 'optional'}:
                    raise ValueError(f'{title}.{panel}: expected required and optional lists')
                seen = set()
                for role in ('required', 'optional'):
                    names = controls[role]
                    if not isinstance(names, list) or any(not isinstance(n, str) for n in names):
                        raise ValueError(f'{title}.{panel}.{role}: expected string list')
                    for name in names:
                        if name not in _supported(title, panel):
                            raise ValueError(f'{title}.{panel}.{role}: unsupported control {name!r}')
                        if name in seen:
                            raise ValueError(f'{title}.{panel}: repeated control {name!r}')
                        seen.add(name)
                        key = (panel + '_display', *name.split('/'))
                        allowed.add(key)
                        if role == 'required':
                            required.add(key)
            dynamic = entry['dynamic_ocr']
            field_key = ('right_display', 'data_field')
            if dynamic is not None:
                if (not isinstance(dynamic, dict) or set(dynamic) != {'region', 'name'}
                        or title not in FIELD_NAMES or dynamic['region'] != '/'.join(field_key)
                        or dynamic['name'] != FIELD_NAMES[title] or field_key not in required):
                    raise ValueError(f'{title}: unsupported dynamic_ocr; use required right data_field '
                                     f'and name {FIELD_NAMES.get(title)!r}')
            confirmation = entry['confirmation']
            if confirmation is not None and (title not in {'Driver ID', 'Level'}
                    or confirmation != '/'.join(field_key) or field_key not in allowed):
                raise ValueError(f'{title}: confirmation role requires configured right data_field '
                                 'on Driver ID/Level; it grants no action permission')
            profiles[title] = ScreenProfile(title, side, frozenset(required), frozenset(allowed),
                field_key if dynamic else None, dynamic['name'] if dynamic else None,
                field_key if confirmation else None, entry['reuse_left_sidebar'])
        return profiles
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(f'Invalid SENSE screen profiles {path}: {exc}') from exc
