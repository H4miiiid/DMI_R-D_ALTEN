"""Simulation-only, one-shot pressing and action-bound visual acknowledgement."""
from dataclasses import dataclass
import json
import math
import time

import numpy as np

from dmi_computer_vision.src.dmi.mode_observation import MODE_PAIRS
from dmi_robot_master.integration.move_only import (
    MOVE_CHECKS, MovePlan, _calibrated_candidate, _load, _prepare_target,
)

PRESS_CHECKS = MOVE_CHECKS + ('contact_sensing_checked','contact_routine_reviewed','move_only_alignment_reviewed')
SINGLE_PRESS_MS = 100
MODE_HOLD_MS = 5000
VERIFICATION_SECONDS = 4.


def _centers_match(observations: dict, expected: dict | None = None) -> bool:
    for box in ('box_14','box_16'):
        center = observations.get(box,{}).get('center')
        if (not isinstance(center,list) or len(center)!=2 or
                any(type(v) not in (int,float) or not math.isfinite(v) for v in center)):
            return False
        if expected is not None and max(abs(a-b) for a,b in zip(center,expected[box]['center'])) > 4:
            return False
    return True


def eligible_mode(sample: dict, expected_mode=None, expected_epoch=None, expected_centers=None) -> tuple[str,int]:
    target = sample['target']
    if (target['label'] != 'left/box/box_16' or target['kind'] != 'box' or target['display'] != 'left'):
        raise ValueError('The five-second hold requires the currently measured left box_16')
    modes = sample.get('modes',{})
    yellow, white = (modes.get('observations',{}).get(box,{}) for box in ('box_16','box_14'))
    mode, epoch = modes.get('mode'), modes.get('history_epoch')
    if (mode not in MODE_PAIRS or modes.get('state') != 'blinking' or
            yellow.get('status') != 'recognized' or yellow.get('mode') != mode or
            white.get('status') != 'recognized' or white.get('mode') != 'power' or
            modes.get('previous_blink_mode') != mode or modes.get('power_observed_at') is None or
            type(epoch) is not int or epoch < 0 or
            expected_mode is not None and mode != expected_mode or
            expected_epoch is not None and epoch != expected_epoch):
        raise ValueError('No current eligible blinking mode with direct power lineage; blink-off is insufficient')
    if (not _centers_match(modes.get('observations',{}),expected_centers) or
            max(abs(a-b) for a,b in zip(yellow['center'],target['pixel'])) > 4):
        raise ValueError('The selected box lacks matching current icon geometry')
    return mode, epoch


def _mode_candidate(document, sample, context, origin_epoch, mode, epoch, centers):
    xy = _calibrated_candidate(document,sample,context,origin_epoch)
    eligible_mode(sample,mode,epoch,centers)
    return xy


@dataclass(frozen=True)
class PressPlan:
    target: MovePlan
    kind: str
    mode: str | None = None
    history_epoch: int | None = None

    @property
    def token(self) -> str:
        return self.target.token

    @property
    def duration_ms(self) -> int:
        if self.kind == 'single_press' and self.mode is None and self.history_epoch is None:
            return SINGLE_PRESS_MS
        if self.kind == 'mode_hold' and self.mode in MODE_PAIRS and type(self.history_epoch) is int:
            return MODE_HOLD_MS
        raise ValueError('Unsupported immutable press/hold intent')

    def preview(self) -> dict:
        return {**self.target.preview(),'commissioning_only':False,'simulation_only':True,
            'hardware_press_enabled':False,'action_kind':self.kind,'mode_identity':self.mode,
            'history_epoch':self.history_epoch,'duration_ms':self.duration_ms}

    def resolve(self, observer, *, origin_epoch, limits, simulation, position=None):
        if simulation is not True:
            raise ValueError('Physical vision pressing is disabled pending independent hardware validation')
        self.duration_ms  # Validate intent kind and fixed duration before any packets.
        centers = json.loads(self.target.anchor_json).get('modes',{}).get('observations',{})
        resolver = (lambda d,s,c,o:_mode_candidate(d,s,c,o,self.mode,self.history_epoch,centers)) if self.kind=='mode_hold' else None
        return self.target.resolve(observer,origin_epoch=origin_epoch,limits=limits,
            simulation=True,position=position,_resolve_target=resolver)


def prepare_press(observer, selection, envelope_path, *, kind: str,
                  origin_epoch: str, limits: tuple[int,int], simulation: bool) -> PressPlan:
    if simulation is not True:
        raise ValueError('Physical vision pressing is disabled pending independent hardware validation')
    mode = epoch = None
    resolver = None
    if kind == 'mode_hold':
        sample = observer.calibration_sample(*selection)
        mode,epoch = eligible_mode(sample)
        centers = sample['modes']['observations']
        resolver = lambda d,s,c,o:_mode_candidate(d,s,c,o,mode,epoch,centers)
    elif kind != 'single_press':
        raise ValueError('Select one single press or one five-second mode hold')
    target = _prepare_target(observer,selection,envelope_path,origin_epoch=origin_epoch,
        limits=limits,simulation=True,_resolve_target=resolver)
    return PressPlan(target,kind,mode,epoch)


class HoldVerification:
    """Post-DONE evidence only; a camera transition never proves physical contact."""
    def __init__(self, plan: PressPlan, done_at: float, *, clock=time.monotonic):
        if plan.kind != 'mode_hold':
            raise ValueError('Visual mode verification requires a hold intent')
        self.plan, self.done_at = plan, done_at
        self.clock = clock
        self.anchor = json.loads(plan.target.anchor_json)
        self.samples = []
        self.last_capture = -1

    def poll(self, observer) -> dict | None:
        try:
            current = observer.action_observation()
        except (ValueError,RuntimeError) as exc:
            return {'ui_outcome':'unconfirmed','verification_reason':str(exc)}
        if (current['session_id'] != self.plan.target.selection[0] or
                current['source_info'] != self.anchor['source_info'] or
                current['frame_size'] != self.anchor['frame_size'] or
                current.get('calibration_id') != self.plan.target.calibration_id or
                current.get('calibration_error') is not None or any(
                    np.max(np.abs(np.array(current['geometry'][s])-self.anchor['geometry'][s])) > 4
                    for s in ('left','right'))):
            return {'ui_outcome':'unconfirmed','verification_reason':'Source, calibration or geometry changed'}
        modes = current.get('modes',{})
        if modes.get('history_epoch') != self.plan.history_epoch:
            return {'ui_outcome':'unconfirmed','verification_reason':'Mode evidence history was invalidated'}
        received, upstream = current['received_at'], current['upstream_age_seconds']
        age = self.clock()-received+upstream
        if not 0 <= age <= 1.5:
            return {'ui_outcome':'unconfirmed','verification_reason':'Feedback is stale'}
        # A newly delivered buffered frame may still predate command completion.
        if received-upstream <= self.done_at or current['capture_index'] <= self.last_capture:
            return None
        self.last_capture = current['capture_index']
        observations = modes.get('observations',{})
        if not _centers_match(observations,self.anchor['modes']['observations']):
            return {'ui_outcome':'unconfirmed','verification_reason':'Measured mode boxes moved or disappeared'}
        white, yellow = (observations.get(k,{}) for k in ('box_14','box_16'))
        if any(v.get('status') not in ('recognized','empty') for v in (white,yellow)):
            return {'ui_outcome':'unconfirmed','verification_reason':'Boxes are missing or ambiguous'}
        if (white.get('mode') not in ('power',self.plan.mode,None) or
                yellow.get('mode') not in (self.plan.mode,None)):
            return {'ui_outcome':'unconfirmed','verification_reason':'A different mode was observed'}
        if (white.get('status')=='recognized' and white.get('mode')==self.plan.mode and
                yellow.get('status')=='empty' and yellow.get('mode') is None):
            self.samples.append((received,current['capture_index']))
            if len(self.samples)>3:
                self.samples = [self.samples[0],*self.samples[-2:]]
        else:
            self.samples.clear()  # Blink-off while power remains is never success.
        if (len(self.samples)>=3 and received-self.samples[0][0]>=.8 and
                modes.get('state')=='steady' and modes.get('mode')==self.plan.mode and
                modes.get('previous_blink_mode')==self.plan.mode and modes.get('replacement_verified') is True):
            if (_load(self.plan.target.calibration_path)[1] != self.plan.target.calibration_sha256 or
                    _load(self.plan.target.envelope_path)[1] != self.plan.target.envelope_sha256):
                return {'ui_outcome':'unconfirmed','verification_reason':'Configuration changed after dispatch'}
            try:
                latest = observer.action_observation()
            except (ValueError,RuntimeError) as exc:
                return {'ui_outcome':'unconfirmed','verification_reason':str(exc)}
            if latest != current:
                return None  # Re-evaluate a newer frame rather than certify an old one.
            if not 0 <= self.clock()-received+upstream <= 1.5:
                return {'ui_outcome':'unconfirmed','verification_reason':'Feedback expired during final configuration checks'}
            return {'ui_outcome':'observed_mode_transition','verification_reason':'Same mode steady in box_14; box_16 empty',
                'verification_frames':[sample[1] for sample in self.samples],
                'verification_span_seconds':received-self.samples[0][0]}
        return None
