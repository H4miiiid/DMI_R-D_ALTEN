import os
import pathlib
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import xml.etree.ElementTree as ET

# Libreria per il Drag and Drop nativo in Tkinter
from tkinterdnd2 import TkinterDnD, DND_FILES 

# Importazioni dei tuoi moduli originali
from YamlCfg import YamlCfg
from ComProtocol import ComProtocol
from Logger import setup_logging, logger
from DmiMessages import DmiMessages
from DmiControllerMaster import DmiControllerMaster

class DmiControlPanel:
    def __init__(self, root):
        self.root = root
        self.root.title("TapperWare Interface")
        self.root.geometry("600x530") 
        self.root.configure(bg="#2b2b2b") 

        # Inizializzazione della configurazione hardware del Master
        self._init_hardware_controller()

        self.style = ttk.Style()
        self.style.theme_use('clam')
        self._configure_styles()

        self.selected_dmi = tk.StringVar()
        self.loaded_script_path = None
        
        # FLAG DI SICUREZZA
        self.hardware_initialized = False
        self.sequence_running = False  # Controlla lo stato di esecuzione dello script

        self._create_header()
        self._create_dmi_selector()
        self._create_hardware_tools() 
        self._create_drop_zone()
        self._create_footer()

    def _init_hardware_controller(self):
        """ Inizializza il canale di comunicazione con lo Slave (Raspberry Pi) """
        try:
            cfg_path = os.path.join(pathlib.Path(__file__).parent, "pc_cfg.yaml")
            cfg = YamlCfg(cfg_path)
            setup_logging(cfg.log_level, pathlib.Path(__file__).stem)
            
            self.com_protocol = ComProtocol(cfg.address, cfg.remote_address)
            self.dmi_controller = DmiControllerMaster(self.com_protocol.put_data, self.com_protocol.get_data)
            logger.info("DmiControllerMaster agganciato alla GUI con successo.")
        except Exception as e:
            messagebox.showerror("Errore Hardware", f"Impossibile inizializzare la comunicazione: {e}")
            self.dmi_controller = None

    def _configure_styles(self):
        self.style.configure('.', background='#2b2b2b', foreground='#ffffff')
        self.style.configure('TLabel', font=('Helvetica', 11), background='#2b2b2b', foreground='#e0e0e0')
        
        self.style.configure('TCombobox', 
                             font=('Helvetica', 11), 
                             arrowcolor='#00bcd4',       
                             background='#3c3f41',      
                             fieldbackground='#3c3f41', 
                             foreground='#ffffff')      
        
        self.style.map('TCombobox',
                       fieldbackground=[('readonly', '#3c3f41')],
                       foreground=[('readonly', '#ffffff')])

        self.root.option_add('*TCombobox*Listbox.background', '#3c3f41')
        self.root.option_add('*TCombobox*Listbox.foreground', '#ffffff')
        self.root.option_add('*TCombobox*Listbox.selectBackground', '#00bcd4')
        self.root.option_add('*TCombobox*Listbox.selectForeground', '#2b2b2b')

        # Stile pulsante Inizializzazione (Arancione/Giallo industriale)
        self.style.configure('Init.TButton', font=('Helvetica', 11, 'bold'), background='#d97706', foreground='white')
        self.style.map('Init.TButton', background=[('active', '#b45309')])

        # Stile Pulsante Run (Verde)
        self.style.configure('Run.TButton', font=('Helvetica', 12, 'bold'), background='#2d7d46', foreground='white')
        self.style.map('Run.TButton', background=[('active', '#1e522e')])

        # Stile Pulsante Stop (Rosso Industriale)
        self.style.configure('Stop.TButton', font=('Helvetica', 12, 'bold'), background='#c53030', foreground='white')
        self.style.map('Stop.TButton', background=[('active', '#9b1c1c')])

    def _create_header(self):
        header = tk.Label(self.root, text="TapperWare Interface", font=("Helvetica", 16, "bold"), bg="#2b2b2b", fg="#00bcd4")
        header.pack(pady=15)

    def _create_dmi_selector(self):
        frame = ttk.Frame(self.root)
        frame.pack(pady=5, fill='x', padx=40)
        ttk.Label(frame, text="Seleziona il modello di DMI:").pack(side='left', padx=5)

        dmi_models = ["SENSE TOUCHSCREEN", "SENSE SOFTKEY", "TWINS", "STEN"]
        self.dmi_combo = ttk.Combobox(frame, textvariable=self.selected_dmi, values=dmi_models, state="readonly", width=30)
        self.dmi_combo.pack(side='left', padx=10, fill='x', expand=True)
        self.dmi_combo.current(0)
        self.dmi_combo.bind("<<ComboboxSelected>>", lambda e: (self.dmi_combo.selection_clear(), self.root.focus()))

    def _create_hardware_tools(self):
        """ Crea la sezione per i comandi hardware diretti (es. Initialize) """
        frame = ttk.Frame(self.root)
        frame.pack(pady=10, fill='x', padx=40)

        self.btn_init = ttk.Button(
            frame, 
            text="INIZIALIZZA HARDWARE", 
            style='Init.TButton',
            command=self._hardware_initialize
        )
        self.btn_init.pack(fill='x', ipady=3)

    def _create_drop_zone(self):
        lbl = ttk.Label(self.root, text="Carica lo script:")
        lbl.pack(pady=(10, 5), anchor='w', padx=40)

        self.drop_frame = tk.Label(
            self.root,
            text="\nNessuno script caricato\n\nTrascina qui il file .xml\n\noppure\n\nCLICCA PER SFOGLIARE",
            font=("Helvetica", 11, "italic"),
            bg="#3c3f41",
            fg="#a9b7c6",
            bd=2,
            relief="groove", 
            justify="center",
            cursor="hand2"
        )
        self.drop_frame.pack(pady=5, fill='both', expand=True, padx=40)
        
        # Gestore Drag & Drop Nativo
        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind('<<Drop>>', self._on_file_drop)
        
        # Gestore Click Alternativo per Selezione Manuale
        self.drop_frame.bind("<Button-1>", self._browse_file)

    def _browse_file(self, event):
        """ Apre la finestra di dialogo nativa per selezionare il file se il drag & drop fallisce """
        if self.sequence_running:
            return # Blocca modifiche file durante l'esecuzione
        file_path = filedialog.askopenfilename(
            title="Seleziona Script di test XML",
            filetypes=[("Script di test XML", "*.xml"), ("Tutti i file", "*.*")]
        )
        if file_path:
            file_path = os.path.normpath(file_path).replace("\\", "/")
            self._activate_script(file_path)

    def _on_file_drop(self, event):
        """ Gestisce il percorso quando il file viene trascinato """
        if self.sequence_running:
            return
        file_path = event.data
        file_path = file_path.strip("'\"{}") 
        file_path = os.path.normpath(file_path).replace("\\", "/")
        self._activate_script(file_path)

    def _activate_script(self, file_path):
        """ Sotto-funzione comune per validare il file e sbloccare lo stato se l'hardware è pronto """
        if not file_path.lower().endswith('.xml'):
            messagebox.showerror("Errore File", "Formato non valido! Scegli solo file con estensione .xml")
            return

        raw_target = self.selected_dmi.get()
        dmi_target = f"DMI_{raw_target.replace(' ', '_')}"

        try:
            import json
            if not os.path.exists("DmiPositions.json"):
                messagebox.showerror("Errore Database", "Il file 'DmiPositions.json' non esiste nella cartella corrente!")
                return
                
            with open("DmiPositions.json", "r") as f:
                db = json.load(f)
                
            if dmi_target not in db:
                messagebox.showerror("Errore JSON", f"La chiave '{dmi_target}' non è stata trouvata dentro DmiPositions.json!")
                return
        except Exception as e:
            messagebox.showerror("Errore Lettura JSON", f"Impossibile validare il file JSON: {e}")
            return

        self.loaded_script_path = file_path
        filename = os.path.basename(file_path)
        
        self.drop_frame.configure(
            bg="#1e2d3d", 
            fg="#5cb85c",
            text=f"\n\nSCRIPT CARICATO CON SUCCESSO:\n\n[FILE]: {filename}",
            font=("Helvetica", 11, "bold")
        )
        
        # Gestione sblocco condizionale del pulsante Run
        if self.hardware_initialized:
            self.btn_run.configure(state="normal")
            self.btn_run.state(["!disabled"]) 
            self.status_label.configure(text=f"Script pronto: {file_path}", fg="#5cb85c")
        else:
            self.btn_run.configure(state="disabled")
            self.btn_run.state(["disabled"])
            self.status_label.configure(text=f"Script caricato. [ATTENZIONE] Inizializzare l'hardware prima di avviare!", fg="#d97706")
            
        logger.info(f"Script XML agganciato correttamente: {file_path}")

    def _create_footer(self):
        """ Crea la zona comandi inferiore affiancando Avvia e Arresta """
        footer_frame = ttk.Frame(self.root)
        footer_frame.pack(pady=15, padx=40, fill='x')

        # Configurazione griglia per rendere i pulsanti simmetrici
        footer_frame.columnconfigure(0, weight=1, uniform="buttons")
        footer_frame.columnconfigure(1, weight=1, uniform="buttons")

        # Pulsante AVVIA
        self.btn_run = ttk.Button(footer_frame, text="AVVIA SEQUENZA", style='Run.TButton', command=self._run_sequence, state="disabled")
        self.btn_run.grid(row=0, column=0, padx=5, sticky="ew", ipady=5)

        # Pulsante ARRESTA
        self.btn_stop = ttk.Button(footer_frame, text="ARRESTA SEQUENZA", style='Stop.TButton', command=self._stop_sequence, state="disabled")
        self.btn_stop.grid(row=0, column=1, padx=5, sticky="ew", ipady=5)

        self.status_label = tk.Label(self.root, text="Pronto. Inizializzazione hardware richiesta.", bd=1, relief="sunken", anchor="w", bg="#252525", fg="#d97706", font=("Helvetica", 9))
        self.status_label.pack(side="bottom", fill="x")

    def _stop_sequence(self):
        """ Richiama l'interruzione immediata del ciclo """
        if self.sequence_running:
            logger.warning("Richiesta di ARRESTO URGENTE intercettata dall'utente.")
            self.sequence_running = False

    def _check_and_handshake(self) -> bool:
        """ Verifica la connettività di rete mandando un ACK allo slave """
        start_handshake = time.time()
        while (time.time() - start_handshake) < 3.0:
            success, _ = self.dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.ACK, [], DmiMessages.ACK, 0, 1))
            if success:
                return True
            time.sleep(0.1)
            self.root.update()
        return False

    def _hardware_initialize(self):
        """ Invia il comando INITIALIZE reale allo slave sul Raspberry Pi """
        if not self.dmi_controller:
            messagebox.showerror("Errore Robot", "Connettività hardware non disponibile!")
            return

        self.status_label.configure(text="Sincronizzazione di rete con lo slave...", fg="#00bcd4")
        self.btn_init.configure(state="disabled") 
        self.root.update()

        if not self._check_and_handshake():
            messagebox.showerror("Errore Connessione", "Impossibile comunicare con il Raspberry Pi (Nessun ACK ricevuto).")
            self.status_label.configure(text="Disconnesso.", fg="#ff5555")
            self.btn_init.configure(state="normal")
            return

        self.status_label.configure(text="Inizializzazione hardware dei motori in corso...", fg="#00bcd4")
        self.root.update()

        success, _ = self.dmi_controller.manage_action(
            DmiControllerMaster.Action(DmiMessages.INITIALIZE, [], DmiMessages.DONE, 0)
        )

        if success:
            self.hardware_initialized = True
            self.status_label.configure(text="Hardware inizializzato con successo! (Assi azzerati)", fg="#5cb85c")
            
            if self.loaded_script_path:
                self.btn_run.configure(state="normal")
                self.btn_run.state(["!disabled"])
                self.status_label.configure(text=f"Script pronto per l'invio: {os.path.basename(self.loaded_script_path)}", fg="#5cb85c")
                
            messagebox.showinfo("Hardware Reset", "Il Raspberry Pi ha completato l'homing degli assi hardware correttamente!")
        else:
            self.hardware_initialized = False
            self.status_label.configure(text="Errore durante l'inizializzazione hardware.", fg="#ff5555")
            messagebox.showerror("Errore Robot", "Lo slave sul Raspberry Pi ha restituito un errore o è andato in timeout.")

        self.btn_init.configure(state="normal")

    def _run_sequence(self):
        """ Gestisce l'invio dei comandi con controllo real-time del flag di stop """
        if not self.hardware_initialized:
            messagebox.showerror("Sicurezza Robot", "Azione bloccata! Devi prima eseguire l'inizializzazione hardware per calibrare gli assi.")
            return

        if not self.dmi_controller:
            messagebox.showerror("Errore Robot", "Connettività hardware non disponibile!")
            return

        raw_target = self.selected_dmi.get()
        dmi_target = f"DMI_{raw_target.replace(' ', '_')}"
        script_xml = self.loaded_script_path
        
        try:
            import json
            with open("DmiPositions.json", "r") as f:
                db = json.load(f)
        except Exception as e:
            messagebox.showerror("Errore DB", f"Impossibile leggere DmiPositions.json: {e}")
            return

        if dmi_target not in db or not db[dmi_target]:
            messagebox.showerror("Errore DB", f"Il modello {dmi_target} non ha ancora coordinate mappate nel JSON.")
            return

        STAY_ON_POSITION = True

        T9_MAP = {
            '1': ['1', '.', '-', '+'], '2': ['2', 'A', 'B', 'C'], '3': ['3', 'D', 'E', 'F'],
            '4': ['4', 'G', 'H', 'I'], '5': ['5', 'J', 'K', 'L'], '6': ['6', 'M', 'N', 'O'],
            '7': ['7', 'P', 'Q', 'R', 'S'], '8': ['8', 'T', 'U', 'V'], '9': ['9', 'W', 'X', 'Y', 'Z'],
            '0': ['0', ' ']
        }

        self.status_label.configure(text="Verifica connessione prima dello script...", fg="#00bcd4")
        self.root.update()
        
        if not self._check_and_handshake():
            messagebox.showerror("Errore Sincronizzazione", "Nessun ACK ricevuto dal Raspberry Pi. Verifica che lo Slave sia attivo.")
            self.status_label.configure(text="Disconnesso.", fg="#ff5555")
            return

        try:
            tree = ET.parse(script_xml)
            root = tree.getroot()
            
            # --- SETUP STATO DI MARCIA GUI ---
            self.sequence_running = True
            self.btn_run.configure(state="disabled")
            self.btn_stop.configure(state="normal")
            self.btn_stop.state(["!disabled"])
            self.dmi_combo.configure(state="disabled")
            self.btn_init.configure(state="disabled")
            
            self.status_label.configure(text="Esecuzione script in corso...", fg="#00bcd4")
            self.root.update()

            dmi_data = db[dmi_target]
            current_screen = "DRIVER_ID_WINDOW"
            last_physical_button = None

            for cmd in root.findall('command'):
                # Controllo immediato del pulsante arresta
                if not self.sequence_running:
                    break

                action = cmd.attrib.get('action')
                target = cmd.attrib.get('target')

                # --- AZIONE SCRITTURA T9 ---
                if action == "WRITE_T9":
                    text_to_write = str(target).upper()
                    logger.info(f"Avvio scrittura testo T9: {text_to_write}")
                    
                    for char in text_to_write:
                        if not self.sequence_running:
                            break

                        target_button = None
                        clicks_needed = 1
                        
                        for num_key, chars_list in T9_MAP.items():
                            if char in chars_list:
                                target_button = f"KEY_{num_key}"
                                clicks_needed = chars_list.index(char) + 1
                                break
                        
                        if not target_button:
                            logger.warning(f"Carattere '{char}' non supportato. Salto.")
                            continue

                        if target_button == last_physical_button:
                            logger.info("Stesso tasto consecutivo. Attesa timeout (1.2s)...")
                            # Pausa frazionata per mantenere reattivo il tasto STOP
                            for _ in range(12):
                                if not self.sequence_running: break
                                time.sleep(0.1)
                                self.root.update()

                        if not self.sequence_running:
                            break

                        screen_info = dmi_data["screens"].get(current_screen)
                        if not screen_info or target_button not in screen_info["buttons"]:
                            for scr_name, scr_content in dmi_data["screens"].items():
                                if target_button in scr_content["buttons"]:
                                    current_screen = scr_name
                                    screen_info = scr_content
                                    break
                                    
                        if target_button in screen_info["buttons"]:
                            button_coords = screen_info["buttons"][target_button]
                            x = int(button_coords['x'])
                            y = int(button_coords['y'])
                            duration_ms = int(dmi_data.get("click_duration_ms", 200))
                            
                            logger.info(f"T9 Spostamento su {target_button} -> [{x}mm, {y}mm]")
                            self.dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [x, y, 0], DmiMessages.DONE, 0))
                            
                            for i in range(clicks_needed):
                                if not self.sequence_running:
                                    break
                                logger.info(f"T9 -> Click {i+1}/{clicks_needed} su {target_button}")
                                self.dmi_controller.manage_action(
                                    DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [x, y, duration_ms], DmiMessages.DONE, 0)
                                )
                                time.sleep(0.25)
                                self.root.update()
                        
                        last_physical_button = target_button
                    continue

                # --- AZIONI STANDARD (PRESS / MOVE_TO) ---
                elif action in ["PRESS", "MOVE_TO"]:
                    screen_info = dmi_data["screens"].get(current_screen)
                    if not screen_info or target not in screen_info["buttons"]:
                        found = False
                        for scr_name, scr_content in dmi_data["screens"].items():
                            if target in scr_content["buttons"]:
                                current_screen = scr_name
                                screen_info = scr_content
                                found = True
                                break
                        if not found:
                            logger.error(f"Tasto '{target}' non trovato per {dmi_target}")
                            continue

                    button_coords = screen_info["buttons"][target]
                    x = int(button_coords['x'])
                    y = int(button_coords['y'])
                    duration_ms = int(dmi_data.get("click_duration_ms", 200))
                    
                    if action == "PRESS":
                        if STAY_ON_POSITION:
                            logger.info(f"Spostamento fluido su {target} -> [{x}mm, {y}mm]")
                            self.dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [x, y, 0], DmiMessages.DONE, 0))
                            
                            if not self.sequence_running: break
                            
                            logger.info(f"Click sul posto su {target} -> [{duration_ms}ms]")
                            self.dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [x, y, duration_ms], DmiMessages.DONE, 0))
                        else:
                            logger.info(f"MOVE_AND_CLICK classico su {target}")
                            self.dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [x, y, duration_ms], DmiMessages.DONE, 0))
                    
                    elif action == "MOVE_TO":
                        logger.info(f"Inviando MOVE su {target}")
                        self.dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [x, y, 0], DmiMessages.DONE, 0))

                    if button_coords.get("leads_to"):
                        current_screen = button_coords["leads_to"]
                    
                    last_physical_button = target

                elif action == "WAIT":
                    duration = float(cmd.attrib.get('duration', 1000)) / 1000.0
                    # Fornisce una granularità fine all'attesa in modo da intercettare lo STOP istantaneamente
                    steps = int(duration / 0.1)
                    for _ in range(steps):
                        if not self.sequence_running: break
                        time.sleep(0.1)
                        self.root.update()
                
                self.root.update()

            # --- PARCHEGGIO DI SICUREZZA ORIGINE ---
            # Viene eseguito sia se lo script finisce normalmente, sia in caso di ARRESTA SEQUENZA
            logger.info("Frenata / Fine script rilevata. Parcheggio di sicurezza all'origine [0, 0, 0].")
            self.status_label.configure(text="Rientro hardware di sicurezza all'origine...", fg="#d97706")
            self.root.update()
            self.dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [0, 0, 0], DmiMessages.DONE, 0))

            # --- RIPRISTINO STATO INTERFACCIA ---
            was_interrupted = not self.sequence_running
            self.sequence_running = False
            self.btn_run.configure(state="normal")
            self.btn_stop.configure(state="disabled")
            self.dmi_combo.configure(state="readonly")
            self.btn_init.configure(state="normal")

            if was_interrupted:
                self.status_label.configure(text="Sequenza ANNULLATA dall'utente. Assi azzerati.", fg="#ff5555")
                messagebox.showwarning("Interruzione", "La sequenza è stata interrotta! Il robot è tornato in posizione di parcheggio in totale sicurezza.")
            else:
                self.status_label.configure(text="Test completato con successo.", fg="#5cb85c")
                messagebox.showinfo("Successo", "Esecuzione completata sul robot!")

        except Exception as e:
            self.sequence_running = False
            self.btn_run.configure(state="normal")
            self.btn_stop.configure(state="disabled")
            self.dmi_combo.configure(state="readonly")
            self.btn_init.configure(state="normal")
            messagebox.showerror("Errore Esecuzione", f"Si è verificato un errore nello script: {e}")
            self.status_label.configure(text="Errore Esecuzione.", fg="#ff5555")

if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = DmiControlPanel(root)
    root.mainloop()