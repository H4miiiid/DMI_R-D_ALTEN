"""Presentation of a current target; never resolves or authorizes robot actions."""
import flet as ft


def format_pixels(point) -> str:
    return '—' if point is None else '[' + ', '.join(str(round(v)) for v in point) + ']'


def format_mm(point) -> str:
    return '—' if point is None else '[' + ', '.join(f'{v:.1f}' for v in point) + ']'


def target_name(identity: str) -> str:
    """Friendly text alongside the unchanged, region-qualified identity."""
    leaf = identity.rsplit('/', 1)[-1]
    if leaf.startswith('KEY_') and leaf[4:].isdigit():
        return f'Key {leaf[4:]}'
    return leaf.replace('_', ' ').capitalize()


def experimental_selection(view, selected):
    """Keep an operator's button identity; coordinates are checked only on click."""
    projection = (view or {}).get('projection') or {}
    context = (view or {}).get('experimental_context')
    if projection.get('experimental_recorded_test'):
        context = [(view or {}).get('session_id'), projection.get('screen')]
    return bool(selected and context and context[0] == selected[0]
                and context[1] in (selected[1], 'unknown')
                and (selected[2].startswith('KEY_') or '/button/' in selected[2]))


class TargetInspector:
    def __init__(self, app):
        self.app = app
        self._coordinate_key = None
        self.display_mm = None  # Display-only copy; never used to resolve actions.
        self.name = ft.Text('No key selected', size=22, weight=ft.FontWeight.W_600)
        self.pixel = ft.Text('Camera centre: —', selectable=True)
        self.xy = ft.Text('Robot XY estimate: —', selectable=True)
        self.age = ft.Text('Observation age: —')
        self.reason = ft.Text('Start the camera, then select a detected key.', size=12)
        self.hardware_press = ft.Button('Move and click selected key · 100 ms', disabled=True)
        self.control = ft.Column([
            self.name, self.pixel, self.xy, self.age,
            ft.Text('Display: whole pixels, 0.1 mm; live XY updates at 2 mm per axis. Actions use current coordinates.', size=11),
            ft.Divider(), self.hardware_press,
            ft.Text('Select a detected button. Experimental testing uses one click; ordinary pressing opens a confirmation. '
                    'Direct detection, matching calibration, robot readiness and movement limits are checked on click.', size=12),
            self.reason,
        ], spacing=9)

    def update(self, view=None):
        projection = (view or {}).get('projection')
        selected = self.app._vision_selection_key
        target = None
        if (view and view.get('fresh') and projection and selected
                and selected[:2] == (view['session_id'], projection['screen'])):
            target = projection['targets'].get(selected[2])
        if target is None:
            self._coordinate_key = self.display_mm = None
            self.name.value = 'No key selected'
            self.pixel.value = 'Camera centre: —'
            self.xy.value = 'Robot XY estimate: —'
            self.age.value = 'Observation age: —'
            self.reason.value = ('Select a detected key below. Selection does not move the robot.'
                                 if projection else 'Start the camera and wait for fresh detections.')
            if experimental_selection(view, selected):
                self.name.value = target_name(selected[2])
                self.reason.value = 'Selection retained. Click Experimental move and click to check the latest direct coordinates.'
            return
        self.name.value = target_name(selected[2])
        inspection = target.get('mm') is None and target.get('inspection_xy_mm') is not None
        key = (selected, projection.get('calibration_id'), projection.get('calibration_provenance'), inspection)
        mm = target.get('mm')
        if inspection:
            mm = target['inspection_xy_mm']
        if (key != self._coordinate_key or mm is None or self.display_mm is None
                or any(abs(a-b) >= 2. for a, b in zip(mm, self.display_mm))):
            self.display_mm = tuple(mm) if mm is not None else None
        self._coordinate_key = key
        self.pixel.value = f"Camera centre: {format_pixels(target['pixel'])} px (original image)"
        self.xy.value = (f"Robot XY estimate: {format_mm(self.display_mm)} mm · unverified"
                         if target.get('mm') is not None else 'Robot XY estimate: unavailable · load a matching calibration')
        if target.get('mm') is None and view.get('calibration_error'):
            self.xy.value = 'Robot XY estimate: unavailable · ' + view['calibration_error']
        self.age.value = f"Observation age: {view['age_seconds']:.2f} s"
        if projection.get('experimental_recorded_test') and target.get('mm') is None and not view.get('calibration_error'):
            self.xy.value = 'Robot XY estimate: unavailable · ' + target.get('mapping_error', 'no eligible button inside measured SENSE bounds')
        if inspection:
            self.xy.value = f'Read-only XY prediction: {format_mm(self.display_mm)} mm · unverified'
        if target.get('reference_xy_mm') is not None:
            self.xy.value += f"\nReference XY: {format_mm(target['reference_xy_mm'])} mm"
            if target.get('reference_error_mm') is not None:
                self.xy.value += f" · difference {target['reference_error_mm']:.1f} mm"
        if target.get('left_border_disagreement_px') is not None:
            policy = ('diagnostic only; experimental accuracy unverified'
                      if projection.get('experimental_allow_unverified_left') else '4 px action limit')
            self.xy.value += f"\nLeft-border disagreement: {target['left_border_disagreement_px']:.1f} px · {policy}"
        notes = []
        if target['kind'] != 'button':
            notes.append('This is an information field or mode box, not a normal press button.')
        if 'active' in target and target['active'] is not True:
            notes.append('The detected control is inactive or its activity is uncertain.')
        if view.get('calibration_error'):
            notes.append('Calibration: ' + view['calibration_error'])
        if target.get('mapping_error'):
            notes.append('Action mapping: ' + target['mapping_error'])
        notes.append('Move and click uses the latest valid target. Move without pressing remains optional.')
        self.reason.value = '\n'.join(notes)
