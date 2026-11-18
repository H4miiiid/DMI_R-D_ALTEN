"""Operator-authorized fixed-setup snapshot; never represented as fresh evidence."""
from copy import deepcopy
from uuid import uuid4

from dmi_robot_master.integration.v2.screen_lock import ScreenLock
from dmi_robot_master.integration.v2.locked_targets import inspection_result, is_confirmation


class FrozenScreen:
    """One completed lock's content, retained until action or context invalidation."""

    def __init__(self, observation, layout: dict, context: tuple, modes: dict, history=()):
        self.token = uuid4().hex
        self.observation = observation
        self.context = deepcopy(context)
        self.modes = deepcopy(modes)
        self.result = ScreenLock.measured_display(observation.result, observation.layout_evidence,
                                                 layout=layout, frame_size=observation.frame_size)
        # A completed geometry lock can outlive a same-pass recognition miss.
        # Retain semantic content only from the owner's bounded compatible full
        # observations, never from a profile or a button's nominal location.
        for path in layout['elements']:
            parts = path.split('/')
            if len(parts) != 3 or parts[1] != 'buttons':
                continue
            side, _, name = parts
            if name in self.result[side].get('buttons', {}):
                continue
            for previous in reversed(tuple(history)[-3:]):
                if (previous.session_id != observation.session_id or previous.source_id != observation.source_id
                        or previous.frame_size != observation.frame_size
                        or previous.result['right_display']['state'] != layout['screen']):
                    continue
                region = previous.result[side].get('buttons', {}).get(name)
                if region is not None:
                    self.result[side].setdefault('buttons', {})[name] = deepcopy(region)
                    break
        ScreenLock.apply_display(self.result, layout)
        self.fields = {}  # Filled from the existing same-pass OCR output by the owner.

    def targets_result(self, layout: dict) -> dict:
        result = inspection_result(self.result, layout)
        for side in ('left_display', 'right_display'):
            for name, region in result[side]['buttons'].items():
                original = self.result[side].get('buttons', {}).get(name)
                if original is None:
                    region['active'] = None
                elif 'active' in original:
                    region['active'] = original['active']
                else:
                    region.pop('active', None)
        return result

    def element(self, target: dict, screen: str, layout: dict) -> str:
        if target.get('active', True) is not True:
            raise ValueError('Selected locked control is inactive or uncertain')
        if is_confirmation(target, screen):
            path = 'right_display/data_field'
        elif target['kind'] == 'button':
            name = ('digit_' + target['label'][4:] if target['label'].startswith('KEY_')
                    else target['label'].rsplit('/', 1)[-1])
            path = f"{target['display']}_display/buttons/{name}"
        else:
            raise ValueError('Selected locked item is not an authorized press control')
        if path not in layout['elements']:
            raise ValueError('Selected control has no confirmed locked geometry')
        return path
