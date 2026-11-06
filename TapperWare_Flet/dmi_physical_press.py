"""One-click experimental requests and confirmed ordinary live-camera presses."""
import flet as ft
from dmi_target import format_pixels, experimental_selection


class PhysicalPressControls:
    def __init__(self, app):
        self.app = app
        self._view = None
        self.message = ft.Text('Select a detected button, review its coordinates and confirm one short press.', size=12)
        self.control = self.message

    def reset(self):
        self.message.value = 'Select a detected button, review its coordinates and confirm one short press.'

    def update(self, view):
        self._view = view
        self.refresh()

    def refresh(self):
        app = self.app
        backend = app.runner.backend
        status = backend.session.status() if hasattr(backend, 'session') else {}
        selected = app._vision_selection_key
        view = self._view or {}
        projection = view.get('projection') or {}
        experimental = (projection.get('experimental_recorded_test') is True
                        or experimental_selection(view, selected))
        target = projection.get('targets', {}).get(selected[2]) if selected else None
        eligible = (not app.is_demo and app.runner.initialized and status.get('homed')
                    and status.get('connection') == 'connected' and not status.get('legacy_xml_armed')
                    and view.get('fresh') and selected
                    and selected[:2] == (view.get('session_id'), projection.get('screen'))
                    and not view.get('calibration_error') and target
                    and target['kind'] == 'button'
                    and target['display'] in (('left', 'right') if experimental else ('right',))
                    and target.get('mm') is not None and target.get('active', True) is True)
        if experimental:
            # Availability is independent of individual missed detections. The
            # backend still checks direct evidence, mapping and limits on click.
            eligible = (not app.is_demo and app.runner.initialized and status.get('homed')
                        and status.get('connection') == 'connected' and not status.get('legacy_xml_armed')
                        and experimental_selection(view, selected))
        app.target_ui.hardware_press.disabled = bool(app.locked or not eligible or (not experimental and not app.move_ui.envelope.value))
        if not app.is_demo:
            app.target_ui.hardware_press.content = ('Experimental move and click · 100 ms' if experimental else 'Move and click selected key · 100 ms')
        if eligible and experimental:
            app.target_ui.reason.value = ('One click requests one experimental press using the latest direct coordinates '
                '(at most two missed updates / 1.5 s old). Clicking confirms the tool and return path are clear and the physical stop is ready. No second dialog.')
            if view.get('calibration_error'):
                app.target_ui.reason.value = 'Mapping currently blocked: ' + view['calibration_error']
        elif eligible:
            app.target_ui.reason.value = ('Review and confirm one short press. Current detection, calibration and limits are checked before sending.'
                if app.move_ui.envelope.value else 'Set the existing movement limits under Movement limits and optional move-only test below; no move-only test is required.')
        elif selected and not app.is_demo:
            if not app.runner.initialized or not status.get('homed'):
                app.target_ui.reason.value = 'Connect and initialize the robot first; camera detection alone does not initialize it.'
            elif view.get('calibration_error'):
                app.target_ui.reason.value = 'Mapping blocked: ' + view['calibration_error']

    async def request(self, e=None):
        app = self.app
        self.refresh()
        if app.locked or app.is_demo or not app._vision_selection_key or app.target_ui.hardware_press.disabled:
            return
        app.ui_busy = True; app.refresh()
        experimental = experimental_selection(self._view, app._vision_selection_key)
        from dmi_robot_master.integration.physical_press import PHYSICAL_PRESS_CHECKS
        try:
            preview = await app.runner.prepare_press(app.vision.observer, app._vision_selection_key,
                app.move_ui.envelope.value, kind='single_press', experimental_one_click=experimental)
            if experimental:
                result = await app.runner.confirm_press(preview['token'], operator_confirmed=True,
                    checks={key: True for key in PHYSICAL_PRESS_CHECKS})
                self.message.value = f"{result['response']} · inspect the DMI to check the result."
                app.log('Physical press', str(result))
                return
        except Exception as exc:
            self.message.value = f'Press not completed: {exc}'
            app.log('Physical press', str(exc)); return
        finally:
            app.ui_busy = False; app.refresh()
        bounds = preview['independent_envelope']
        experimental = preview.get('experimental_recorded_test') is True
        details = ft.Text(f"{preview['selection'][1:]} · camera centre {format_pixels(preview['pixel'])} px\n"
            f"Robot XY {preview['command_xy_mm']} mm · one 100 ms press\n"
            f"Movement limits {bounds['minimum_xy_mm']} → {bounds['maximum_xy_mm']} mm; "
            f"maximum move {bounds['maximum_move_mm']} mm\n"
            f"Calibration sample maximum error: {preview['numerical_max_error_mm']:.3f} mm\n"
            'Latest coordinates are rechecked before sending. A changed or stale target blocks the press. '
            'After contact and Z retraction, the robot returns to home (0, 0) before completing. '
            'No automatic retry. Inspect the DMI result yourself.', size=12)
        if experimental:
            details.value = ('EXPERIMENTAL: the same homography is used across both SENSE regions. Accuracy outside tested keys is unverified; '
                f"recorded error {preview['numerical_max_error_mm']:.2f} mm exceeded the earlier 3 mm limit and does not bound full-monitor error.\n" + details.value)
        readiness = ft.Text('Before confirming: tool retracted; path and contact area clear; '
            'starting position, movement limits and the return path to (0, 0) verified; physical stop available; '
            'contact sensor, retraction and 100 ms contact routine checked. GUI Stop cannot interrupt motors.', size=12)
        confirmed = ft.Checkbox(label=('I accept the experimental accuracy and confirm readiness for this one test press.'
            if experimental else 'I confirm these readiness checks for this one press.'), value=False)
        notice = ft.Text('No preceding move-only test or alignment form is required.', size=12)
        def cancel(e=None):
            app.runner.discard_move(); app.page.pop_dialog()
        async def confirm(e=None):
            if confirmed.value is not True:
                notice.value = 'Confirm the readiness checks before sending.'; app.page.update(notice); return
            app.page.pop_dialog()
            if app.locked:
                app.runner.discard_move(); return
            app.ui_busy = True; app.refresh()
            try:
                result = await app.runner.confirm_press(preview['token'], operator_confirmed=True,
                    checks={key: True for key in PHYSICAL_PRESS_CHECKS})
                self.message.value = f"{result['response']} · inspect the DMI to check the result."
                app.log('Physical press', str(result))
            except Exception as exc:
                self.message.value = f'Press not completed: {exc}'; app.log('Physical press', str(exc))
            finally:
                app.ui_busy = False; app.refresh()
        app.page.show_dialog(ft.AlertDialog(modal=True, title=ft.Text('Confirm one short press'),
            content=ft.Column([details, readiness, confirmed, notice], tight=True, scroll=ft.ScrollMode.AUTO),
            actions=[ft.TextButton('Cancel', on_click=cancel), ft.TextButton('Press once · 100 ms', on_click=confirm)]))
