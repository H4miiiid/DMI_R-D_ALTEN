"""Small fixed-step XY controls sharing the existing serialized robot owner."""
import flet as ft

from dmi_robot_master.integration.move_only import MOVE_CHECKS
from dmi_robot_master.integration.robot_session import MANUAL_STEP_MM


class ManualControls:
    def __init__(self, app):
        self.app = app
        self._epoch = None
        self.position = ft.Text('Controller XY: —', selectable=True)
        self.message = ft.Text('Connect and initialize the robot, then confirm readiness below.', size=12)
        self.ready = ft.Checkbox(label='Tool retracted; path clear; starting position and movement limits verified; physical stop available.',
                                 value=False, on_change=self.arm)
        self.buttons = {}
        for axis, direction in (('y', 1), ('x', -1), ('x', 1), ('y', -1)):
            async def move(e=None, axis=axis, direction=direction):
                await self.jog(axis, direction)
            sign = '+' if direction > 0 else '−'
            self.buttons[axis, direction] = ft.Button(f'{axis.upper()}{sign} · {MANUAL_STEP_MM} mm', on_click=move,
                                                     width=145, height=44, disabled=True)
        self.read = ft.TextButton('Read controller XY', on_click=self.read_position, disabled=True)
        self.control = ft.Column([
            ft.Text('Manual robot movement · 5 mm per click', size=17, weight=ft.FontWeight.W_600),
            ft.Text('Robot X/Y axes. Each click sends one step with Z=0 and no press. Camera and calibration are not required.', size=12),
            self.ready,
            ft.Row([self.buttons['y', 1]], alignment=ft.MainAxisAlignment.CENTER),
            ft.Row([self.buttons['x', -1], self.buttons['x', 1]], alignment=ft.MainAxisAlignment.CENTER),
            ft.Row([self.buttons['y', -1]], alignment=ft.MainAxisAlignment.CENTER),
            ft.Row([self.position, self.read], wrap=True), self.message,
            ft.Text('Controller XY is internally calculated, not an independent measurement. GUI Stop cannot interrupt a running motor command.', size=11),
        ], spacing=9)

    def arm(self, e=None):
        self.refresh()
        if not self.app.disposed:
            self.app.page.update(self.control)

    def refresh(self):
        app = self.app
        backend = app.runner.backend
        state = backend.session.status() if hasattr(backend, 'session') else {}
        epoch = state.get('origin_epoch')
        initialized = app.runner.initialized and state.get('homed') and state.get('connection') == 'connected'
        if epoch != self._epoch or not initialized:
            self._epoch = epoch
            self.ready.value = False
            self.position.value = 'Controller XY: —'
        available = bool(initialized and not state.get('legacy_xml_armed') and not app.locked)
        self.ready.disabled = self.read.disabled = not available
        for button in self.buttons.values():
            button.disabled = not available or self.ready.value is not True

    async def read_position(self, e=None):
        if self.app.locked or self.read.disabled:
            return
        self.app.ui_busy = True; self.app.refresh()
        try:
            result = await self.app.runner.read_position()
            self.position.value = f"Controller XY: {result['xy_mm']} mm"
        except Exception as exc:
            self.message.value = f'Position unavailable: {exc}'
        finally:
            self.app.ui_busy = False; self.app.refresh()

    async def jog(self, axis, direction):
        self.refresh()
        if self.app.locked or self.buttons[axis, direction].disabled:
            return
        self.app.ui_busy = True; self.app.refresh()
        self.message.value = f'Moving {axis.upper()} by {direction * MANUAL_STEP_MM:+d} mm…'
        self.app.page.update(self.message)
        try:
            result = await self.app.runner.jog(axis, direction, operator_confirmed=True,
                                              checks={key: True for key in MOVE_CHECKS})
            self.position.value = f"Controller XY: {result['xy_mm']} mm"
            prefix = 'SIMULATED · ' if result['simulation'] else ''
            self.message.value = f"{prefix}{result['response']} · requested XY {result['command_xy_mm']} mm · no press."
        except Exception as exc:
            self.message.value = f'Move blocked or not completed: {exc}'
        finally:
            self.app.ui_busy = False; self.app.refresh()
