"""TapperWare · Flet desktop console (tested with 0.82.2 and 1.0.4).

    python DmiGUI.pyw          # real hardware, explicitly initialize first
    python DmiGUI.pyw --demo   # no hardware imports or communication
"""
from __future__ import annotations

import argparse
import asyncio
from collections import deque
from dataclasses import replace
from datetime import datetime
from pathlib import Path
import sys
import time

import flet as ft

# Standard desktop launch must also resolve the repository's reusable packages
# when invoked from another working directory.
REPOSITORY = Path(__file__).resolve().parent.parent
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from dmi_runtime import (MODELS, MAX_XML_BYTES, GuidedCalibrationRuntime, ObservationRuntime, RealBackend, Runner, Script, ValidationError,
                         compile_script, integer, load_database, model_data)
from dmi_settings import AppSettings, PANELS, load_settings, save_settings
from dmi_photos import PhotoError, latest_photo, snapshot_images, wait_for_new_photo
from dmi_activity import ExecutionActivity, motion
from dmi_commissioning import ConnectionControls, CalibrationControls
from dmi_move import MoveControls
from dmi_press import PressControls
from dmi_target import TargetInspector, target_name, format_pixels, format_mm, experimental_selection
from dmi_physical_press import PhysicalPressControls
from dmi_manual import ManualControls

APP_DIR = Path(__file__).resolve().parent
BG, SURFACE, FIELD = "#0B111B", "#121C2A", "#0D1521"
LINE, TEXT, MUTED = "#263345", "#EEF3FA", "#9AAABD"
ACCENT, GREEN_BG = "#9BE9C5", "#173A32"
AMBER, RED, BLUE = "#F2BE73", "#FF8F98", "#91BFFF"


def label(value, size=13, color=TEXT, weight=None, **kwargs):
    return ft.Text(value, size=size, color=color, weight=weight, **kwargs)


def caption(value):
    return label(value, 10, MUTED, ft.FontWeight.W_600)


def badge(value, color=ACCENT, background=GREEN_BG):
    return ft.Container(label(value, 10, color, ft.FontWeight.W_600),
                        bgcolor=background, border_radius=6,
                        padding=ft.Padding.symmetric(horizontal=9, vertical=5))


def panel(content, **kwargs):
    kwargs.setdefault("padding", 22)
    return ft.Container(content, bgcolor=SURFACE, border=ft.Border.all(1, LINE),
                        border_radius=18, **kwargs)


def disclosure(title, controls, subtitle=None):
    return ft.ExpansionTile(title=label(title, 14, weight=ft.FontWeight.W_600),
        subtitle=label(subtitle, 11, MUTED) if subtitle else None,
        controls=controls, maintain_state=True, expanded=False,
        expanded_cross_axis_alignment=ft.CrossAxisAlignment.STRETCH,
        controls_padding=16)


def button_style(background=None, color=TEXT):
    return ft.ButtonStyle(
        color={ft.ControlState.DEFAULT: color, ft.ControlState.DISABLED: "#718093"},
        bgcolor={ft.ControlState.DEFAULT: background or "#203043",
                 ft.ControlState.DISABLED: "#202A38"},
        shape=ft.RoundedRectangleBorder(radius=10),
        padding=ft.Padding.symmetric(horizontal=18, vertical=13),
        text_style=ft.TextStyle(size=13, weight=ft.FontWeight.W_600),
        elevation=0,
    )


def dropdown_border():
    if hasattr(ft, "OutlineInputBorder"):
        return {"border": ft.OutlineInputBorder(side=ft.BorderSide(1, LINE), border_radius=10)}
    return {"border": ft.InputBorder.OUTLINE, "border_color": LINE, "border_radius": 10}


def panel_options():
    return [ft.DropdownOption(key=value, text=f"Pannello {value}") for value in PANELS]


class DmiControlPanel:
    def __init__(self, page: ft.Page, demo=False, native_drop=False, settings_path=None):
        self.page = page
        self.runner = Runner(APP_DIR, self.on_runtime,observation_active=lambda:self.vision.running)
        self.runner.set_mode("demo" if demo or page.web else "hardware")
        self.vision = ObservationRuntime()
        self.calibration = GuidedCalibrationRuntime()
        self.vision_busy = False
        self.script: Script | None = None
        self.source: bytes | None = None
        self.filename = ""
        self.database = {}
        self.completed = 0
        self.active_index = None
        self.rows = []
        self.row_indicators = []
        self.log_lines = deque(maxlen=2000)
        self.started = None
        self.elapsed = 0.0
        self.ui_busy = False
        self.disposed = False
        self.native_drop = native_drop
        self.startup_notice = None
        self.settings_path = Path(settings_path) if settings_path else APP_DIR / "TapperWare.settings.json"
        settings_error = None
        try:
            self.settings = load_settings(self.settings_path)
        except ValidationError as exc:
            self.settings = AppSettings()
            settings_error = str(exc)
        self.last_photo = None
        self.photo_heading = ""
        # Desktop pick_files() returns its result asynchronously. In Flet 0.8x
        # the constructor does not accept on_result at all. Only newer web
        # client actions need that event; wire it separately when supported.
        self.picker = ft.FilePicker()
        self.save_picker = ft.FilePicker()
        for service in (self.picker, self.save_picker):
            if not any(existing is service for existing in page.services):
                page.services.append(service)
        self.web_picker_action = bool(page.web and hasattr(ft, "PickFiles")
                                      and hasattr(self.picker, "on_result"))
        if self.web_picker_action:
            self.picker.on_result = self.picked_web
        self.setup_page()
        self.build()
        try:
            self.database = load_database(APP_DIR / "DmiPositions.json")
            self.log("Sistema", "Database coordinate caricato.")
        except ValidationError as exc:
            self.log("Errore", str(exc))
        self.log("Sistema", "Modalità demo: nessun comando al robot." if self.is_demo
                 else "Console avviata. Inizializzazione hardware richiesta.")
        if self.startup_notice:
            self.log("Sistema", self.startup_notice)
        if settings_error:
            self.error(settings_error + " Sono in uso i valori iniziali: offset Y = 0.")
        self.update_model_summary()
        self.update_panel_summary()
        self.clear_photo()
        self.refresh()
        page.run_task(self.clock)
        page.run_task(self.vision_clock)

    @property
    def is_demo(self):
        return self.runner.mode == "demo"

    @property
    def locked(self):
        return self.ui_busy or self.runner.busy

    def setup_page(self):
        p = self.page
        p.title = "TapperWare · DMI Control"
        p.bgcolor = BG
        p.padding = 0
        p.theme_mode = ft.ThemeMode.DARK
        p.theme = ft.Theme(color_scheme_seed=ACCENT, font_family="Segoe UI",
                           scaffold_bgcolor=BG, visual_density=ft.VisualDensity.COMFORTABLE)
        p.window.width, p.window.height = 1240, 940
        p.window.min_width, p.window.min_height = 860, 700
        p.window.prevent_close = True
        p.window.on_event = self.window_event
        p.on_keyboard_event = self.keyboard
        p.on_disconnect = self.disconnect

    def build(self):
        self.mode_badge = badge("DEMO" if self.is_demo else "HARDWARE", AMBER, "#392C1C")
        self.settings_button = ft.IconButton(ft.Icons.SETTINGS_OUTLINED, icon_color=MUTED,
            tooltip="Impostazioni · foto e pannelli", on_click=self.open_settings)
        header = ft.Container(ft.Row([
            ft.Container(ft.Icon(ft.Icons.TOUCH_APP_ROUNDED, color=BG, size=25),
                         bgcolor=ACCENT, width=43, height=43, border_radius=12,
                         alignment=ft.Alignment.CENTER),
            ft.Column([label("TapperWare", 20, weight=ft.FontWeight.W_700),
                       caption("DMI  /  CONSOLE DI AUTOMAZIONE")], spacing=1),
            ft.Container(expand=True), self.mode_badge, self.settings_button,
            ft.IconButton(ft.Icons.HELP_OUTLINE_ROUNDED, icon_color=MUTED,
                          tooltip="Guida rapida", on_click=self.help_dialog),
        ], spacing=13), padding=ft.Padding.symmetric(horizontal=30, vertical=18),
            border=ft.Border.only(bottom=ft.BorderSide(1, LINE)))

        self.status_title = label("In attesa", 14, AMBER, ft.FontWeight.W_600)
        self.status_dot = ft.Container(width=7, height=7, border_radius=5, bgcolor=AMBER,
            animate_scale=motion(250), animate_opacity=motion(250))
        self.status_text = label("Inizializzazione della postazione richiesta.", 12, MUTED,
                                 max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)
        title = ft.Row([
            ft.Column([caption("POSTAZIONE DI COLLAUDO"),
                       label("Camera → key → robot", 25, weight=ft.FontWeight.W_600),
                       label("Start the camera, select a detected key, inspect its coordinates.", 13, MUTED)], spacing=5),
            ft.Container(expand=True),
            ft.Container(ft.Row([self.status_dot, self.status_title], spacing=8),
                         padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                         border=ft.Border.all(1, LINE), border_radius=25),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

        self.model = ft.Dropdown(value=MODELS[0], options=[ft.DropdownOption(x) for x in MODELS],
            label="Modello DMI", text_size=13, bgcolor=FIELD, filled=True, fill_color=FIELD,
            content_padding=14, on_select=self.change_model, **dropdown_border())
        self.model_info = label("", 12, MUTED)
        self.panel_select = ft.Dropdown(value=self.settings.selected_panel, options=panel_options(),
            label="Pannello", text_size=13, bgcolor=FIELD, filled=True, fill_color=FIELD,
            content_padding=14, on_select=self.change_panel, **dropdown_border())
        self.panel_info = label("", 12, MUTED)
        self.mode = ft.SegmentedButton(
            selected=[self.runner.mode], allow_empty_selection=False,
            segments=[ft.Segment(value="hardware", label=label("Hardware", 12),
                                 icon=ft.Icons.MEMORY_ROUNDED, disabled=bool(self.page.web)),
                      ft.Segment(value="demo", label=label("Demo", 12), icon=ft.Icons.SCIENCE_OUTLINED)],
            on_change=self.change_mode)
        self.hardware_title = label("Da inizializzare", 17, weight=ft.FontWeight.W_600)
        self.hardware_hint = label("Homing richiesto prima dell'esecuzione.", 12, MUTED)
        self.hw_icon = ft.Icon(ft.Icons.POWER_SETTINGS_NEW_ROUNDED, color=AMBER, size=23)
        self.init_button = ft.Button("Inizializza hardware", icon=ft.Icons.RESTART_ALT_ROUNDED,
            style=button_style("#293528", ACCENT), width=320, height=45, on_click=self.initialize)
        self.demo_note = ft.Container(label("Ambiente simulato. Nessun movimento reale.", 12, AMBER),
            bgcolor="#30291F", border_radius=10, padding=12, visible=self.is_demo)
        self.axis_x, self.axis_y = label("—", 23, weight=ft.FontWeight.W_500), label("—", 23, weight=ft.FontWeight.W_500)
        self.axis_note = label("Ultimo comando · nessuna lettura di posizione", 10, MUTED)
        self.screen_count, self.button_count = label("—", 20), label("—", 20)
        visual = ft.Container(ft.Column([
            ft.Row([caption("PROFILO DMI"), ft.Container(expand=True),
                    ft.Container(width=5, height=5, bgcolor=ACCENT, border_radius=5)]),
            ft.Container(ft.Row([
                ft.Container(ft.Icon(ft.Icons.SPEED_ROUNDED, size=43, color=ACCENT),
                             expand=True, alignment=ft.Alignment.CENTER),
                ft.Column([ft.Container(bgcolor="#294839", height=5, width=58, border_radius=4),
                           ft.Container(bgcolor="#28384B", height=5, width=43, border_radius=4),
                           ft.Container(bgcolor="#28384B", height=5, width=51, border_radius=4)], spacing=9),
            ], spacing=15), bgcolor="#101F29", border=ft.Border.all(1, "#304350"),
                border_radius=9, height=91, padding=18),
            ft.Row([ft.Column([self.screen_count, caption("SCHERMATE")], spacing=2),
                    ft.Container(expand=True),
                    ft.Column([self.button_count, caption("TASTI MAPPATI")], spacing=2)]),
        ], spacing=15), padding=18, bgcolor=FIELD, border_radius=12)
        self.model.width, self.panel_select.width = 240, 200
        station = panel(ft.Column([
            ft.Row([self.model, self.panel_select, self.mode], wrap=True), self.demo_note,
            disclosure('Reference profile and panel offset', [self.model_info, self.panel_info, visual]),
        ], spacing=8), padding=14)
        hardware = ft.Column([
                label('Robot initialization · sensor homing', 17, weight=ft.FontWeight.W_600),
                label('Sets up the robot origin and sensor travel before movement. Camera viewing does not require homing.', 12, MUTED),
                ft.Row([self.init_button, self.hw_icon, self.hardware_title], wrap=True), self.hardware_hint,
                label('ACK checks the connection. DONE reports controller initialization completion; it does not validate camera calibration.', 12, MUTED),
        ], spacing=10)
        requested_position = ft.Column([
                caption("COORDINATE RICHIESTE"),
                ft.Row([ft.Column([caption("X / mm"), self.axis_x], spacing=3),
                        ft.Container(width=32), ft.Column([caption("Y / mm"), self.axis_y], spacing=3)]),
                self.axis_note,
        ], spacing=12)

        self.file_title = label("Nessuno script caricato", 16, weight=ft.FontWeight.W_600,
                               max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        self.file_subtitle = label("Seleziona una sequenza XML per visualizzare i comandi.", 12, MUTED)
        self.file_badge = badge("XML", BLUE, "#1E3149")
        self.browse_button = ft.OutlinedButton("Sfoglia file", icon=ft.Icons.FOLDER_OPEN_ROUNDED,
            style=button_style(), on_click=self.browse)
        if self.web_picker_action:
            self.browse_button.on_click = None
            self.browse_button.action = ft.PickFiles(self.picker, allow_multiple=False, with_data=True,
                file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=["xml"])
        self.example_button = ft.TextButton("Carica esempio", icon=ft.Icons.DESCRIPTION_OUTLINED,
                                           on_click=self.load_example, style=ft.ButtonStyle(color=MUTED))
        self.clear_button = ft.IconButton(ft.Icons.CLOSE_ROUNDED, icon_color=MUTED,
                                          tooltip="Rimuovi script", on_click=self.clear_file, visible=False)
        file_area = ft.Container(ft.Column([
            ft.Row([ft.Container(ft.Icon(ft.Icons.CODE_ROUNDED, color=BLUE, size=24),
                                 bgcolor="#1A2D45", padding=13, border_radius=12),
                    ft.Column([self.file_title, self.file_subtitle], spacing=5, expand=True),
                    self.clear_button], spacing=14),
            ft.Row([self.browse_button, self.example_button], spacing=10),
        ], spacing=18), padding=20, bgcolor=FIELD, border=ft.Border.all(1, LINE), border_radius=12)
        self.drop_area = None
        if self.native_drop:
            try:
                import flet_dropzone as ftd
            except ImportError:
                self.native_drop = False
                self.startup_notice = "Trascinamento non disponibile: usa Sfoglia file."
            else:
                self.drop_area = ftd.Dropzone(content=file_area, on_dropped=self.dropped)
                file_area = ft.Column([self.drop_area, label("Caricamento XML tramite trascinamento disponibile.", 11, MUTED)])

        self.command_list = ft.ListView(height=260, spacing=3, padding=0)
        self.empty = ft.Container(ft.Column([
            ft.Icon(ft.Icons.PLAYLIST_PLAY_ROUNDED, size=43, color="#4F6178"),
            label("Nessuna sequenza disponibile", 14, MUTED),
            label("PRESS  ·  MOVE_TO  ·  WRITE_T9  ·  WAIT", 11, "#73879E"),
        ], spacing=12, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER), height=260, alignment=ft.Alignment.CENTER)
        self.table_header = ft.Container(ft.Row([
            caption("#"), ft.Container(width=23), ft.Container(caption("AZIONE"), width=95),
            ft.Container(caption("DESTINAZIONE / DETTAGLIO"), expand=True), caption("STATO"),
        ]), padding=ft.Padding.symmetric(horizontal=12, vertical=12),
            border=ft.Border.only(bottom=ft.BorderSide(1, LINE)), visible=False)
        self.command_list.visible = False
        self.total_text = label("—", 22, weight=ft.FontWeight.W_600)
        self.elapsed_text = label("00:00", 22, weight=ft.FontWeight.W_600)
        self.done_text = label("—", 22, ACCENT, ft.FontWeight.W_600)
        self.validation_text = label("In attesa di un file", 11, MUTED)
        self.activity = ExecutionActivity()
        self.sequence_panel = panel(ft.Column([
            ft.Row([badge("02", MUTED, "#233044"), label("Sequenza", 16, weight=ft.FontWeight.W_600),
                    ft.Container(expand=True), self.file_badge]),
            file_area, self.activity.control,
            ft.Row([label("Anteprima comandi", 13, weight=ft.FontWeight.W_600),
                              ft.Container(expand=True), self.validation_text]),
            ft.Column([self.table_header, self.empty, self.command_list], spacing=0),
            ft.Divider(color=LINE, height=8),
            ft.Row([self.metric(self.total_text, "COMANDI"), self.metric(self.done_text, "COMPLETATI"),
                    self.metric(self.elapsed_text, "TEMPO TRASCORSO")], spacing=20),
        ], spacing=18))

        self.log_view = ft.ListView(height=121, spacing=7, auto_scroll=True)
        self.export_button = ft.IconButton(ft.Icons.DOWNLOAD_ROUNDED, tooltip="Esporta registro",
                                          icon_color=MUTED, on_click=self.export_log, disabled=bool(self.page.web))
        logs = panel(ft.Column([
            ft.Row([ft.Icon(ft.Icons.TERMINAL_ROUNDED, size=18, color=MUTED),
                    label("Registro eventi", 13, weight=ft.FontWeight.W_600),
                    ft.Container(expand=True), self.export_button,
                    ft.IconButton(ft.Icons.DELETE_SWEEP_OUTLINED, tooltip="Pulisci registro",
                                  icon_color=MUTED, on_click=self.clear_log)]), self.log_view,
        ], spacing=8), padding=16)
        self.photo_title = label("Foto di fine operazione", 16, weight=ft.FontWeight.W_600)
        self.photo_info = label("Configura la cartella di download nelle Impostazioni.", 12, MUTED,
                                selectable=True)
        self.photo_preview = ft.Container(height=180, bgcolor=FIELD, border_radius=12,
            alignment=ft.Alignment.CENTER, content=ft.Icon(ft.Icons.IMAGE_OUTLINED, size=44, color=MUTED))
        self.photo_open_button = ft.TextButton("Apri ultima foto", icon=ft.Icons.PHOTO_LIBRARY_OUTLINED,
            on_click=self.open_latest_photo, style=ft.ButtonStyle(color=ACCENT))
        photo_card = panel(ft.Column([
            ft.Row([ft.Icon(ft.Icons.PHOTO_CAMERA_OUTLINED, color=ACCENT), self.photo_title], spacing=12),
            self.photo_preview, self.photo_info, self.photo_open_button,
        ], spacing=12))
        self.communication = ConnectionControls(self)
        self.build_vision()
        self.robot_tools.controls.append(self.communication.control)
        self.manual_ui = ManualControls(self)
        self.robot_initialization_card = panel(ft.Column([
            hardware, self.robot_tools, ft.Divider(color=LINE), self.manual_ui.control,
            disclosure('Controller initialization details', [
                label('The existing Pi routine first establishes sensor-based travel and origin, then returns DONE or ERROR. '
                      'Once autoscaling is complete, another INITIALIZE in the same receiver process can return DONE without a new sweep.', 12, MUTED),
                label('Homing moves the axes. Confirm measured limits, retracted tool, clear area, physical stop and origin/mount before starting. '
                      'GUI Stop cannot interrupt a blocking receiver motor routine.', 12, AMBER),
                requested_position,
            ]),
        ], spacing=10))
        self.run_button = ft.Button("Avvia sequenza", icon=ft.Icons.PLAY_ARROW_ROUNDED,
            style=button_style(ACCENT, "#10251E"), height=46, on_click=self.run)
        self.stop_button = ft.Button("Arresta", icon=ft.Icons.STOP_ROUNDED,
            style=button_style("#422931", RED), height=46, on_click=self.stop)
        self.legacy_xml_confirm = ft.Checkbox(
            label='Confermo XML legacy con coordinate statiche del database; nessun target visivo/calibrazione',
            value=False,on_change=lambda e:self.refresh())
        self.progress = ft.ProgressBar(value=0, bar_height=5, color=ACCENT, bgcolor=LINE, border_radius=4)
        self.progress_text = label("0%", 12, ACCENT)
        self.current_text = label("In attesa di una sequenza", 13, weight=ft.FontWeight.W_600,
                                  max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        self.dock_spinner = ft.ProgressRing(width=21, height=21, stroke_width=2.5,
                                            color=ACCENT, visible=False)
        dock = ft.Container(ft.Column([
            self.legacy_xml_confirm,
            ft.Row([self.dock_spinner, ft.Column([self.current_text, self.status_text], spacing=4, expand=True),
                    self.run_button, self.stop_button], spacing=12),
            ft.Row([ft.Container(self.progress, expand=True), self.progress_text], spacing=12),
            label("Arresta blocca i comandi successivi e poi richiede il rientro. Non è un arresto di emergenza.", 10, MUTED),
        ], spacing=12), padding=ft.Padding.symmetric(horizontal=30, vertical=17), bgcolor=SURFACE,
            border=ft.Border.only(top=ft.BorderSide(1, LINE)))
        self.legacy_dock = dock
        self.xml_tools = disclosure('Legacy XML sequences and photos', [self.sequence_panel, photo_card],
            'Stored reference coordinates; separate confirmation, stopped observation and homing required.')
        self.xml_tools.on_change = lambda e: self.refresh()
        body = ft.Container(ft.Column([title, station, self.robot_initialization_card,
            ft.ResponsiveRow([
                ft.Column([self.vision_card], col={"xs": 12, "md": 7}),
                ft.Column([self.target_card], col={"xs": 12, "md": 5}),
            ], columns=12, spacing=16, run_spacing=16),
            self.calibration_tools, self.xml_tools,
            disclosure('Event log', [logs]),
        ], spacing=16), padding=ft.Padding.symmetric(horizontal=24, vertical=20))
        self.page.add(ft.Column([header, ft.Column([body], expand=True, scroll=ft.ScrollMode.AUTO), dock],
                               spacing=0, expand=True))

    def metric(self, value, title):
        return ft.Container(ft.Column([value, caption(title)], spacing=4), expand=True)

    def build_vision(self):
        self.vision_kind = ft.Dropdown(value="recorded_replay" if self.is_demo else "remote_bridge", label="Camera source",
            options=[ft.DropdownOption("recorded_replay", "Registrazione offline"),
                     ft.DropdownOption("remote_bridge", "Bridge HTTP camera"),
                     ft.DropdownOption("local_camera", "Camera locale")], on_select=self.vision_source_changed, **dropdown_border())
        self.vision_address = ft.TextField(label="Percorso video / URL frame.jpg / indice camera",
            value="", text_size=12)
        self._vision_addresses = {}
        self._vision_address_kind = self.vision_kind.value
        self.vision_calibration = ft.TextField(label="Custom calibration JSON (optional; blank uses recorded test mapping)", text_size=12)
        self.vision_context = ft.TextField(label="Custom calibration context JSON (only with a custom model)", text_size=12)
        self.vision_debug = ft.Checkbox(label="Log JSONL diagnostico (opzionale)", value=False)
        self.vision_start = ft.Button("Start camera", on_click=self.start_vision)
        self.vision_stop = ft.Button("Stop camera", on_click=self.stop_vision, disabled=True)
        self.vision_status = label("Visione ferma · SENSE/superiore oppure TWINS/inferiore", 12, MUTED)
        self.vision_cal_status = label("Nessuna calibrazione · azioni da visione disabilitate", 12, AMBER)
        self.vision_metrics = label("", 11, MUTED)
        self.vision_mode = label("Icone modalità: sconosciute", 12, MUTED)
        self.vision_raw = ft.Image(src=b"", height=230, visible=False, gapless_playback=True)
        self.vision_annotated = ft.Image(src=b"", height=300, fit=ft.BoxFit.CONTAIN, visible=False, gapless_playback=True)
        self.vision_empty = label('Start the camera to see the live preview here.', 12, MUTED)
        self.vision_fields = label('Waiting for fresh OCR values.', 13, selectable=True)
        self.vision_targets = ft.Column(spacing=4, height=150, scroll=ft.ScrollMode.AUTO)
        self.target_search = ft.TextField(label='Find a detected key', hint_text='For example: 5, enter, close',
            on_change=self.filter_vision_targets)
        self.target_empty = label('Start the camera to see detected keys here.', 12, MUTED)
        self.vision_selection = label("Selezione solo per ispezione · nessun movimento", 12, AMBER, selectable=True)
        self.calibration_ui = CalibrationControls(self)
        self.move_ui = MoveControls(self)
        self.press_ui = PressControls(self)
        self.target_ui = TargetInspector(self)
        self.physical_press_ui = PhysicalPressControls(self)
        self.target_ui.hardware_press.on_click = self.physical_press_ui.request
        self.robot_tools = disclosure('Robot connection settings · connect / ACK first', [],
            'Enter the robot JSON and connect here, then use Initialize robot above.')
        self.calibration_tools = disclosure('Calibration · enter measured robot X / Y', [
            self.vision_calibration, self.vision_context, self.calibration_ui.control],
            'Required before camera-guided actions. Predicted XY are not independent measurements.')
        self.vision_card = panel(ft.Column([
            label('1. Camera and detection results', 17, weight=ft.FontWeight.W_600),
            label('SENSE TOUCHSCREEN / superiore or TWINS / inferiore. TWIN preview is observation-only. Camera viewing needs no robot connection.', 12, MUTED),
            self.vision_kind, self.vision_address,
            ft.Row([self.vision_start, self.vision_stop], wrap=True), self.vision_status,
            caption('LIVE CAMERA · DETECTION OVERLAY'), self.vision_empty, self.vision_annotated,
            caption('OCR FIELD VALUES'), self.vision_fields,
            disclosure('Live camera image', [self.vision_raw]),
            disclosure('Timing, calibration status and diagnostics', [self.vision_cal_status,
                self.vision_metrics, self.vision_mode, self.vision_debug]),
        ], spacing=10))
        self.target_card = panel(ft.Column([
            label('2. Select a detected key', 17, weight=ft.FontWeight.W_600),
            label('Find 5, then click Key 5. Selection alone never sends a command.', 12, MUTED),
            self.target_search, self.target_empty, self.vision_targets,
            ft.Divider(), label('3. Inspect and act', 17, weight=ft.FontWeight.W_600),
            self.target_ui.control, self.physical_press_ui.control,
            disclosure('Movement limits and optional move-only test', [self.move_ui.control],
                'An adequate fit and independently measured movement bounds are required.'),
            disclosure('Demo presses and mode holds · simulation only', [self.press_ui.control]),
            disclosure('Selected detection details', [self.vision_selection]),
        ], spacing=10))
        self._vision_signature = None
        self._vision_running = False
        self._vision_selection_key = None
        self.vision_source_changed()
        return self.vision_card

    def vision_source_changed(self, e=None):
        kind = self.vision_kind.value
        if kind != self._vision_address_kind:
            self._vision_addresses[self._vision_address_kind] = self.vision_address.value or ''
            self.vision_address.value = self._vision_addresses.get(kind, '')
            self._vision_address_kind = kind
        labels = {'remote_bridge': ('Camera address', 'http://PI_IP:8080/frame.jpg'),
                  'recorded_replay': ('Recording path', '/absolute/path/to/recording.mp4'),
                  'local_camera': ('Local camera index', '1')}
        self.vision_address.label, self.vision_address.hint_text = labels[self.vision_kind.value]
        if e is not None:
            self.page.update(self.vision_address)

    def filter_vision_targets(self, e=None):
        if self.vision.observer:
            self._vision_signature = None
            self.render_vision(self.vision.observer.snapshot())
        self.page.update(self.target_card)

    def clear_vision(self):
        self.legacy_xml_confirm.value = False
        self.calibration_ui.reset()
        self.move_ui.reset()
        self.press_ui.reset()
        self.physical_press_ui.reset()
        self.vision_raw.visible = self.vision_annotated.visible = False
        self.vision_raw.src = self.vision_annotated.src = b""
        self.vision_empty.visible = True
        self.vision_targets.controls.clear()
        self._vision_signature = self._vision_selection_key = None
        self.vision_selection.value = "Selezione solo per ispezione · nessun movimento"
        self.vision_mode.value = "Icone modalità: sconosciute"
        self.vision_fields.value = 'Waiting for fresh OCR values.'
        self.target_ui.update()
        self.target_empty.value = 'Start the camera to see detected keys here.'
        self.target_empty.visible = True

    async def start_vision(self, e=None):
        if self.locked or self.vision_busy or self.vision.running:
            return
        sense = self.model.value == 'SENSE TOUCHSCREEN' and self.panel_select.value == 'superiore'
        twin = self.model.value == 'TWINS' and self.panel_select.value == 'inferiore'
        if not (sense or twin):
            self.error("La visione richiede SENSE TOUCHSCREEN/superiore oppure TWINS/inferiore.")
            return
        if twin and (self.vision_calibration.value.strip() or self.vision_context.value.strip()):
            self.error('TWIN preview is observation-only. Clear the SENSE calibration and context fields before starting.')
            return
        if (self.is_demo or self.page.web) and self.vision_kind.value != "recorded_replay":
            self.error("In demo/browser usare una registrazione offline; nessuna camera reale viene aperta.")
            return
        self.vision_busy = True
        self.clear_vision()
        self.refresh()
        try:
            await asyncio.to_thread(self.vision.start, self.vision_kind.value,
                self.vision_address.value.strip(), calibration_path=self.vision_calibration.value.strip(),
                context_path=self.vision_context.value.strip(),
                recorded_test=(sense and not self.is_demo and self.vision_kind.value == "remote_bridge"
                    and not self.vision_calibration.value.strip() and not self.vision_context.value.strip()),
                origin_epoch=self.runner.origin_epoch,
                debug_jsonl=REPOSITORY / "dmi_robot_config/local/vision_debug.jsonl" if self.vision_debug.value else None)
            experimental = sense and not self.is_demo and not self.vision_calibration.value.strip() and not self.vision_context.value.strip()
            self.vision_status.value = ('Avvio visione TWIN · sola osservazione…' if twin else
                'Avvio visione · experimental recorded homography (accuracy unverified)…' if experimental else 'Avvio visione…')
            self.log("Visione", "Osservazione avviata; nessuna azione robot abilitata.")
        except Exception as exc:
            self.error(f"Avvio visione: {exc}")
        finally:
            self.vision_busy = False
            self.refresh()

    async def stop_vision(self, e=None):
        self.vision.invalidate()
        self.clear_vision()
        self.vision_status.value = "Visione ferma · risultati invalidati"
        self.vision_busy = True
        self.refresh()
        try:
            await asyncio.to_thread(self.vision.close)
        except Exception as exc:
            self.error(str(exc))
        finally:
            self.vision_busy = False
            self.refresh()

    async def select_vision_target(self, session_id, screen, target_label):
        self.move_ui.changed()
        self.press_ui.changed()
        self.physical_press_ui.reset()
        self._vision_selection_key = None
        self.calibration_ui.use_selected_target(None, None, None)
        try:
            target = await asyncio.to_thread(self.vision.observer.inspect_target,
                                            session_id, screen, target_label)
            current = self.vision.observer.snapshot()
            if (not current['fresh'] or current['session_id'] != session_id
                    or current['capture_index'] != target['capture_index']):
                raise ValueError("Osservazione cambiata durante la selezione")
            self._vision_selection_key = (session_id, screen, target_label)
            self.calibration_ui.use_selected_target(session_id, screen, target_label)
            self.target_ui.update(current)
            self.vision_selection.value = (f"{screen} · {target_label} · px {format_pixels(target['pixel'])} · "
                f"XY previsto {format_mm(self.target_ui.display_mm)} mm · età {target['age_seconds']:.2f} s · conferma separata richiesta")
            if target['kind']=='box':
                self.vision_selection.value += ' · stima non verificata; pressione fisica bloccata'
        except Exception as exc:
            self._vision_selection_key = None
            self.vision_selection.value = f"Selezione invalidata: {exc}"
        current = self.vision.observer.snapshot()
        self.target_ui.update(current)
        self.physical_press_ui.update(current)
        if not self.disposed:
            self.page.update(self.target_card, self.calibration_tools)

    async def vision_clock(self):
        while not self.disposed:
            if self.vision.observer:
                view = self.vision.observer.snapshot()
                self.render_vision(view)
                running = self.vision.running
                if running != self._vision_running:
                    self._vision_running = running
                    self.refresh()
                else:
                    self.page.update(self.vision_card, self.target_card, self.calibration_tools)
            await asyncio.sleep(.2)

    def render_vision(self, view):
        age = f"{view['age_seconds']:.2f} s" if view['age_seconds'] is not None else "—"
        self.vision_status.value = (f"{view['state']} · età rilevamento {age}"
                                    + (f" · {view['error']}" if view['error'] else ""))
        for control, value in ((self.vision_raw, view['raw_jpeg']),
                               (self.vision_annotated, view['annotation_jpeg'])):
            control.visible = value is not None
            if control.src != (value or b""):
                control.src = value or b""
        projection = view['projection']
        fields = view.get('ocr_fields', {})
        if not view['fresh']:
            self.vision_fields.value = ('OCR values stale — waiting for fresh detections.'
                if view['state'] == 'stale' else 'Waiting for fresh OCR values.')
        else:
            self.vision_fields.value = '\n'.join(
                f"{target_name(name)}: {value if value is not None and str(value).strip() else '— unreadable / awaiting confirmation'}"
                for name, value in fields.items()) or 'No OCR fields available in the latest detection.'
        self.vision_empty.visible = view['annotation_jpeg'] is None
        self.calibration_ui.update_targets(view)
        self.move_ui.update(view)
        self.press_ui.update(view)
        self.vision_cal_status.value = ("Calibrazione: " + (view['calibration_error'] or
            ("stima non verificata fisicamente" if projection and not projection['calibration_valid']
             else "ispezione")) + " · test con conferma separata e controlli al comando")
        if projection and projection.get('experimental_recorded_test') and not view.get('calibration_error'):
            self.vision_cal_status.value = 'EXPERIMENTAL · saved homography + current measured borders · accuracy unverified; freshness/travel guards apply'
        if projection and projection.get('calibration_id'):
            self.vision_cal_status.value += f" · ID {projection['calibration_id'][:12]}"
        m = view['metrics']
        self.vision_metrics.value = (f"Analisi {m['processed_fps']:.2f} FPS · media/P95 "
            f"{m['analysis_mean_seconds']:.3f}/{m['analysis_p95_seconds']:.3f} s · sovrascritti {m['overwrites']} "
            "· FPS locali, non misura camera/GUI")
        modes = view['modes']
        self.vision_mode.value = f"Icone modalità: {modes.get('state', 'unknown')} · {modes.get('mode') or '—'}"
        if modes.get('replacement_verified'):
            self.vision_mode.value += " · stessa icona lampeggiante ora stabile al posto di power (solo osservazione)"
        self.target_ui.update(view)
        signature = (view['session_id'], view['capture_index'])
        if signature != self._vision_signature:
            self._vision_signature = signature
            self.vision_targets.controls.clear()
            if projection:
                screen = projection['screen']
                for name, target in projection['targets'].items():
                    query = (self.target_search.value or '').strip().casefold()
                    if query and query not in (target_name(name) + ' ' + name).casefold():
                        continue
                    text = f"{target_name(name)} · {name} · px {format_pixels(target['pixel'])}"
                    if 'active' in target:
                        text += f" · active={target['active']}"
                    if target['kind']=='box':
                        text += ' · stima non verificata; nessuna autorizzazione fisica'
                    async def select(e, sid=view['session_id'], state=screen, identity=name):
                        await self.select_vision_target(sid, state, identity)
                    self.vision_targets.controls.append(ft.TextButton(text, on_click=select))
            self.target_empty.visible = not bool(self.vision_targets.controls)
            self.target_empty.value = ('No matching detected key. Try another name.' if projection
                                       else 'Waiting for fresh detections. Old results cannot be selected.')
        selected = self._vision_selection_key
        if (view['fresh'] and selected and projection
                and selected[:2] == (view['session_id'], projection['screen'])
                and selected[2] in projection['targets']):
            target = projection['targets'][selected[2]]
            self.vision_selection.value = (f"{selected[1]} · {selected[2]} · px {format_pixels(target['pixel'])} · "
                f"XY previsto {format_mm(self.target_ui.display_mm)} mm · età {age} · "
                + ('one-click experimental test' if experimental_selection(view, selected) else 'conferma separata richiesta'))
            if target['kind']=='box':
                self.vision_selection.value += ' · stima non verificata; pressione fisica bloccata'
        elif experimental_selection(view, selected):
            self.vision_selection.value = f'{selected[1]} · {selected[2]} · selection retained; direct coordinates checked on click'
        else:
            self._vision_selection_key = None
            self.vision_selection.value = "Seleziona un rilevamento attuale per ispezionarlo · azioni disabilitate"
        self.physical_press_ui.update(view)
        self.vision_stop.disabled = self.vision_busy or not self.vision.running
        self.vision_start.disabled = self.vision_busy or self.vision.running or self.locked

    def log(self, category, text):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_lines.append(f"{timestamp} [{category}] {text}")
        color = RED if category == "Errore" else AMBER if category == "Arresto" else ACCENT
        self.log_view.controls.append(ft.Row([
            label(timestamp, 10, "#74859A", font_family="Consolas"),
            label(category.upper(), 9, color, ft.FontWeight.W_600, width=67),
            label(text, 11, MUTED, expand=True, selectable=True),
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.START))
        if len(self.log_view.controls) > 160:
            del self.log_view.controls[:-160]

    def refresh(self):
        if self.disposed:
            return
        locked = self.locked
        for control in (self.model, self.mode, self.init_button, self.browse_button,
                        self.example_button, self.clear_button, self.panel_select,
                        self.settings_button, self.photo_open_button):
            control.disabled = locked
        if self.drop_area:
            self.drop_area.disabled = locked
        self.run_button.disabled = locked or not self.runner.initialized or not self.script
        observing = self.vision.running or self.vision_busy
        # Legacy static-coordinate XML shares this owner but cannot compete with vision/photos.
        if self.runner.hardware_actions_blocked:
            self.run_button.disabled = True
        self.legacy_xml_confirm.visible = not self.is_demo
        self.legacy_xml_confirm.disabled = locked or observing
        if not self.is_demo and isinstance(self.runner.backend,RealBackend) and not self.legacy_xml_confirm.value:
            self.run_button.disabled = True
        self.vision_start.disabled = locked or observing
        self.vision_stop.disabled = self.vision_busy or not self.vision.running
        for control in (self.vision_kind, self.vision_address, self.vision_calibration,
                        self.vision_context, self.vision_debug):
            control.disabled = observing
        self.communication.refresh()
        self.manual_ui.refresh()
        self.calibration_ui.refresh()
        self.move_ui.refresh()
        self.press_ui.refresh()
        self.target_ui.hardware_press.visible = not self.is_demo
        self.physical_press_ui.refresh()
        self.legacy_dock.visible = bool(self.xml_tools.expanded or self.runner.busy or self.started is not None)
        self.stop_button.disabled = self.runner.phase != "running" or self.runner.stop.is_set()
        self.mode_badge.content.value = "DEMO · SIMULAZIONE" if self.is_demo else "HARDWARE"
        self.mode_badge.content.color = AMBER if self.is_demo else BLUE
        self.mode_badge.bgcolor = "#392C1C" if self.is_demo else "#1E3149"
        self.demo_note.visible = self.is_demo
        self.dock_spinner.visible = self.activity.active
        if not self.activity.active:
            self.status_dot.scale, self.status_dot.opacity = 1, 1
        connected = (self.runner.backend is not None and (
            not isinstance(self.runner.backend, RealBackend)
            or self.runner.backend.session.status()['connection'] == 'connected'))
        self.init_button.disabled = locked or (not self.is_demo and not connected)
        self.init_button.content = 'Initialize demo · simulated homing' if self.is_demo else 'Initialize robot · sensor homing'
        if self.runner.initialized:
            self.hardware_title.value = 'Demo initialized' if self.is_demo else 'Controller initialization complete'
            self.hardware_hint.value = ('Simulated initialization only.' if self.is_demo else
                                        'INITIALIZE: DONE. A new sensor sweep is not guaranteed if the Pi was already initialized. Camera calibration remains separate.')
            self.hw_icon.icon, self.hw_icon.color = ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, ACCENT
        elif self.runner.phase == 'initializing':
            self.hardware_title.value = 'Initializing…'
            self.hardware_hint.value = 'Waiting for the controller outcome. Do not send another initialization.'
            self.hw_icon.icon, self.hw_icon.color = ft.Icons.SYNC_ROUNDED, BLUE
        else:
            self.hardware_title.value = 'Not initialized'
            self.hardware_hint.value = ('Open Robot connection settings and use Connetti / ACK first.'
                if not self.is_demo and not connected else
                'Initialize before robot movement. Hardware homing requires explicit safety confirmation.')
            self.hw_icon.icon, self.hw_icon.color = ft.Icons.POWER_SETTINGS_NEW_ROUNDED, AMBER
        self.page.update()

    def status(self, title, text, color=ACCENT):
        self.status_title.value, self.status_title.color = title, color
        self.status_dot.bgcolor = color
        self.status_text.value = text

    def update_model_summary(self):
        try:
            data = model_data(self.database, self.model.value)
            self.screen_count.value = str(len(data["screens"]))
            self.button_count.value = str(sum(len(s.get("buttons", {})) for s in data["screens"].values()
                                              if isinstance(s, dict)))
            self.model_info.value, self.model_info.color = "Mappa coordinate disponibile", ACCENT
        except ValidationError:
            self.screen_count.value = self.button_count.value = "—"
            self.model_info.value, self.model_info.color = "Coordinate non configurate", AMBER

    def clear_preview(self):
        self.script = None
        self.rows = []
        self.row_indicators = []
        self.activity.configure(None)
        self.completed = 0
        self.active_index = None
        self.command_list.controls.clear()
        self.command_list.visible = self.table_header.visible = False
        self.empty.visible = True
        self.total_text.value = self.done_text.value = "—"
        self.progress.value = 0
        self.progress_text.value = "0%"
        self.elapsed = 0
        self.elapsed_text.value = "00:00"
        self.validation_text.value, self.validation_text.color = "In attesa di un file", MUTED

    def activate(self, name, source):
        if self.locked:
            return
        self.legacy_xml_confirm.value = False
        self.clear_preview()
        self.clear_photo()
        self.source, self.filename = source, name
        self.file_title.value = name
        self.file_title.tooltip = name
        self.clear_button.visible = True
        try:
            # Read JSON at every file/model change; the resulting plan is immutable.
            self.database = load_database(APP_DIR / "DmiPositions.json")
            self.update_model_summary()
            self.script = compile_script(source, name, self.model.value, self.database,
                y_offset_mm=self.settings.offset_for(self.panel_select.value))
            self.activity.configure(self.script)
            self.render_commands()
            self.file_subtitle.value = (f"{len(source) / 1024:.1f} KB · {self.model.value} · "
                                        f"pannello {self.panel_select.value} · ΔY {self.script.y_offset_mm:+d} mm")
            self.validation_text.value, self.validation_text.color = "✓ Validazione completata", ACCENT
            self.current_text.value = "Sequenza validata"
            self.status("Operativa" if self.runner.initialized else "Da inizializzare",
                        "Avvio della sequenza abilitato." if self.runner.initialized else "Inizializzazione richiesta per abilitare l'esecuzione.",
                        ACCENT if self.runner.initialized else AMBER)
            self.log("Script", f"{name} · {len(self.script.commands)} comandi validati.")
        except (ValidationError, TypeError) as exc:
            self.file_subtitle.value = "Verificare lo script o selezionare un modello con coordinate configurate."
            self.validation_text.value, self.validation_text.color = "Script non valido", RED
            self.current_text.value = "Esecuzione non disponibile"
            self.error(str(exc))
        self.refresh()

    def render_commands(self):
        self.empty.visible = False
        self.command_list.visible = self.table_header.visible = True
        for command in self.script.commands:
            color = BLUE if command.action == "MOVE_TO" else AMBER if command.action == "WAIT" else ACCENT
            state = label("In coda", 10, MUTED, width=64, text_align=ft.TextAlign.RIGHT)
            indicator = ft.Container(width=17, height=17,
                content=ft.Icon(ft.Icons.RADIO_BUTTON_UNCHECKED, size=12, color="#526478"))
            row = ft.Container(ft.Row([
                label(f"{command.number:02d}", 11, "#72859B", width=32, font_family="Consolas"),
                ft.Container(badge(command.action, color, "#1D2B3B"), width=104),
                ft.Column([label(command.target, 12, weight=ft.FontWeight.W_500,
                                 max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, tooltip=command.target),
                           label(command.detail, 10, MUTED)], spacing=3, expand=True), indicator, state,
            ], spacing=9), padding=ft.Padding.symmetric(horizontal=12, vertical=10), border_radius=8,
                bgcolor=FIELD, border=ft.Border.all(1, FIELD), animate=motion(220))
            self.rows.append((row, state))
            self.row_indicators.append(indicator)
            self.command_list.controls.append(row)
        self.total_text.value, self.done_text.value = str(len(self.script.commands)), "0"

    async def browse(self, e=None):
        if self.locked:
            return
        try:
            files = await self.picker.pick_files(dialog_title="Seleziona uno script XML", allow_multiple=False,
                file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=["xml"],
                with_data=bool(self.page.web))
            await self.accept_files(files)
        except Exception as exc:
            self.error(f"Selezione file: {exc}")

    async def picked_web(self, e):
        await self.accept_files(e.files)

    async def accept_files(self, files):
        """Shared loader for async desktop selection and browser file bytes."""
        if self.locked or not files:
            return
        file = files[0]
        if not self.page.web and getattr(file, "path", None):
            await self.load_path(Path(file.path))
        elif getattr(file, "bytes", None) is not None:
            self.activate(file.name, file.bytes)
        else:
            self.error("Il selettore non ha fornito il percorso o il contenuto del file.")

    async def dropped(self, e):
        if self.locked:
            return
        if len(e.files) != 1:
            self.error("Trascina un solo file XML alla volta.")
            return
        file = e.files[0]
        try:
            if not self.page.web and file.path:
                await self.load_path(Path(file.path))
            else:
                self.activate(file.name, await e.control.read_bytes(file))
        except Exception as exc:
            self.error(f"Caricamento file: {exc}")

    async def load_path(self, path):
        try:
            if path.stat().st_size > MAX_XML_BYTES:
                raise ValidationError("Lo script supera il limite di 2 MB.")
            source = await asyncio.to_thread(path.read_bytes)
            self.activate(path.name, source)
        except (OSError, ValidationError) as exc:
            self.error(str(exc))

    async def load_example(self, e=None):
        if not self.locked:
            await self.load_path(APP_DIR / "test.xml")

    def clear_file(self, e=None):
        if self.locked:
            return
        self.clear_preview()
        self.clear_photo()
        self.source, self.filename = None, ""
        self.file_title.value = "Nessuno script caricato"
        self.file_subtitle.value = "Seleziona una sequenza XML per visualizzare i comandi."
        self.clear_button.visible = False
        self.current_text.value = "In attesa di una sequenza"
        self.status("Operativa" if self.runner.initialized else "In attesa", "Carica uno script XML.", MUTED)
        self.refresh()

    def change_model(self, e):
        if self.locked:
            return
        self.vision.invalidate()
        self.clear_vision()
        self.update_model_summary()
        if self.source is not None:
            self.activate(self.filename, self.source)
        self.refresh()

    def update_panel_summary(self):
        offset = self.settings.offset_for(self.panel_select.value)
        self.panel_info.value = (f"X = JSON · Y = JSON {offset:+d} mm" if offset
                                 else "Coordinate X e Y originali del JSON")

    def change_panel(self, e=None):
        if self.locked:
            self.panel_select.value = self.settings.selected_panel
            self.refresh()
            return
        try:
            settings = replace(self.settings, selected_panel=self.panel_select.value)
            save_settings(self.settings_path, settings)
        except (OSError, ValidationError) as exc:
            self.panel_select.value = self.settings.selected_panel
            self.error(f"Impossibile salvare il pannello: {exc}")
            return
        self.settings = settings
        self.vision.invalidate()
        self.clear_vision()
        self.update_panel_summary()
        self.clear_photo()
        if self.source is not None:
            self.activate(self.filename, self.source)
        self.log("Pannello", f"{self.panel_select.value.capitalize()} · {self.panel_info.value}")
        self.refresh()

    def open_settings(self, e=None):
        if self.locked:
            return
        self.folder_field = ft.TextField(label="Cartella delle foto scaricate", value=self.settings.photo_directory,
            hint_text="Es. C:\\DMI\\Pictures", text_size=13, bgcolor=FIELD)
        self.offset_field = ft.TextField(label="Offset Y (mm, anche negativo)",
            value=str(self.settings.y_offset_mm), text_size=13, bgcolor=FIELD)
        self.offset_panel_field = ft.Dropdown(label="Applica l'offset a", options=panel_options(),
            value=self.settings.offset_panel, text_size=13, filled=True, fill_color=FIELD,
            **dropdown_border())
        self.timeout_field = ft.TextField(label="Attesa del file dopo GET_PICTURES (secondi)",
            value=str(self.settings.photo_wait_seconds), text_size=13, bgcolor=FIELD)
        self.recursive_field = ft.Checkbox(label="Cerca anche nelle sottocartelle",
                                            value=self.settings.photo_recursive)
        self.settings_error = label("", 12, RED, visible=False)
        self.settings_dialog = ft.AlertDialog(modal=True, title=label("Impostazioni", 22), bgcolor=SURFACE,
            content=ft.Container(ft.Column([
                caption("FOTO AUTOMATICA A FINE SEQUENZA"),
                self.folder_field,
                ft.TextButton("Scegli cartella", icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                              on_click=self.browse_photo_folder, disabled=bool(self.page.web)),
                label("Indica la cartella in cui GET_PICTURES salva già i file. "
                      "Questa opzione imposta dove cercare la foto.", 12, MUTED),
                self.timeout_field, self.recursive_field,
                ft.Divider(color=LINE), caption("COORDINATE DEI PANNELLI"),
                self.offset_panel_field, self.offset_field,
                label("Sul pannello scelto: X invariata, Y = Y del JSON + offset. "
                      "L'altro pannello usa le coordinate originali. Il rientro resta [0, 0, 0].", 12, MUTED),
                self.settings_error,
            ], spacing=13, tight=True, scroll=ft.ScrollMode.AUTO), width=500, height=520),
            actions=[ft.TextButton("Annulla", on_click=lambda e: self.page.pop_dialog()),
                     ft.Button("Salva impostazioni", style=button_style(ACCENT, BG),
                               on_click=self.commit_settings)])
        self.page.show_dialog(self.settings_dialog)

    async def browse_photo_folder(self, e=None):
        if self.locked or self.page.web:
            return
        try:
            path = await self.save_picker.get_directory_path(dialog_title="Cartella foto DMI")
            if path and self.settings_dialog.open:
                self.folder_field.value = path
                self.page.update()
        except Exception as exc:
            self.settings_error.value = f"Scelta cartella: {exc}"
            self.settings_error.visible = True
            self.page.update()

    def commit_settings(self, e=None):
        if self.locked:
            return
        try:
            settings = AppSettings(
                photo_directory=(self.folder_field.value or "").strip(),
                photo_wait_seconds=integer(self.timeout_field.value, "attesa foto"),
                photo_recursive=bool(self.recursive_field.value),
                y_offset_mm=integer(self.offset_field.value, "offset Y"),
                offset_panel=self.offset_panel_field.value,
                selected_panel=self.panel_select.value).validate()
            save_settings(self.settings_path, settings)
        except (OSError, ValidationError) as exc:
            self.settings_error.value = str(exc)
            self.settings_error.visible = True
            self.page.update()
            return
        self.settings = settings
        self.page.pop_dialog()
        self.update_panel_summary()
        self.clear_photo()
        if self.source is not None:
            self.activate(self.filename, self.source)
        self.log("Opzioni", f"Impostazioni salvate · offset {settings.y_offset_mm:+d} mm "
                            f"sul pannello {settings.offset_panel}.")
        self.refresh()

    def clear_photo(self):
        self.last_photo = None
        self.photo_heading = ""
        self.photo_title.value = "Foto di fine operazione"
        self.photo_preview.content = ft.Icon(ft.Icons.IMAGE_OUTLINED, size=44, color=MUTED)
        self.photo_preview.on_click = None
        self.photo_info.value = ("Acquisizione automatica al termine della sequenza."
            if self.settings.photo_directory else "Configura la cartella di download nelle Impostazioni.")

    def display_photo(self, photo, heading):
        self.last_photo, self.photo_heading = photo, heading
        self.photo_title.value = heading
        self.photo_info.value = f"{photo.path.name} · {photo.width} × {photo.height} px\n{photo.path}"
        self.photo_preview.content = ft.Image(src=photo.preview, fit=ft.BoxFit.CONTAIN)
        self.photo_preview.on_click = self.show_photo_dialog
        self.log("Foto", str(photo.path))
        self.show_photo_dialog()

    def show_photo_dialog(self, e=None):
        if self.last_photo is None:
            return
        self.page.show_dialog(ft.AlertDialog(title=label(self.photo_heading, 22), bgcolor=SURFACE,
            content=ft.Container(ft.Column([
                ft.Image(src=self.last_photo.preview, fit=ft.BoxFit.CONTAIN, width=720, height=340),
                label(self.photo_info.value, 12, MUTED, selectable=True),
            ], spacing=14, tight=True, scroll=ft.ScrollMode.AUTO), width=720),
            actions=[ft.TextButton("Chiudi", on_click=lambda e: self.page.pop_dialog())]))

    async def open_latest_photo(self, e=None):
        if self.locked:
            return
        self.ui_busy = True
        self.refresh()
        try:
            folder = self.settings.photo_path(APP_DIR)
            if folder is None:
                raise PhotoError("Imposta la cartella delle foto nelle Impostazioni (icona ingranaggio).")
            photo = await asyncio.to_thread(latest_photo, folder, self.settings.photo_recursive)
            self.display_photo(photo, "Ultima foto nella cartella")
        except PhotoError as exc:
            self.error(str(exc))
        finally:
            self.ui_busy = False
            self.refresh()

    async def finish_with_photo(self):
        self.current_text.value = "Acquisizione foto…"
        self.status("Acquisizione", "Sequenza e rientro completati. Preparazione fotocamera…", BLUE)
        self.activity.set_phase("capture", "Acquisizione foto", title="Acquisizione immagine",
                                detail="Sequenza e rientro completati.")
        self.refresh()
        folder = self.settings.photo_path(APP_DIR)
        before, folder_error = {}, None
        if folder is not None and not self.is_demo:
            try:
                # GET_PICTURES may create the folder on its first download.
                if folder.exists():
                    before = await asyncio.to_thread(snapshot_images, folder, self.settings.photo_recursive)
            except (OSError, PhotoError) as exc:
                folder_error = str(exc)
        try:
            await self.runner.capture_pictures(directory=folder)
        except Exception as exc:
            raise PhotoError(f"Sequenza e rientro completati. Acquisizione foto non riuscita: {exc}") from exc
        if self.is_demo:
            self.current_text.value = "Operazione completata · DEMO"
            self.status("Completata", "TAKE_PICTURES e GET_PICTURES simulati; nessuna nuova foto scattata.")
            self.log("Foto", "Comandi foto simulati. Nessun download reale.")
            self.activity.set_phase("complete", "Simulazione completata",
                title="Operazione completata · DEMO", detail="Comandi e acquisizione simulati.", active=False)
            if folder is not None:
                try:
                    photo = await asyncio.to_thread(latest_photo, folder, self.settings.photo_recursive)
                    self.display_photo(photo, "Operazione completata · DEMO · foto esistente")
                except PhotoError as exc:
                    self.log("Foto", f"Anteprima demo non disponibile: {exc}")
            return
        if folder_error:
            raise PhotoError(folder_error)
        if folder is None:
            raise PhotoError("Comandi foto eseguiti. Configura la cartella di download nelle Impostazioni, "
                             "poi usa Apri ultima foto.")
        self.current_text.value = "Ricezione dell'immagine in corso…"
        self.status("Ricezione foto", f"Ricerca della nuova immagine in {folder}…", BLUE)
        self.activity.set_phase("download", "Ricezione foto", title="Verifica dell'immagine",
                                detail="Attesa del completamento del download.")
        self.refresh()
        photo = await wait_for_new_photo(folder, before, timeout=self.settings.photo_wait_seconds,
                                        recursive=self.settings.photo_recursive)
        self.current_text.value = "Operazione completata"
        self.status("Completata", "Sequenza, rientro e acquisizione foto completati.")
        self.activity.set_phase("complete", "Operazione completata", title="Sequenza completata",
                                detail="Rientro e acquisizione foto confermati.", active=False)
        self.display_photo(photo, "Operazione completata")

    async def change_mode(self, e):
        if self.locked:
            return
        try:
            await self.runner.disconnect()
        except Exception as exc:
            self.mode.selected = [self.runner.mode]
            self.error(str(exc))
            return
        self.vision.invalidate()
        self.clear_vision()
        self.runner.set_mode(self.mode.selected[0])
        self.vision_kind.value = 'recorded_replay' if self.is_demo else 'remote_bridge'
        self.vision_source_changed()
        self.axis_x.value = self.axis_y.value = "—"
        if self.source is not None:
            self.activate(self.filename, self.source)
        self.status("Da inizializzare", "Ambiente cambiato: inizializzazione richiesta.", AMBER)
        self.log("Sistema", "Modalità demo attiva." if self.is_demo else "Modalità hardware reale attiva.")
        self.refresh()

    async def initialize(self, e=None, *, operator_confirmed=False, checks=None):
        if self.locked:
            return
        if isinstance(self.runner.backend,RealBackend) and not self.is_demo and not operator_confirmed:
            from dmi_robot_master.integration.robot_session import HOMING_CHECKS
            confirmed_backend = self.runner.backend
            confirmed_epoch = self.runner.origin_epoch
            titles = ('Limiti XY misurati e configurati','Tool Z retratto','Arresto fisico disponibile',
                      'Area homing libera','Origine, montaggio e convenzioni verificati dall’operatore')
            boxes = {key:ft.Checkbox(label=text,value=False) for key,text in zip(HOMING_CHECKS,titles)}
            async def confirm(event):
                if not all(box.value for box in boxes.values()):
                    return
                self.page.pop_dialog()
                if self.runner.backend is not confirmed_backend or self.runner.origin_epoch != confirmed_epoch:
                    self.error('Connessione/origine cambiata: richiedere una nuova conferma di homing')
                    return
                await self.initialize(operator_confirmed=True,checks={key:box.value for key,box in boxes.items()})
            self.page.show_dialog(ft.AlertDialog(title=label('Confermare homing hardware',20),
                content=ft.Column([label('INITIALIZE può muovere gli assi. Le caselle sono dichiarazioni, non prove fisiche.',12),*boxes.values()],tight=True),
                actions=[ft.TextButton('Annulla',on_click=lambda e:self.page.pop_dialog()),ft.TextButton('Confermo homing',on_click=confirm)]))
            return
        self.ui_busy = True
        self.activity.set_phase("sync", "Connessione", title="Inizializzazione della postazione",
                                detail="Sincronizzazione con il controller.")
        self.status("Inizializzazione", "Connessione al controller…", BLUE)
        self.refresh()
        try:
            if self.is_demo and isinstance(self.runner.backend,RealBackend):
                from dmi_robot_master.integration.robot_session import HOMING_CHECKS
                operator_confirmed,checks = True,{key:True for key in HOMING_CHECKS}
            await self.runner.initialize(operator_confirmed=operator_confirmed,checks=checks)
            self.axis_x.value = self.axis_y.value = "0"
            self.activity.move_to(0, 0)
            self.activity.set_phase("ready", "Postazione operativa", title="Inizializzazione completata",
                detail="Sequenza disponibile per l'esecuzione." if self.script else "Caricare una sequenza XML.",
                active=False)
            self.status("Operativa", "Postazione inizializzata. " + ("Avvio della sequenza abilitato." if self.script else "Carica uno script XML."))
            if not self.is_demo:
                self.status('Initialization complete', 'INITIALIZE: DONE; a new sensor sweep is not guaranteed. Vision actions remain unverified.', AMBER)
            self.log("Hardware", "Homing simulato completato." if self.is_demo else "INITIALIZE completato: DONE ricevuto.")
        except Exception as exc:
            self.activity.set_phase("error", "Inizializzazione non riuscita", title="Postazione non inizializzata",
                                    detail=str(exc), active=False, color=RED)
            self.error(f"Inizializzazione non riuscita: {exc}")
        finally:
            self.ui_busy = False
            self.refresh()

    async def run(self, e=None):
        if (self.locked or not self.script or not self.runner.initialized
                or self.runner.hardware_actions_blocked):
            return
        if not self.is_demo and isinstance(self.runner.backend,RealBackend) and not self.legacy_xml_confirm.value:
            return
        self.ui_busy = True
        self.clear_photo()
        self.completed, self.elapsed = 0, 0
        self.started = time.monotonic()
        self.activity.start()
        self.done_text.value = "0"
        self.progress.value, self.progress_text.value = 0, "0%"
        for index, (row, state) in enumerate(self.rows):
            row.bgcolor, row.border = FIELD, ft.Border.all(1, FIELD)
            state.value, state.color = "In coda", MUTED
            self.row_indicators[index].content = ft.Icon(ft.Icons.RADIO_BUTTON_UNCHECKED, size=12, color="#526478")
        self.status("In esecuzione", "Preparazione sequenza…", BLUE)
        self.log("Script", f"Avvio {self.script.name}" + (" [DEMO]" if self.is_demo else ""))
        self.refresh()
        try:
            if isinstance(self.runner.backend,RealBackend):
                result = await self.runner.run(self.script,legacy_confirmed=self.legacy_xml_confirm.value)
            else:
                result = await self.runner.run(self.script)
            if result == "stopped":
                self.current_text.value = "Sequenza interrotta"
                self.status("Interrotta", "Arresto della sequenza completato.", AMBER)
                self.log("Arresto", "Sequenza interrotta dall'operatore.")
                self.mark_current("Interrotto", AMBER)
                self.activity.set_phase("stopped", "Sequenza interrotta", title="Esecuzione interrotta",
                                        detail="Arresto della sequenza completato.", active=False, color=AMBER)
            else:
                self.log("Script", "Sequenza e rientro completati" + (" [DEMO]." if self.is_demo else "."))
                await self.finish_with_photo()
        except PhotoError as exc:
            self.activity.set_phase("error", "Foto non disponibile", title="Sequenza eseguita",
                detail="Acquisizione o ricezione dell'immagine non completata.", active=False, color=AMBER)
            self.current_text.value = "Sequenza eseguita · foto non disponibile"
            self.photo_info.value = str(exc)
            self.error(str(exc))
            self.status("Foto non disponibile", "Sequenza e rientro completati. Verificare il dettaglio dell'errore di acquisizione.", AMBER)
        except Exception as exc:
            self.activity.set_phase("error", "Errore di esecuzione", title="Sequenza non completata",
                                    detail=str(exc), active=False, color=RED)
            self.mark_current("Errore", RED)
            self.current_text.value = "Sequenza terminata con errore"
            self.error(f"{exc} Nuova inizializzazione richiesta prima del riavvio. Rientro non confermato.")
        finally:
            self.elapsed = time.monotonic() - self.started
            minutes, seconds = divmod(int(self.elapsed), 60)
            self.elapsed_text.value = f"{minutes:02d}:{seconds:02d}"
            self.started = None
            self.active_index = None
            self.ui_busy = False
            self.legacy_xml_confirm.value = False
            self.refresh()

    def stop(self, e=None):
        if self.runner.phase == "running" and not self.runner.stop.is_set():
            self.runner.request_stop()
            self.activity.set_phase("stopping", "Arresto richiesto", title="Arresto della sequenza",
                detail="Attesa del comando in corso, seguita dal rientro.", color=AMBER)
            self.status("Arresto richiesto", "Comando in corso: rientro previsto al termine.", AMBER)
            self.log("Arresto", "Richiesta ricevuta; il comando già inviato deve terminare.")
            self.refresh()

    def mark_current(self, text, color):
        if self.active_index is not None and self.active_index < len(self.rows):
            row, state = self.rows[self.active_index]
            state.value, state.color = text, color
            row.border = ft.Border.all(1, color)
            self.row_indicators[self.active_index].content = ft.Icon(
                ft.Icons.ERROR_OUTLINE_ROUNDED if color == RED else ft.Icons.STOP_ROUNDED,
                size=16, color=color)

    def on_runtime(self, kind, **data):
        if kind == 'origin_changed':
            self.legacy_xml_confirm.value = False
            self.calibration_ui.reset()
            self.move_ui.reset()
            self.press_ui.reset()
            if self.vision.observer:
                self.vision.observer.invalidate_calibration()
        elif kind == 'initialized':
            backend = self.runner.backend
            if (not self.is_demo and self.runner.initialized and hasattr(backend, 'session')
                    and self.vision.observer and hasattr(self.vision.observer, 'bind_experimental_origin')):
                status = backend.session.status()
                if status.get('homed') and status.get('connection') == 'connected':
                    self.vision.observer.bind_experimental_origin(status['origin_epoch'])
        elif kind == 'robot_status':
            self.log('Robot',str(data['status']))
        elif kind == 'move_only_result':
            result = data['result']
            self.log('Movimento simulato' if result['simulation'] else 'Movimento commissioning',str(result))
            self.axis_x.value,self.axis_y.value = map(str,result['command_xy_mm'])
        elif kind == 'press_result':
            result = data['result']
            self.log('Pressione simulata' if result['simulation'] else 'Pressione fisica',str(result))
            self.axis_x.value,self.axis_y.value = map(str,result['command_xy_mm'])
        elif kind == "status":
            self.status_text.value = data["text"]
        elif kind == "transmit":
            name, args = data["name"], data["args"]
            self.activity.transmit(name, args, self.runner.phase)
            if name in ("MOVE", "MOVE_AND_CLICK"):
                self.axis_x.value, self.axis_y.value = str(args[0]), str(args[1])
            self.log("TX demo" if self.is_demo else "TX", f"{name} {list(args)}")
        elif kind == "command_start":
            index, command = data["index"], data["command"]
            self.activity.start_command(index, command)
            self.active_index = index
            row, state = self.rows[index]
            row.bgcolor = "#1A3433"
            row.border = ft.Border.all(1, "#527F72")
            self.row_indicators[index].content = ft.ProgressRing(width=16, height=16, stroke_width=2, color=ACCENT)
            state.value, state.color = "In corso", ACCENT
            self.current_text.value = f"{index + 1:02d} / {len(self.script.commands):02d}   {command.action} · {command.target}"
            self.status_text.value = command.detail
            self.page.run_task(self.scroll_to_command, index)
        elif kind == "command_done":
            self.activity.command_done(data["index"])
            row, state = self.rows[data["index"]]
            row.bgcolor, row.border = "#112722", ft.Border.all(1, "#203D34")
            state.value, state.color = "Eseguito", ACCENT
            self.row_indicators[data["index"]].content = ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=16, color=ACCENT)
            self.active_index = None
            self.completed = data["index"] + 1
            self.done_text.value = str(self.completed)
            self.progress.value = self.completed / len(self.script.commands)
            self.progress_text.value = f"{self.progress.value:.0%}"
        self.refresh()

    async def scroll_to_command(self, index):
        if not self.disposed:
            await self.command_list.scroll_to(offset=max(0, index * 59 - 70), duration=160)

    async def clock(self):
        while not self.disposed:
            now = time.monotonic()
            previous = self.communication.status.value
            self.communication.refresh()
            if previous != self.communication.status.value:
                self.page.update(self.communication.control)
            changed = self.activity.tick(now)
            if self.started is not None:
                self.elapsed = now - self.started
                minutes, seconds = divmod(int(self.elapsed), 60)
                elapsed = f"{minutes:02d}:{seconds:02d}"
                changed |= self.elapsed_text.value != elapsed
                self.elapsed_text.value = elapsed
            if self.activity.active:
                self.status_dot.scale = 1.2 if int(now * 2) % 2 else 0.85
                self.status_dot.opacity = 1 if int(now * 2) % 2 else 0.5
            if changed:
                # Do not diff the whole command table on each animation frame.
                self.page.update(self.activity.control, self.status_dot, self.elapsed_text)
            await asyncio.sleep(0.12 if self.activity.active else 0.25)

    def error(self, text):
        self.status("Errore", text, RED)
        self.log("Errore", text)
        self.page.show_dialog(ft.AlertDialog(title=label("Operazione non riuscita", 20),
            content=label(text, 14), bgcolor=SURFACE,
            actions=[ft.TextButton("Chiudi", on_click=lambda e: self.page.pop_dialog())]))
        self.refresh()

    def help_dialog(self, e=None):
        self.page.show_dialog(ft.AlertDialog(title=label("Guida rapida", 22), bgcolor=SURFACE,
            content=ft.Container(ft.Column([
                label("1. Select SENSE TOUCHSCREEN / superiore or TWINS / inferiore (preview only), then your environment.", 14),
                label("2. Hardware: enter the Pi camera URL and Start camera. Demo: use a recording.", 14),
                label("3. Search 5 and click Key 5 to inspect current camera pixels and estimated robot XY.", 14),
                label("4. Open Calibration to enter independently measured X/Y and collect fit/check controls.", 14),
                label("Select a fresh detected button, click Move and click, then confirm readiness for one 100 ms press. Calibration, robot readiness and movement limits are rechecked; no move-only test or alignment form is required.", 13, AMBER),
                ft.Divider(color=LINE),
                label("Demo", 14, ACCENT, ft.FontWeight.W_600),
                label("La demo non apre connessioni e simula gli esiti dei comandi.", 13, MUTED),
                label("Hardware", 14, ACCENT, ft.FontWeight.W_600),
                label("Open Robot connection and homing for the explicit robot JSON and ACK controls. "
                      "A matching adequate calibration and independent bounds are required for one commissioning move.", 13, MUTED),
                label("Arresto · tasto Esc", 14, AMBER, ft.FontWeight.W_600),
                label("Interrompe la sequenza dopo il comando in corso e richiede MOVE [0,0,0]. "
                      "Non interrompe i motori a metà movimento. In caso di errore non viene "
                      "inviato un rientro automatico.", 13, MUTED),
                label("Le coordinate mostrate sono richieste al controller, non misure reali.", 12, MUTED),
            ], spacing=12, tight=True, scroll=ft.ScrollMode.AUTO), width=440),
            actions=[ft.TextButton("Chiudi", on_click=lambda e: self.page.pop_dialog())]))

    def clear_log(self, e=None):
        self.log_lines.clear()
        self.log_view.controls.clear()
        self.page.update()

    async def export_log(self, e=None):
        try:
            path = await self.save_picker.save_file(dialog_title="Esporta registro eventi",
                file_name=f"TapperWare_{datetime.now():%Y%m%d_%H%M%S}.log")
            if path:
                text = "TapperWare · registro sessione\n" + "\n".join(self.log_lines) + "\n"
                await asyncio.to_thread(Path(path).write_text, text, encoding="utf-8")
                self.log("Sistema", "Registro esportato.")
                self.page.update()
        except Exception as exc:
            self.error(f"Esportazione registro: {exc}")

    def keyboard(self, e):
        if e.key == "Escape":
            self.stop()

    async def window_event(self, e):
        if e.type == ft.WindowEventType.CLOSE:
            if self.locked:
                self.page.show_dialog(ft.AlertDialog(title=label("Operazione in corso", 20),
                    content=label("Chiusura disponibile al termine dell'operazione. Per interrompere la sequenza usare Arresta.", 14),
                    actions=[ft.TextButton("Torna alla console", on_click=lambda e: self.page.pop_dialog())]))
            else:
                # Keep UI clocks alive until cleanup succeeds. A timed-out
                # native worker may require the operator to retry closure.
                self.ui_busy = True
                self.vision.invalidate()
                self.clear_vision()
                self.refresh()
                try:
                    await asyncio.to_thread(self.vision.close)
                    await self.runner.disconnect()
                except Exception as exc:
                    self.ui_busy = False
                    self.error(str(exc))
                    return
                self.disposed = True
                self.runner.shutdown()
                await self.page.window.destroy()

    def disconnect(self, e=None):
        self.vision.invalidate()
        self.page.run_task(self.close_vision_after_disconnect)
        self.runner.request_stop()
        self.activity.active = False
        self.disposed = True
        # The executor queues socket cleanup after any bounded in-flight call;
        # never cancel it or create a second owner while its outcome is pending.
        self.runner.shutdown()

    async def close_vision_after_disconnect(self):
        try:
            await asyncio.to_thread(self.vision.close)
        except RuntimeError:
            pass  # Invalidated already; process teardown releases a blocked device.


def launch():
    parser = argparse.ArgumentParser(description="TapperWare · Flet DMI Control")
    parser.add_argument("--demo", action="store_true", help="Simula senza collegare hardware")
    parser.add_argument("--web", action="store_true", help="Anteprima browser, solo demo")
    parser.add_argument("--port", type=int, default=8550, help="Porta dell'anteprima web locale")
    parser.add_argument("--native-drop", action="store_true", help="Richiede client compilato con flet-dropzone")
    args = parser.parse_args()

    async def main(page: ft.Page):
        DmiControlPanel(page, demo=args.demo or args.web, native_drop=args.native_drop)

    if args.web:
        ft.run(main, view=ft.AppView.WEB_BROWSER, host="127.0.0.1", port=args.port)
    else:
        ft.run(main)


if __name__ == "__main__":
    launch()
