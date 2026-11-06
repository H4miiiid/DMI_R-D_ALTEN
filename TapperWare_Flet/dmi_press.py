"""One explicitly confirmed simulated press/hold; physical pressing is locked."""
import flet as ft
from dmi_target import format_pixels, format_mm


class PressControls:
    def __init__(self, app):
        self.app = app
        self.intent = None
        self._view = {}
        self.enabled = ft.Checkbox(label='Abilita prove di pressione solo simulate',value=False,on_change=self.changed)
        self.message = ft.Text('Pressione fisica bloccata: calibrazione, allineamento e hardware non verificati.',size=12)
        self.single = ft.Button('Simula una pressione · 100 ms',on_click=self.single_press,disabled=True)
        self.hold = ft.Button('Simula hold box 16 · 5 s',on_click=self.mode_hold,disabled=True)
        self.control = ft.Column([self.enabled,ft.Text('Usa il JSON limiti indipendenti indicato sopra. '
            'Una sola azione per conferma; nessun retry o sequenza automatica.',size=11),
            ft.Row([self.single,self.hold],wrap=True),self.message],spacing=8)

    def changed(self,e=None):
        self.app.runner.discard_move();self.intent = None
        self.refresh()
        if not self.app.disposed:self.app.page.update(self.control)

    def reset(self):
        self.enabled.value = False
        self.changed()

    def update(self, view):
        self._view = view
        selected = self.app._vision_selection_key
        projection = view.get('projection')
        valid = (view.get('fresh') and selected and projection and
            selected[:2]==(view['session_id'],projection['screen']) and selected[2] in projection['targets'])
        if self.intent and (not valid or self.intent['action_kind']=='mode_hold' and (
                view.get('modes',{}).get('history_epoch') != self.intent['history_epoch'] or
                view.get('modes',{}).get('mode') != self.intent['mode_identity'])):
            self.app.runner.discard_move();self.intent = None
            self.message.value = 'Conferma invalidata: sorgente, selezione o storia modalità cambiata.'
        self.refresh()

    def refresh(self):
        from dmi_runtime import RealBackend
        selected = self.app._vision_selection_key
        view = self._view
        target = (view.get('projection') or {}).get('targets',{}).get(selected[2]) if selected else None
        simulated = isinstance(self.app.runner.backend,RealBackend) and self.app.runner.backend.session.simulation is True
        ready = (not self.app.locked and self.enabled.value and simulated and self.app.runner.initialized
            and self.app.move_ui.envelope.value and view.get('fresh') and target is not None)
        self.enabled.disabled = self.app.locked
        self.single.disabled = not (ready and target['kind']=='button' and target['display']=='right'
            and ('active' not in target or target['active'] is True))
        self.hold.disabled = not (ready and selected[2]=='left/box/box_16' and
            view.get('modes',{}).get('state')=='blinking')

    async def single_press(self,e=None):
        await self.request('single_press')

    async def mode_hold(self,e=None):
        await self.request('mode_hold')

    async def request(self,kind):
        from dmi_robot_master.integration.pressing import PRESS_CHECKS
        if self.app.locked or not self.enabled.value or not self.app._vision_selection_key:return
        backend = self.app.runner.backend
        if not hasattr(backend, 'session') or backend.session.simulation is not True:
            self.message.value = 'Physical vision pressing is disabled in simulation controls; use the separate physical commissioning flow.'
            self.app.log('Pressione', self.message.value)
            return
        self.app.ui_busy = True;self.app.refresh()
        try:
            intent = await self.app.runner.prepare_press(self.app.vision.observer,self.app._vision_selection_key,
                self.app.move_ui.envelope.value,kind=kind)
            self.intent = intent
        except Exception as exc:
            self.message.value = f'Pressione bloccata: {exc}'
            self.app.log('Pressione',str(exc));return
        finally:
            self.app.ui_busy = False;self.app.refresh()
        labels = ('Utensile retratto nel modello di prova; nessuna dichiarazione hardware',
            'Traiettoria sgombra nel modello di prova','Posizione iniziale dentro i limiti del modello di prova',
            'Arresto previsto nel modello; Stop GUI non interrompe un motore reale',
            'Limiti del modello dichiarati indipendentemente dalla calibrazione',
            'Contatto/sensori verificati nel modello di prova',
            'Routine di contatto revisionata nel modello di prova','Allineamento move-only verificato nel modello di prova')
        checks = [ft.Checkbox(label=text,value=False) for text in labels]
        notice = ft.Text('Solo trasporto simulato. Queste dichiarazioni non abilitano hardware fisico.',size=12)
        bounds = intent['independent_envelope']
        details = (f"{intent['selection'][1:]} · px {format_pixels(intent['pixel'])}\n"
            f"XY stimato {format_mm(intent['predicted_xy_mm'])} mm · comando {intent['command_xy_mm']}\n"
            f"MOVE_AND_CLICK · {intent['duration_ms']} ms · modalità {intent['mode_identity'] or 'pulsante'}\n"
            f"Limiti {bounds['minimum_xy_mm']} → {bounds['maximum_xy_mm']} mm; distanza ≤{bounds['maximum_move_mm']} mm\n"
            'Calibrazione non verificata fisicamente. DONE non prova contatto o conferma DMI.')
        def cancel(e=None):
            self.app.runner.discard_move();self.intent = None;self.app.page.pop_dialog()
        async def confirm(e=None):
            if any(c.value is not True for c in checks):
                notice.value = 'Completare tutti i controlli per questa singola prova.'
                self.app.page.update(notice);return
            self.app.page.pop_dialog()
            if self.app.locked or self.intent is not intent:
                self.app.runner.discard_move();return
            self.intent = None;self.app.ui_busy = True;self.app.refresh()
            self.message.value = 'Prova simulata in corso; rilevamento attivo. Nessun retry.'
            try:
                result = await self.app.runner.confirm_press(intent['token'],operator_confirmed=True,
                    checks=dict(zip(PRESS_CHECKS,(c.value for c in checks))))
                self.message.value = f"SIMULATO · {result['response']} · {result['ui_outcome']} · " + result.get('verification_reason','nessuna conferma visiva richiesta')
            except Exception as exc:
                self.message.value = f'Prova non completata: {exc}';self.app.log('Errore',str(exc))
            finally:
                self.app.ui_busy = False;self.app.refresh()
        self.app.page.show_dialog(ft.AlertDialog(modal=True,title=ft.Text('Conferma una sola azione SIMULATA'),
            content=ft.Column([ft.Text(details,size=12),*checks,notice],tight=True,scroll=ft.ScrollMode.AUTO),
            actions=[ft.TextButton('Annulla',on_click=cancel),ft.TextButton('Conferma prova simulata',on_click=confirm)]))
