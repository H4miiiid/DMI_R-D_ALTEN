"""Operator confirmation for one bounded commissioning move, without pressing."""
import flet as ft

CHECK_LABELS = ('Utensile verificato fisicamente retratto; Z richiesto = 0',
                'Traiettoria sgombra e area di lavoro controllata',
                'Posizione iniziale verificata dentro i limiti indipendenti',
                'Arresto fisico disponibile; Stop GUI non interrompe il motore',
                'Limiti e distanza misurati indipendentemente dalla calibrazione')


class MoveControls:
    def __init__(self, app):
        self.app = app
        self.enabled = ft.Checkbox(label='Commissioning: solo allineamento con limiti indipendenti',
                                   value=False,on_change=self.changed)
        self.envelope = ft.TextField(label='JSON limiti commissioning indipendenti',on_change=self.changed)
        self.message = ft.Text('Movimento normale non pronto: calibrazione non verificata. Nessuna pressione.',size=12)
        self.prepare = ft.Button('Verifica e prepara un movimento',on_click=self.request,disabled=True)
        self.control = ft.Column([self.enabled,self.envelope,self.message,self.prepare],spacing=8)
        self.intent = None
        self._view = None

    def changed(self, e=None):
        self.app.runner.discard_move()
        self.intent = None
        self.message.value = 'Movimento normale non pronto. Preparare e confermare ogni movimento commissioning.'
        self.refresh()
        if not self.app.disposed:self.app.page.update(self.control)

    def reset(self):
        self.enabled.value = False
        self.changed()

    def update(self, view):
        self._view = view
        selected = self.app._vision_selection_key
        projection = view.get('projection')
        target = projection['targets'].get(selected[2]) if projection and selected else None
        if (not view.get('fresh') or not selected or not projection or
                selected[:2] != (view['session_id'],projection['screen']) or
                target is None or target['kind']!='button' or target['display']!='right' or
                ('active' in target and target['active'] is not True)):
            if self.intent is not None:
                self.app.runner.discard_move();self.intent = None
                self.message.value = 'Conferma invalidata: selezione/sorgente non attuale.'
        self.refresh()

    def refresh(self):
        self.enabled.disabled = self.envelope.disabled = self.app.locked
        selected = self.app._vision_selection_key
        view = self._view or {}
        target = (view.get('projection') or {}).get('targets',{}).get(selected[2]) if selected else None
        eligible = target and target['kind']=='button' and target['display']=='right' and (
            'active' not in target or target['active'] is True)
        self.prepare.disabled = bool(self.app.locked or not self.enabled.value or not self.envelope.value
            or not self.app.runner.initialized or not view.get('fresh') or not eligible)

    async def request(self,e=None):
        from dmi_robot_master.integration.move_only import MOVE_CHECKS
        if self.app.locked or not self.enabled.value or not self.app._vision_selection_key:
            return
        self.app.ui_busy = True;self.app.refresh()
        try:
            observer = self.app.vision.observer
            intent = await self.app.runner.prepare_move(observer,self.app._vision_selection_key,self.envelope.value)
            self.intent = intent
        except Exception as exc:
            self.message.value = f'Movimento bloccato: {exc}'
            self.app.log('Movimento',str(exc))
            return
        finally:
            self.app.ui_busy = False;self.app.refresh()
        bounds = intent['independent_envelope']
        checks = [ft.Checkbox(label=text,value=False) for text in CHECK_LABELS]
        notice = ft.Text('Conferma valida per 30 s; evidenza diretta ricontrollata entro 1,5 s al comando.',size=12)
        details = (f"{intent['selection'][1:]} · px {intent['pixel']}\n"
            f"XY previsto {intent['predicted_xy_mm']} mm · comando {intent['command_xy_mm']} · Z=0\n"
            f"Limiti {bounds['minimum_xy_mm']} → {bounds['maximum_xy_mm']} mm; "
            f"distanza massima {bounds['maximum_move_mm']} mm\n{bounds['measurement_basis']}\n"
            f"Modello {intent['calibration_id'][:12]}: errore numerico massimo "
            f"{intent['numerical_max_error_mm']:.3f} mm; NON verificato fisicamente.\n"
            'Commissioning soltanto. Nessuna pressione o prova di allineamento.')
        def cancel(e=None):
            self.app.runner.discard_move();self.intent = None
            self.app.page.pop_dialog()
        async def confirm(e=None):
            if any(c.value is not True for c in checks):
                notice.value = 'Completare tutti i controlli prima di confermare.'
                self.app.page.update(notice);return
            self.app.page.pop_dialog()
            if self.app.locked or self.intent is not intent:
                self.app.runner.discard_move();return
            self.intent = None
            self.app.ui_busy = True;self.app.refresh()
            try:
                result = await self.app.runner.confirm_move(intent['token'],operator_confirmed=True,
                    checks=dict(zip(MOVE_CHECKS,(c.value for c in checks))))
                self.message.value = (f"{'SIMULATO · ' if result['simulation'] else ''}"
                    f"{result['response']} · MOVE {result['command_xy_mm']}, Z=0. "
                    'Allineamento fisico non verificato; nessuna pressione.')
            except Exception as exc:
                self.message.value = f'Movimento non completato: {exc}'
                self.app.log('Errore',str(exc))
            finally:
                self.app.ui_busy = False;self.app.refresh()
        self.app.page.show_dialog(ft.AlertDialog(modal=True,title=ft.Text('Conferma un solo movimento commissioning'),
            content=ft.Column([ft.Text(details,size=12),*checks,notice],tight=True,scroll=ft.ScrollMode.AUTO),
            actions=[ft.TextButton('Annulla',on_click=cancel),ft.TextButton('Conferma MOVE, Z=0',on_click=confirm)]))
