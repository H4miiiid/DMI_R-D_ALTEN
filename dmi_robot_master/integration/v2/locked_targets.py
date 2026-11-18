"""Detached Version 2 locked geometry checks; current proof remains independent.

VisionObserver retains locks, evidence history, freshness, worker requests and
projector ownership. These functions never renew evidence or issue commands.
"""
from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

import cv2
import numpy as np

from dmi_robot_master.integration.v2.policy import CONFIRMATION_SCREENS

if TYPE_CHECKING:
    from dmi_computer_vision.src.dmi.api import Observation


def is_confirmation(target: dict, screen: str) -> bool:
    """Only explicitly authorized right input-confirmation identities."""
    return (screen in CONFIRMATION_SCREENS and target.get('kind') == 'field'
            and target.get('display') == 'right' and target.get('label') == 'right/field/input')


def is_driver_confirmation(target: dict, screen: str) -> bool:
    """Preserve the original Driver-ID-only predicate for existing callers."""
    return screen == 'Driver ID' and is_confirmation(target, screen)


def inspection_result(result: dict, layout: dict) -> dict:
    """Build display-only static button geometry, with no direct evidence."""
    result = deepcopy(result)
    for side in ('left_display', 'right_display'):
        result[side]['buttons'] = {}
        result[side]['boxes'] = {}
        result[side]['data_field'] = None
        for path, region in layout['elements'].items():
            parts = path.split('/')
            if (side == 'right_display' and layout.get('screen') in CONFIRMATION_SCREENS
                    and parts == ['right_display', 'data_field']):
                result[side]['data_field'] = deepcopy(region)
            if len(parts) == 3 and parts[:2] == [side, 'buttons']:
                result[side]['buttons'][parts[2]] = deepcopy(region)
    return result


def validate_layout(layout: dict, sample: dict, *, enabled: bool) -> None:
    """Reject a changed lock generation/center; caller holds its condition lock."""
    region = layout.get('elements', {}).get(sample['locked_element'])
    if (not enabled or not layout.get('alignment_valid')
            or layout.get('screen') != sample['screen']
            or layout.get('generation') != sample['lock_generation'] or region is None
            or region['center'] != sample['target']['pixel']):
        raise ValueError('Locked target changed during the press request')


def locked_center(
    layout: dict, *, screen: str, observation: Observation, display: str,
    name: str, pixel: list[float], direct: dict[str, list[float]], tolerance: float,
    field: bool = False,
) -> list[float] | None:
    """Return a compatible locked center only with unique current button proof."""
    locked = None
    if (layout.get('screen') == screen and layout.get('alignment_valid')
            and layout.get('frame_size') == observation.frame_size):
        locked = layout.get('elements', {}).get(
            "right_display/data_field" if field else f"{display}_display/buttons/{name}")
    if locked is None:
        return None
    center = np.asarray(locked['center'], float)
    content = (observation.layout_evidence or {}).get(f"{display}_display", {})
    region = content.get('data_field') if field else content.get('buttons', {}).get(name)
    quad = np.asarray((region or {}).get('corners', []), np.float32)
    if (center.shape != (2,) or not np.isfinite(center).all()
            or np.max(np.abs(center-pixel)) > tolerance
            or quad.shape != (4, 2) or not np.isfinite(quad).all()
            or not cv2.isContourConvex(quad)
            or cv2.pointPolygonTest(quad, tuple(center), False) < 0
            or any(other != name and np.max(np.abs(center-point)) <= tolerance
                   for other, point in direct.items())):
        raise ValueError('Locked center lacks unique current measured button support')
    return center.tolist()
