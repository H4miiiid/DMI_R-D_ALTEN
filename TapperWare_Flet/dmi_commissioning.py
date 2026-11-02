"""Flet forms for shared communication and operator-measured calibration."""
from pathlib import Path
import asyncio

import flet as ft


class ConnectionControls:
    def __init__(self, app):
        self.app = app
        self.config = ft.TextField(label='Configurazione robot JSON (esplicita in hardware)', text_size=12)
        self.status = ft.Text('Disconnesso · nessuna prontezza fisica verificata', size=12, selectable=True)
        self.buttons = [ft.TextButton(text, on_click=callback) for text,callback in (
            ('Connetti / ACK', self.connect), ('Controlla ACK', self.ping),
            ('Leggi XY controller', self.position), ('Disconnetti', self.disconnect))]
        self.control = ft.Column([ft.Text('Comunicazione robot', size=16), self.config,
            ft.Row(self.buttons,wrap=True), self.status,
            ft.Text('ACK verifica solo la comunicazione. XY controller non è una misura indipendente. '
                    'XML legacy usa coordinate statiche e conferma separata, solo a visione ferma. '
                    'Movimento normale/pressione da target visivi non pronti; commissioning richiede limiti indipendenti.',size=11)],spacing=10)

    async def _run(self, operation):
        if self.app.locked:
            return
        self.app.ui_busy = True
        self.app.refresh()
        try:
            return await operation()
        except Exception as exc:
            self.app.error(str(exc))
        finally:
            self.app.ui_busy = False
            self.app.refresh()

    async def connect(self,e=None):
        await self._run(lambda:self.app.runner.connect(self.config.value.strip() or None))

    async def ping(self,e=None):
        await self._run(self.app.runner.check_connection)

    async def disconnect(self,e=None):
        await self._run(self.app.runner.disconnect)

    async def position(self,e=None):
        async def read():
            value = await self.app.runner.read_position()
            self.app.log('XY controller', f"{value['xy_mm']} mm · {'SIMULATO' if value['simulation'] else 'calcolato internamente'} · non indipendente")
        await self._run(read)

    def refresh(self):
        for control in [self.config,*self.buttons]:
            control.disabled = self.app.locked
        backend = self.app.runner.backend
        if backend is not None and hasattr(backend,'session'):
            status = backend.session.status()
            connected = status['connection']=='connected'
            self.config.disabled = self.app.locked or connected
            self.buttons[0].disabled = self.app.locked or connected
            self.buttons[1].disabled = self.buttons[2].disabled = self.app.locked or not connected
            self.status.value = (f"{'SIMULATO' if status['simulation'] else 'UDP'} · {status['connection']} · "
                f"risposta {status['response']} · homing controller={status['homed']} · target visivi pronti=False")
            age=status['last_response_age_seconds']
            if age is not None:
                self.status.value += f' · età ultima risposta {age:.1f} s (nessuna garanzia continua)'
        else:
            self.status.value = 'Disconnesso · nessuna prontezza fisica verificata'
            self.buttons[1].disabled = self.buttons[2].disabled = self.buttons[3].disabled = True


class CalibrationControls:
    def __init__(self, app):
        self.app = app
        self.target = ft.Dropdown(label='Centro attuale da misurare', options=[],on_select=self.measurement_changed)
        self._identity = None
        self.x = ft.TextField(label='X assoluta misurata (mm)', width=180,on_change=self.measurement_changed)
        self.y = ft.TextField(label='Y assoluta misurata (mm)', width=180,on_change=self.measurement_changed)
        self.role = ft.Dropdown(label='Ruolo indipendente',value='fit',options=[
            ft.DropdownOption('fit','Punto di fit'),ft.DropdownOption('check','Controllo tenuto fuori dal fit')])
        self.confirm = ft.Checkbox(label='Confermo centro visibile e XY misurati indipendentemente, offset pannello/tool inclusi',value=False)
        self.tolerance = ft.TextField(label='Tolleranza numerica mm (non approvazione fisica)',value='3')
        self.basis = ft.TextField(label='Motivo della tolleranza',value='Limite provvisorio 3 mm; non verifica fisica')
        root = Path(__file__).resolve().parent.parent
        self.output = ft.TextField(label='File candidato durevole (nuovo nome, nessuna sovrascrittura)',
            value=str(root/'dmi_robot_config/local/sense-guided-candidate.json'),text_size=12)
        self.message = ft.Text('Usare il contesto camera/origine indipendente sopra. Almeno 5 punti fit + 1 controllo.',size=12,selectable=True)
        self.rows = ft.Column(height=170,scroll=ft.ScrollMode.AUTO,spacing=4)
        self.buttons = [ft.TextButton(text,on_click=callback) for text,callback in (
            ('Nuova raccolta',self.start),('Aggiungi misura',self.collect),('Confronta fit / residui',self.fit),
            ('Salva candidato',self.save))]
        self.control = ft.Column([ft.Text('Calibrazione guidata SENSE · nessun movimento',size=16),
            ft.Text('XY inserite a mano sono misure dichiarate dall’operatore, mai coordinate previste dal fit. '
                    'Non si applica un altro offset Y della GUI.',size=11),
            ft.Row(self.buttons,wrap=True),self.target,ft.Row([self.x,self.y],wrap=True),self.role,self.confirm,
            self.tolerance,self.basis,self.output,self.message,self.rows],spacing=10)

    async def _run(self, operation):
        if self.app.locked:
            return
        self.app.ui_busy = True
        self.app.refresh()
        try:
            await operation()
        except Exception as exc:
            self.message.value = f'Operazione non completata: {exc}'
            self.app.error(str(exc))
        finally:
            self.app.ui_busy = False
            self.render()
            self.app.refresh()

    async def start(self,e=None):
        async def run():
            if not self.app.vision.observer or not self.app.vision.observer.snapshot()['fresh']:
                raise ValueError('Avviare prima una sorgente SENSE con osservazione fresca')
            await asyncio.to_thread(self.app.calibration.start,self.app.vision_context.value.strip(),self.app.runner.origin_epoch)
            backend = self.app.runner.backend
            if backend is not None and hasattr(backend,'session') and not backend.session.simulation:
                if self.app.calibration.draft.context['xy_limits_mm'] != list(backend.session.settings.xy_limits_mm):
                    self.app.calibration.invalidate()
                    raise ValueError('Limiti XY di robot e contesto calibrazione non coincidono')
            self.message.value = 'Raccolta nuova · selezionare un centro e inserire XY indipendenti'
        await self._run(run)

    async def collect(self,e=None):
        async def run():
            if not self.confirm.value or self._identity is None or not self.target.value:
                raise ValueError('Selezionare un centro fresco e confermare la misura indipendente')
            selected = (*self._identity,self.target.value)
            await asyncio.to_thread(self.app.calibration.collect,self.app.vision.observer,selected,
                [float(self.x.value),float(self.y.value)],self.role.value,self.app.runner.origin_epoch)
            self.confirm.value = False
            self.x.value = self.y.value = ''
            self.message.value = 'Misura aggiunta; il precedente fit è invalidato'
        await self._run(run)

    async def fit(self,e=None):
        async def run():
            draft = self.app.calibration.draft
            if draft is None:
                raise ValueError('Avviare una raccolta prima del fit')
            result = await asyncio.to_thread(draft.fit,tolerance_mm=float(self.tolerance.value),tolerance_basis=self.basis.value)
            if draft is not self.app.calibration.draft:
                raise ValueError('Contesto cambiato durante il fit')
            selection = result['selected_model'] or 'nessun modello entro tolleranza'
            self.message.value = f'Candidato non verificato · {selection} · azioni disabilitate'
        await self._run(run)

    async def save(self,e=None):
        async def run():
            draft = self.app.calibration.draft
            if draft is None:
                raise ValueError('Nessun candidato da salvare')
            await asyncio.to_thread(draft.save,self.output.value)
            self.message.value = 'Candidato salvato, non verificato. Per ispezionarlo, ricaricare il file in una nuova osservazione con contesto compatibile.'
        await self._run(run)

    def reset(self):
        self.app.calibration.invalidate()
        self.confirm.value = False
        self._identity = None
        self.target.value = None
        self.target.options = []
        self.rows.controls.clear()
        self.message.value = 'Raccolta invalidata dal cambio sorgente/pannello/ambiente/origine'

    def update_targets(self,view):
        projection = view['projection']
        identity = (view['session_id'],projection['screen']) if projection else None
        if identity != self._identity:
            self.target.value = None
            self.confirm.value = False
        self._identity = identity
        targets = {k:v for k,v in projection['targets'].items() if v['kind'] in ('button','field')} if projection else {}
        self.target.options = [ft.DropdownOption(k,f"{k} · px {v['pixel']}") for k,v in targets.items()]
        if self.target.value not in targets:
            self.target.value = None
            self.confirm.value = False

    def measurement_changed(self,e=None):
        self.confirm.value = False
        if not self.app.disposed:
            self.app.page.update(self.confirm)

    def refresh(self):
        for control in [self.target,self.x,self.y,self.role,self.confirm,self.tolerance,self.basis,self.output,*self.buttons]:
            control.disabled = self.app.locked

    def render(self):
        self.rows.controls.clear()
        draft = self.app.calibration.draft
        if draft is None:
            return
        document = draft.document
        if document is None:
            self.message.value = f'Raccolta {len(draft.points())} punti · nessun fit corrente · azioni disabilitate'
        for index,point in enumerate(draft.points()):
            key = str(tuple(point[k] for k in ('screen','display','kind','label')))
            text = f"{point['role']} · {point['screen']} / {point['label']} · px {point['pixel']} → {point['mm']} mm"
            if document:
                for name,model in document['models'].items():
                    errors = model['leave_one_control_out_mm'] if point['role']=='fit' else model['held_out_control_error_mm']
                    text += f" · {name} indipendente={errors[key]:.3f} mm"
            def remove(e,index=index):
                if self.app.locked or self.app.calibration.draft is not draft:
                    return
                draft.remove(index)
                self.render()
                self.app.refresh()
            self.rows.controls.append(ft.Row([ft.Text(text,size=11,selectable=True,expand=True),
                ft.TextButton('Rimuovi',on_click=remove)]))
        if document:
            for name,model in document['models'].items():
                self.rows.controls.append(ft.Text(f"{name}: media/max indipendenti {model['mean_error_mm']:.3f}/{model['max_error_mm']:.3f} mm · outlier {len(model['outliers'])}",size=12))
