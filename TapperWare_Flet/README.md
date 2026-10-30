# TapperWare · interfaccia Flet

## SENSE live observation (Step 11, offline implementation)

Run this GUI from its place in the complete repository; the vision and integration
packages and `dmi_computer_vision/data/icons/` are required. Install
`python -m pip install -r TapperWare_Flet/requirements.txt` in the same environment.
The existing OCR engine (Tesseract with English data) is also required; see the
vision package README. Launch from any directory using an absolute path:
`python /path/to/DMI_R-D_ALTEN/TapperWare_Flet/main.py --demo`.

Select **SENSE TOUCHSCREEN**, panel **superiore**, then enter an absolute recording
path in **Visione SENSE** and press **Avvia osservazione**. Demo/browser accepts
recordings only and never opens a real camera. Replay uses the recording's native
resolution and encoded FPS; playback timing is not camera cadence or a latency
benchmark. The live camera frame and matching annotated detection frame are
separate; slow analysis may leave the former updating while the latter expires.
Results older than 1.5 seconds (including supplied upstream age) lose their targets
and annotation. Stop, EOF, source/analysis failure and model/panel/environment
changes clear observations. Stop workers before starting another session.

For later hardware observation, launch without `--demo`, choose the bridge source
and enter the deployed HTTP(S) `/frame.jpg` URL, or choose a local camera and enter
its acquisition index (SENSE camera 1 on the documented setup). No camera opens
until observation starts. Receiver orientation is unchanged (rotation 0, no mirror);
the bridge must supply correctly oriented frames. Check actual camera identity,
mount/settings and network configuration independently. No live hardware connection
or installed-camera performance has been validated by Step 11.

Optional calibration and independent context JSON paths can be supplied before
starting. Context has `camera` and `origin` objects using the existing calibration
schema. Do not copy a historical model's context as proof of current mounting or
origin. The resolver checks source kind/path or endpoint, size and measured
geometry. The Step 10 rejected models can show mathematically predicted XY only
when replay/context/geometry match; they remain unverified and unusable. Mismatches
show an explicit calibration error and no XY. No GUI panel Y offset is added to
calibrated XY. All Step 11 target selections are inspection only: select again for
the current observation; coordinates in older UI rows cannot authorize movement.
There are no vision Move, Press or Hold controls in this step.

Mode observation uses paired white `modes/box_14` and yellow `modes/box_16`
templates, with `modes/power.bmp` as the default white icon. Identity names such as
`mode_01` refer to the supplied asset pair, not an inferred operational mode name.
Only measured joined-monitor regions are eligible. A bounded time-based history
reports pending, blinking, temporary blink-off, power, steady or unknown. Blink-off
retains its last direct-evidence timestamp; loss, ambiguity, geometry movement or
a capture gap clears history. Steady requires repeated white evidence with an
observed empty yellow box. These states are observations, not acknowledgement or
press success. Natural blinking footage and physical hold verification remain
pending; the five-second hold belongs to Step 14.
`replacement_verified` separately requires the same confirmed blinking identity
and prior direct power evidence, followed by steady white/empty yellow evidence.
Different white identities, reset/loss and expired blink history cannot verify
that replacement. The transition association expires eight seconds after direct
blink confirmation; blink-off never renews it. Geometry is checked against the
history's anchored basis, including cumulative movement.
Power must still be visible when blinking is confirmed. An intervening different
white icon cancels the pending replacement, including a later return to the old
blinking identity.

Runtime communication is bounded in memory; no per-frame JSON transfer is needed.
The optional JSONL debug checkbox appends detailed evaluation results to ignored
`dmi_robot_config/local/vision_debug.jsonl`; leave it off for ordinary observation.
Displayed FPS is local analysis throughput, and P95 covers the latest 256 analyses;
it is not measured camera FPS or GUI paint rate. Source buffers may also overwrite
frames beyond the GUI observer's own overwrite counter.

Legacy hardware initialization/XML/photo acquisition is blocked while observation
workers are active to avoid a second command/camera owner before Step 12. Stop
observation to use those existing controls. Demo XML remains simulated. Existing
legacy hardware behavior has not been commissioned by this change. Guided fitting,
shared UDP ownership, movement and pressing are separate later steps.

Nuova console desktop in italiano: fondo blu scuro, accenti verde menta, pannelli separati per postazione e sequenza, anteprima comandi, avanzamento, tempo trascorso e registro eventi esportabile.

La versione 2.2 aggiunge un monitor animato dell'esecuzione e messaggi operativi
più professionali. Conserva foto automatica, visualizzatore, impostazioni
persistenti e selezione del pannello con offset Y configurabile.

## Avvio rapido

Richiede Python 3.10 o successivo. Apri un terminale nella cartella estratta:

```console
python -m pip install -r requirements.txt
python DmiGUI.pyw --demo
```

In demo, premi **Carica esempio**, **Inizializza demo**, poi **Avvia sequenza**.
`python main.py --demo` è equivalente: entrambi gli avvii standard funzionano
senza l'estensione per il trascinamento.
Su Windows puoi usare anche `Avvia_DEMO.bat` dopo aver installato le dipendenze.
La demo non importa i moduli hardware e non apre connessioni al robot.
La pressione ACK del file di esempio dura 5 secondi anche in demo.

È fissata la versione Flet **1.0.4**. Il codice usa le API di questa versione;
è stata verificata anche la compatibilità con **Flet 0.82.2**. Flet 0.28 non è supportato.
Pillow è incluso nelle dipendenze per leggere e visualizzare le immagini scaricate.

### Aggiornamento alla versione con animazioni

Sostituisci i file dell'applicazione con quelli di questo archivio, includendo
**dmi_activity.py**, **dmi_settings.py**, **dmi_photos.py** e **requirements.txt**.
Le animazioni usano Flet e non richiedono estensioni aggiuntive. Per allineare le dipendenze:

```console
python -m pip install -r requirements.txt
```

Conserva i tuoi moduli hardware, `pc_cfg.yaml`, eventuali modifiche a
`DmiPositions.json` e il file `TapperWare.settings.json`, se già presente.
L'archivio non contiene un file di impostazioni dell'operatore.

### Correzione FilePicker

La versione corretta crea `FilePicker()` senza `on_result`, registra i servizi
nella pagina e carica i file restituiti da `await pick_files()` sul desktop.
Nel browser usa l'evento solo se l'API `PickFiles` è disponibile; altrimenti usa
il selettore asincrono con lettura del contenuto. È compatibile anche il bordo
del menu DMI, la cui API è cambiata tra le due versioni di Flet.

La correzione è inclusa anche in questa versione. Segui le istruzioni di
aggiornamento sopra per includere i nuovi moduli delle foto e delle impostazioni.

### Correzione avvio standard

La prima versione di `main.py` attivava il trascinamento nativo obbligatoriamente.
È stato corretto: ora `main.py` e `DmiGUI.pyw` usano lo stesso avvio standard.
Mantieni aggiornati anche **main.py** e **pyproject.toml**, che rende
l'estensione opzionale.
Anche una richiesta esplicita `--native-drop` con estensione assente lascia
ora aprire la console e segnala di usare **Sfoglia file**.

## Uso con il tuo progetto hardware

Copia nella cartella del progetto questi file:

- `DmiGUI.pyw` — nuovo punto di avvio, sostituisce la GUI Tkinter.
- `dmi_gui.py` — interfaccia Flet.
- `dmi_runtime.py` — validazione XML ed esecuzione dei comandi.
- `dmi_settings.py` — opzioni e offset per pannello.
- `dmi_photos.py` — attesa del download, lettura e anteprima foto.
- `dmi_activity.py` — monitor animato dell'esecuzione.

Installa le dipendenze di `requirements.txt` nello stesso ambiente Python usato dal progetto.
Devono rimanere disponibili i tuoi moduli originali e le loro dipendenze:

```text
YamlCfg.py
ComProtocol.py
Logger.py
DmiMessages.py
DmiControllerMaster.py
pc_cfg.yaml
DmiPositions.json
```

Questi moduli e la configurazione YAML non erano allegati e non sono stati ricreati.
`DmiPositions.json` e `test.xml` nel pacchetto sono copie inalterate degli allegati.
I percorsi di JSON e YAML vengono risolti dalla cartella dell'applicazione,
indipendentemente dalla cartella dalla quale viene lanciato Python.

```console
python DmiGUI.pyw
```

Puoi anche usare `Avvia_HARDWARE.bat`. L'avvio predefinito è in modalità hardware;
se manca un modulo o il controller non risponde, viene mostrato un errore.
Il programma non passa automaticamente alla demo.

La connessione viene creata quando premi **Inizializza hardware**.
Sono conservate le chiamate originali a `ComProtocol`, `DmiControllerMaster.Action`
e `manage_action`, con gli stessi messaggi ACK, INITIALIZE, MOVE e MOVE_AND_CLICK.
La comunicazione gira su un solo worker dedicato: le chiamate sono seriali e
la finestra rimane disponibile durante le attese del controller.

## Monitor animato dell'esecuzione

Il riquadro **Monitor esecuzione**, sopra l'elenco dei comandi, mostra:

- Cursore animato su una griglia, con spostamenti fra le coordinate richieste e
  impulso visivo durante l'invio dei comandi di pressione.
- Step attivo, destinazione, dettaglio operativo e avanzamento a segmenti.
- Indicazione delle fasi di inizializzazione, posizionamento, pressione, attesa,
  rientro, acquisizione e ricezione della foto.
- Scansione animata durante l'acquisizione e il download; conferma visiva
  del completamento solo al termine dell'operazione.

La riga dello step in corso presenta un indicatore di attività e una transizione
di colore; alla conferma del controller mostra un segno di spunta. Un indicatore
rimane visibile anche nella barra dei comandi in basso. Arresto ed errore
terminano gli indicatori di esecuzione.

La griglia è uno **schema dei comandi richiesti**, adattato alle coordinate della
sequenza, incluso l'offset del pannello. Non è una misura o una simulazione
cinematica della posizione reale. Gli impulsi sono un riscontro visivo del
comando inviato, non una conferma fisica di contatto con il pannello.

Le animazioni usano transizioni native di Flet e un aggiornamento grafico
separato dalla comunicazione. Non aggiungono pause ai comandi né cambiano
coordinate, durate, ordine delle chiamate o gestione dell'arresto. Durante le
animazioni vengono aggiornati solo il monitor e gli indicatori, senza
ridisegnare l'intera tabella a ogni fotogramma.

I messaggi della console sono stati uniformati: **In attesa di una sequenza**,
**Sequenza validata**, **In corso**, **Eseguito**, **Operazione completata**.

## Foto automatica e impostazioni

Apri **Impostazioni** dall'ingranaggio in alto a destra e indica la cartella
in cui il tuo `GET_PICTURES` scarica le immagini. Puoi scrivere il percorso
oppure usare **Scegli cartella** sul desktop. I percorsi relativi vengono
risolti rispetto alla cartella dell'applicazione.

La GUI usa il percorso per cercare i file: la destinazione effettiva di download
rimane gestita dai tuoi moduli `DmiControllerMaster` / `ComProtocol`, che non
erano allegati. Non viene modificata una configurazione di download sconosciuta.

Alla fine di ogni sequenza XML riuscita, **dopo il rientro all'origine**, vengono
eseguite in ordine queste chiamate, sullo stesso worker dei movimenti:

```python
dmi_controller.manage_action(
    DmiControllerMaster.Action(DmiMessages.TAKE_PICTURES, [0, 1, 1], DmiMessages.DONE, 0)
)
dmi_controller.manage_action(
    DmiControllerMaster.Action(DmiMessages.GET_PICTURES, [], DmiMessages.PICTURE)
)
```

L'esito viene verificato dopo ciascuna chiamata. Se TAKE_PICTURES fallisce,
GET_PICTURES non viene accodato. Una sequenza arrestata o con errore di movimento
non avvia l'acquisizione.

Prima dell'acquisizione viene registrato lo stato della cartella. Dopo
GET_PICTURES la GUI attende una foto nuova o modificata, sceglie la più recente
per data di modifica e verifica che sia stabile e leggibile. Sono supportati
JPEG, PNG, BMP, GIF, WebP e TIFF; è prevista anche la sovrascrittura dello
stesso nome file. L'anteprima viene ridimensionata, mentre il file scaricato
resta invariato.

La foto si apre automaticamente in una finestra con la scritta
**Operazione completata** e rimane nel riquadro della console. Facendo clic
sull'anteprima la puoi riaprire. Il pulsante **Apri ultima foto** apre invece
manualmente l'immagine più recente già presente nella cartella.

Nelle impostazioni puoi modificare anche il tempo di attesa del file
(predefinito 15 secondi, da 1 a 120) e abilitare la ricerca nelle sottocartelle.
Il tempo di attesa inizia dopo il ritorno di GET_PICTURES; il timeout di
`manage_action` continua a dipendere dal tuo controller.

Se la foto non arriva, non viene mostrata una vecchia immagine come risultato:
la console segnala **Sequenza eseguita · foto non disponibile**. Un problema
della sola fotocamera non invalida l'homing già confermato. Se non hai ancora
configurato la cartella, i comandi foto vengono comunque eseguiti e il programma
ti invita a impostarla per aprire l'immagine.

In demo i due comandi sono simulati. Se nella cartella c'è già una foto, viene
mostrata con l'indicazione **DEMO · foto esistente**; non viene dichiarato un
download reale e non viene creata una falsa foto del collaudo.

## Pannello superiore / inferiore

Il menu **Pannello** si trova nella sezione Postazione. Nelle Impostazioni scegli
il valore dell'offset Y in millimetri (intero, anche negativo) e quale pannello
deve riceverlo. L'altro pannello mantiene X e Y del JSON.

Poiché la richiesta originale indicava due volte «inferiore», l'associazione
è configurabile. I valori iniziali sono:

| Pannello | X | Y |
| --- | --- | --- |
| Inferiore | X del JSON | Y del JSON |
| Superiore | X del JSON | Y del JSON + offset |

L'offset iniziale è **0 mm**. Puoi invertire l'associazione con **Applica l'offset a**.
Il cambio pannello o offset ricompila l'anteprima della sequenza: l'offset si applica
ai movimenti di PRESS, MOVE_TO e WRITE_T9; durate e coordinata X restano inalterate.
Il comando finale di rientro resta sempre `MOVE [0, 0, 0]`.

Cartella, offset, associazione e pannello selezionato vengono salvati in
`TapperWare.settings.json` accanto all'applicazione, senza riscrivere
`DmiPositions.json`. Queste opzioni sono bloccate durante l'esecuzione e
l'acquisizione delle foto.

## Funzioni

- Selezione di SENSE TOUCHSCREEN, SENSE SOFTKEY, TWINS e STEN.
- Selezione del pannello superiore/inferiore con offset Y persistente.
- Acquisizione foto a fine sequenza, attesa del download e visualizzazione automatica.
- Segnalazione delle mappe mancanti. Nel JSON fornito è configurato solo SENSE TOUCHSCREEN.
- Selezione XML tramite finestra nativa e caricamento rapido di `test.xml`.
- Validazione dell'intera sequenza prima di abilitarne l'esecuzione.
- Anteprima con azione, tasto, coordinate, durata e stato di ogni comando.
- Indicatore di avanzamento, conteggio dei comandi completati e cronometro.
- Monitor animato di movimenti, pressioni, step e acquisizione fotografica.
- Visualizzazione delle ultime coordinate **richieste**: non sono una misura della posizione reale.
- Registro con 160 righe visibili e un massimo di 2.000 righe esportabili in `.log`.
- Blocco di modello, ambiente, file e inizializzazione durante le operazioni.
- Arresto da pulsante o tasto **Esc**.
- Blocco della chiusura ordinaria della finestra finché un'operazione è in corso.
- Layout a due colonne sulle finestre ampie; colonne impilate quando lo spazio si riduce.

## Comportamento di arresto ed errore

**Arresta è un arresto della sequenza, non un arresto di emergenza dei motori.**
Non è disponibile, negli allegati, un comando di interruzione del movimento sullo Slave.

Quando premi Arresta, il programma attende l'esito del comando già inviato,
non invia i successivi e richiede `MOVE [0, 0, 0]`. Il ritorno viene considerato
completato solo se il controller restituisce esito positivo. Anche a fine
sequenza viene eseguito e controllato lo stesso rientro.

Le attese XML sono interrompibili. Una chiamata `manage_action` già in corso,
invece, dipende dai timeout implementati nei tuoi moduli. La GUI non finge di
annullarla e non lancia un secondo comando in parallelo.

In caso di errore o timeout durante inizializzazione, movimenti o rientro, la sequenza termina, l'inizializzazione
viene invalidata e **non** viene accodato un movimento automatico di rientro:
l'esito del movimento precedente potrebbe essere incerto. Occorre verificare
la postazione e reinizializzarla. Questa gestione è diversa dall'originale,
che ignorava diversi valori di ritorno di `manage_action`.

## XML supportato

```xml
<?xml version="1.0" encoding="UTF-8"?>
<sequence>
    <command action="PRESS" target="KEY_1" />
    <command action="MOVE_TO" target="KEY_2" />
    <command action="WRITE_T9" target="AB12" />
    <command action="WAIT" duration="250" />
</sequence>
```

`duration` è in millisecondi; per WAIT il valore predefinito è 1000.
PRESS usa la durata del tasto, altrimenti quella del modello e infine 200 ms.
T9 mantiene le pressioni da 40 ms, la pausa fra click da 20 ms e la pausa da
300 ms fra caratteri consecutivi sullo stesso tasto.

Azioni sconosciute, tasti assenti, caratteri T9 non supportati, XML malformati
e durate non valide sono rifiutati prima dell'avvio. L'originale saltava alcuni
di questi errori durante l'esecuzione. I riferimenti `leads_to` vengono risolti
sia per nome della schermata sia tramite il suo `parent`; MOVE_TO non simula
una pressione e quindi non cambia la schermata logica.

Lo script visualizzato viene mantenuto come piano immutabile: modifiche esterne
al file o al JSON richiedono di ricaricarlo. Limiti: 2 MB per XML, 5.000 comandi,
4.096 caratteri per ciascun WRITE_T9. DTD ed entità personalizzate non sono ammesse.

## Trascinamento dei file: opzione aggiuntiva

Nel client Flet standard usa **Sfoglia file**. Il trascinamento di file esterni
richiede l'estensione `flet-dropzone` e la compilazione di un client che la includa.
L'entry point dedicato è **main_native_drop.py**; **main.py** rimane l'avvio standard.

Su Windows, con la toolchain di compilazione Flet/Flutter installata:

Per includere l'estensione nel client compilato, aggiungi
`"flet-dropzone==0.4.0"` all'elenco `project.dependencies` di `pyproject.toml`
oltre alla dipendenza Flet esistente, quindi:

```console
python -m pip install "flet[all]==1.0.4" "flet-dropzone==0.4.0"
flet build windows --module-name main_native_drop
```

Esegui il client prodotto in `build/windows`. Prima di compilare per l'uso
hardware, inserisci anche i moduli originali, `pc_cfg.yaml` e le rispettive
dipendenze Python nel progetto. Il client compilato parte in ambiente hardware;
puoi selezionare Demo dall'interfaccia. Non è incluso un eseguibile Windows
precompilato. La build dell'estensione e il trascinamento nativo non sono stati
collaudati su questo ambiente.

## Anteprima browser facoltativa

```console
python -m pip install "flet[web]==1.0.4"
python DmiGUI.pyw --web
```

L'anteprima è locale su `127.0.0.1:8550`, sempre in demo. La modalità hardware
è disabilitata nel browser. Il caricamento XML usa il contenuto del file
selezionato; l'esportazione del registro è disponibile nella versione desktop.
Su Linux, la finestra di scelta file del client desktop richiede Zenity.

## Verifiche effettuate

La suite inclusa verifica le coordinate e i tempi dell'XML allegato, la
validazione degli errori, il T9, le attese frazionarie, la serializzazione
delle chiamate al controller, l'arresto durante un movimento, gli errori
di inizializzazione/esecuzione/rientro e il cambio di modalità.

Verifica inoltre la costruzione e serializzazione dei controlli con Flet 0.82.2 e 1.0.4
e il flusso dell'interfaccia: carica, inizializza, esegui, cambia modello,
gestisci errore, rimuovi file. Sono verificati anche il caricamento tramite
FilePicker, l'annullamento del dialogo e il blocco del caricamento durante una
sequenza, nei percorsi desktop e browser. Il trasporto grafico è simulato in questi test.

La suite aggiornata comprende **58 test**, passati su entrambe le versioni
Flet. Include salvataggio e validazione delle opzioni, offset su PRESS/MOVE_TO/T9,
assenza di modifiche al JSON, rientro senza offset, firme esatte delle azioni foto,
ordine dei comandi, gestione di errori della fotocamera, nuove immagini e
sovrascritture, file incompleti, mancato download e serializzazione delle
finestre di impostazioni e delle anteprime immagine. I test del monitor
verificano l'aggiornamento durante una chiamata al controller in attesa,
l'arresto delle animazioni dopo un errore o un'interruzione e la conferma
finale solo dopo la ricezione dell'immagine.

```console
python -m pip install pytest
python -m pytest tests -q
```

Non è stato possibile completare l'ispezione visiva in una finestra nativa
in questo ambiente. Anche le finestre native di apertura/salvataggio,
la build Windows e il collegamento al robot restano da verificare sul PC
di destinazione. Non è una dichiarazione di collaudo dell'hardware.

## Riferimenti tecnici

- [API e migrazione a Flet 1.0](https://flet.dev/docs/updates/migrate-to-1-0/)
- [FilePicker](https://flet.dev/docs/services/filepicker/)
- [Animazioni Flet](https://flet.dev/docs/cookbook/animations/)
- [Compilazione Flet](https://flet.dev/docs/cli/flet-build/)
- [flet-dropzone](https://github.com/shiena/flet-dropzone)
