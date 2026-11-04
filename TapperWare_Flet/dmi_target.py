"""Presentation of a current target; never resolves or authorizes robot actions."""
import flet as ft


def target_name(identity: str) -> str:
    """Friendly text alongside the unchanged, region-qualified identity."""
    leaf = identity.rsplit('/', 1)[-1]
    if leaf.startswith('KEY_') and leaf[4:].isdigit():
        return f'Key {leaf[4:]}'
    return leaf.replace('_', ' ').capitalize()


class TargetInspector:
    def __init__(self, app):
        self.app = app
        self.name = ft.Text('No key selected', size=22, weight=ft.FontWeight.W_600)
        self.pixel = ft.Text('Camera centre: —', selectable=True)
        self.xy = ft.Text('Robot XY estimate: —', selectable=True)
        self.age = ft.Text('Observation age: —')
        self.reason = ft.Text('Start the camera, then select a detected key.', size=12)
        self.hardware_press = ft.Button('Move and click selected key · 100 ms', disabled=True)
        self.control = ft.Column([
            self.name, self.pixel, self.xy, self.age,
            ft.Divider(), self.hardware_press,
            ft.Text('Select a detected button, then confirm one 100 ms press. Fresh detection, valid calibration, '
                    'robot readiness and movement limits are required.', size=12),
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
            self.name.value = 'No key selected'
            self.pixel.value = 'Camera centre: —'
            self.xy.value = 'Robot XY estimate: —'
            self.age.value = 'Observation age: —'
            self.reason.value = ('Select a detected key below. Selection does not move the robot.'
                                 if projection else 'Start the camera and wait for fresh detections.')
            return
        self.name.value = target_name(selected[2])
        self.pixel.value = f"Camera centre: {target['pixel']} px (original image)"
        self.xy.value = (f"Robot XY estimate: {target['mm']} mm · unverified"
                         if target.get('mm') is not None else 'Robot XY estimate: unavailable · load a matching calibration')
        self.age.value = f"Observation age: {view['age_seconds']:.2f} s"
        if projection.get('experimental_recorded_test') and target.get('mm') is None and not view.get('calibration_error'):
            self.xy.value = 'Robot XY estimate: unavailable · ' + target.get('mapping_error', 'no eligible button inside measured SENSE bounds')
        notes = []
        if target['kind'] != 'button':
            notes.append('This is an information field or mode box, not a normal press button.')
        if 'active' in target and target['active'] is not True:
            notes.append('The detected control is inactive or its activity is uncertain.')
        if view.get('calibration_error'):
            notes.append('Calibration: ' + view['calibration_error'])
        notes.append('Move and click uses the latest valid target. Move without pressing remains optional.')
        self.reason.value = '\n'.join(notes)
