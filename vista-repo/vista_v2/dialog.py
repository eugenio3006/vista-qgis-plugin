"""
Dialogo principale del plugin VISTA.
Tab: Calcolo ettometriche | Importa Foto | Importa Dati | Attribuzione progressiva | Revisione Foto | Report Word
"""

import os
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QPushButton, QCheckBox, QTextEdit,
    QGroupBox, QFormLayout, QFileDialog,
    QComboBox, QSpacerItem, QScrollArea, QProgressBar, QApplication,
    QButtonGroup, QRadioButton, QSpinBox, QDateEdit
)
from qgis.PyQt.QtCore import Qt, QDate
from qgis.PyQt.QtGui import QFont, QColor, QIcon, QPixmap
from .compat import (ALIGN_CENTER, ALIGN_RIGHT, ALIGN_VCENTER,
                     KEEP_ASPECT_RATIO, SMOOTH_TRANSFORM,
                     WIN_MAX_BTN, SCROLLBAR_AS_NEEDED, FRAME_NOFRAME,
                     FONT_BOLD, MSG_ICON_WARNING, MSG_ICON_QUESTION,
                     MSG_BTN_OK, MSG_BTN_YES, MSG_BTN_NO, exec_dialog)
from qgis.gui import QgsProjectionSelectionWidget
from qgis.core import QgsProject, QgsCoordinateReferenceSystem

from .core import (assegna_progressive, assegna_progressive_carreggiate, popola_codici,
                   genera_report_word, importa_dati_da_excel, importa_foto_da_cartella,
                   genera_ettometriche, parse_progressiva_metri, normalizza_comment,
                   _COMMENT_PAROLE)


def _primo_codice_title(title):
    """Primo codice difetto del Title, ignorando le parole puntuale/diffuso."""
    for tok in str(title).split():
        if tok.lower() not in _COMMENT_PAROLE:
            return tok
    return ""
from .codici_difetti import CODICI_DICT


# ---------------------------------------------------------------------------
# Dialog principale
# ---------------------------------------------------------------------------

class RoadInspectorDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent or iface.mainWindow())
        self.iface   = iface

        self.setWindowTitle("VISTA")
        self.setMinimumWidth(520)
        self.setWindowFlags(self.windowFlags() | WIN_MAX_BTN)
        # Adatta la dimensione iniziale allo schermo disponibile
        screen = iface.mainWindow().screen()
        screen_h = screen.availableGeometry().height()
        screen_w = screen.availableGeometry().width()
        self.resize(min(680, screen_w - 40), min(700, screen_h - 80))

        # Icona nella barra del titolo della finestra
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # Tab widget
        self.tabs = QTabWidget()

        self.tabs.addTab(self._wrap_scroll(self._build_tab_ettometriche()), "📏 Calcolo ettometriche")
        self.tabs.addTab(self._wrap_scroll(self._build_tab_foto()),        "📷 Importa Foto")
        self.tabs.addTab(self._wrap_scroll(self._build_tab_importa()),     "📥 Importa Dati")
        self.tabs.addTab(self._wrap_scroll(self._build_tab_progressiva()), "📍 Attribuzione progressiva")
        self.tabs.addTab(self._build_tab_revisione(),                      "🖼️ Revisione Foto")
        self.tabs.addTab(self._wrap_scroll(self._build_tab_word()),        "📄 Report Word")

        # Log condiviso
        log_group = QGroupBox("Log operazioni")
        log_layout = QVBoxLayout(log_group)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFont(QFont("Consolas", 9))
        self.log_area.setMinimumHeight(100)
        self.log_area.setMaximumHeight(160)
        log_layout.addWidget(self.log_area)

        btn_clear = QPushButton("🗑  Pulisci log")
        btn_clear.setFixedWidth(120)
        btn_clear.clicked.connect(self.log_area.clear)
        log_layout.addWidget(btn_clear, alignment=ALIGN_RIGHT)

        main_layout.addWidget(self.tabs, stretch=1)
        main_layout.addWidget(log_group)

    # -----------------------------------------------------------------------
    # TAB 1 – Progressiva
    # -----------------------------------------------------------------------

    def _build_tab_progressiva(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        info = QLabel(
            "Assegna la progressiva ettometrica al layer foto "
            "cercando il punto più vicino nel layer di riferimento."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        form.setLabelAlignment(ALIGN_RIGHT)

        self.prog_layer_foto = QComboBox()
        self._popola_layer_combo(self.prog_layer_foto, "Foto")
        form.addRow("Layer foto:", self.prog_layer_foto)

        # ── Pulsante aggiorna ─────────────────────────────────────────────
        btn_aggiorna = QPushButton("🔄 Aggiorna layer")
        btn_aggiorna.setFixedHeight(26)
        btn_aggiorna.clicked.connect(self._aggiorna_tutti_combo)
        form.addRow("", btn_aggiorna)

        layout.addLayout(form)
        layout.addSpacerItem(QSpacerItem(0, 6))

        # ── Riquadro Gestione carreggiate ─────────────────────────────────
        carr_group = QGroupBox("Gestione carreggiate")
        carr_group_layout = QVBoxLayout(carr_group)
        carr_group_layout.setSpacing(6)

        self.prog_radio_carr_singola = QRadioButton("Carreggiata singola")
        self.prog_radio_carr_doppia  = QRadioButton("Doppia carreggiata")
        self.prog_radio_carr_singola.setChecked(True)

        carr_radio_group = QButtonGroup(carr_group)
        carr_radio_group.addButton(self.prog_radio_carr_singola, 0)
        carr_radio_group.addButton(self.prog_radio_carr_doppia,  1)
        carr_radio_group.buttonClicked.connect(self._prog_toggle_carreggiate_mode)

        carr_group_layout.addWidget(self.prog_radio_carr_singola)

        # Sotto-sezione carreggiata singola
        self.prog_singola_widget = QWidget()
        singola_form = QFormLayout(self.prog_singola_widget)
        singola_form.setLabelAlignment(ALIGN_RIGHT)
        singola_form.setContentsMargins(16, 0, 0, 0)

        self.prog_layer_punti = QComboBox()
        self._popola_layer_combo(self.prog_layer_punti, "progressive")
        self.prog_layer_punti.currentIndexChanged.connect(
            lambda: self._popola_campi_combo(self.prog_campo, self.prog_layer_punti))
        singola_form.addRow("Layer progressive:", self.prog_layer_punti)

        self.prog_campo = QComboBox()
        self._popola_campi_combo(self.prog_campo, self.prog_layer_punti, "progressiv")
        singola_form.addRow("Campo progressiva:", self.prog_campo)

        self.prog_singola_widget.setVisible(True)
        carr_group_layout.addWidget(self.prog_singola_widget)

        carr_group_layout.addWidget(self.prog_radio_carr_doppia)

        # Sotto-sezione doppia carreggiata (nascosta di default)
        self.prog_carr_widget = QWidget()
        carr_vbox = QVBoxLayout(self.prog_carr_widget)
        carr_vbox.setContentsMargins(16, 0, 0, 0)
        carr_vbox.setSpacing(6)

        # ── Riquadro 1: Calcolo automatico carreggiata ────────────────────
        self.prog_chk_calc_auto = QCheckBox("Calcola carreggiata automaticamente dai tracciati")
        self.prog_chk_calc_auto.toggled.connect(self._prog_toggle_calc_auto)
        carr_vbox.addWidget(self.prog_chk_calc_auto)

        self.prog_calc_auto_widget = QWidget()
        calc_form = QFormLayout(self.prog_calc_auto_widget)
        calc_form.setLabelAlignment(ALIGN_RIGHT)
        calc_form.setContentsMargins(12, 0, 0, 0)

        self.prog_tratta_a = QComboBox()
        self._popola_layer_combo(self.prog_tratta_a, "tratta_A")
        calc_form.addRow("Layer tratta A:", self.prog_tratta_a)

        self.prog_val_auto_a = QLineEdit()
        self.prog_val_auto_a.setPlaceholderText("es. Nord, A, 1 …")
        calc_form.addRow("Valore da scrivere per A:", self.prog_val_auto_a)

        self.prog_tratta_b = QComboBox()
        self._popola_layer_combo(self.prog_tratta_b, "tratta_B")
        calc_form.addRow("Layer tratta B:", self.prog_tratta_b)

        self.prog_val_auto_b = QLineEdit()
        self.prog_val_auto_b.setPlaceholderText("es. Sud, B, 2 …")
        calc_form.addRow("Valore da scrivere per B:", self.prog_val_auto_b)

        self.prog_btn_calc_carr = QPushButton("📐 Calcola e scrivi in Carr_auto")
        self.prog_btn_calc_carr.setFixedHeight(30)
        self.prog_btn_calc_carr.clicked.connect(self._run_calcola_carreggiata)
        calc_form.addRow("", self.prog_btn_calc_carr)

        self.prog_calc_auto_widget.setVisible(False)
        carr_vbox.addWidget(self.prog_calc_auto_widget)

        # ── Separatore ───────────────────────────────────────────────────
        carr_vbox.addSpacing(4)

        # ── Riquadro 2: Attribuzione progressive ─────────────────────────
        prog_sub = QGroupBox("Attribuzione progressive")
        prog_sub_form = QFormLayout(prog_sub)
        prog_sub_form.setLabelAlignment(ALIGN_RIGHT)

        self.prog_campo_carr = QComboBox()
        self._popola_campi_combo(self.prog_campo_carr, self.prog_layer_foto, "Carr")
        self.prog_campo_carr.currentIndexChanged.connect(self._prog_aggiorna_valori_carr)
        prog_sub_form.addRow("Campo carreggiata:", self.prog_campo_carr)

        self.prog_val_carr_a = QComboBox()
        prog_sub_form.addRow("Valore carreggiata A:", self.prog_val_carr_a)

        self.prog_layer_carr_a = QComboBox()
        self._popola_layer_combo(self.prog_layer_carr_a, "progressive_A")
        self.prog_layer_carr_a.currentIndexChanged.connect(
            lambda: self._popola_campi_combo(self.prog_campo_doppia, self.prog_layer_carr_a))
        prog_sub_form.addRow("Layer progressive A:", self.prog_layer_carr_a)

        self.prog_campo_doppia = QComboBox()
        self._popola_campi_combo(self.prog_campo_doppia, self.prog_layer_carr_a, "progressiv")
        prog_sub_form.addRow("Campo progressiva A:", self.prog_campo_doppia)

        self.prog_val_carr_b = QComboBox()
        prog_sub_form.addRow("Valore carreggiata B:", self.prog_val_carr_b)

        self.prog_layer_carr_b = QComboBox()
        self._popola_layer_combo(self.prog_layer_carr_b, "progressive_B")
        self.prog_layer_carr_b.currentIndexChanged.connect(
            lambda: self._popola_campi_combo(self.prog_campo_doppia_b, self.prog_layer_carr_b))
        prog_sub_form.addRow("Layer progressive B:", self.prog_layer_carr_b)

        self.prog_campo_doppia_b = QComboBox()
        self._popola_campi_combo(self.prog_campo_doppia_b, self.prog_layer_carr_b, "progressiv")
        prog_sub_form.addRow("Campo progressiva B:", self.prog_campo_doppia_b)

        carr_vbox.addWidget(prog_sub)

        self.prog_carr_widget.setVisible(False)
        carr_group_layout.addWidget(self.prog_carr_widget)

        layout.addWidget(carr_group)
        layout.addSpacerItem(QSpacerItem(0, 6))

        # ── Riquadro svincoli separato ────────────────────────────────────
        sv_group = QGroupBox("Gestione svincoli")
        sv_group_layout = QVBoxLayout(sv_group)
        sv_group_layout.setSpacing(6)

        # 2 radio: Svincoli assenti / Svincoli presenti
        self.prog_radio_sv_assenti  = QRadioButton("Svincoli assenti")
        self.prog_radio_sv_presenti = QRadioButton("Svincoli presenti")
        self.prog_radio_sv_assenti.setChecked(True)

        sv_radio_group = QButtonGroup(sv_group)
        sv_radio_group.addButton(self.prog_radio_sv_assenti,  0)
        sv_radio_group.addButton(self.prog_radio_sv_presenti, 1)
        sv_radio_group.buttonClicked.connect(self._prog_toggle_svincoli_mode)

        sv_group_layout.addWidget(self.prog_radio_sv_assenti)
        sv_group_layout.addWidget(self.prog_radio_sv_presenti)

        # Sotto-sezione visibile solo se "Svincoli presenti"
        self.prog_svincoli_presenti_widget = QWidget()
        presenti_vbox = QVBoxLayout(self.prog_svincoli_presenti_widget)
        presenti_vbox.setContentsMargins(16, 0, 0, 0)
        presenti_vbox.setSpacing(4)

        # Radio interni: Campi Excel / Layer svincoli
        self.prog_radio_sv_excel  = QRadioButton("Campi Excel (consigliato)")
        self.prog_radio_sv_layer  = QRadioButton("Layer svincoli (strategia geometrica)")
        self.prog_radio_sv_excel.setChecked(True)

        sv_inner_group = QButtonGroup(self.prog_svincoli_presenti_widget)
        sv_inner_group.addButton(self.prog_radio_sv_excel, 0)
        sv_inner_group.addButton(self.prog_radio_sv_layer, 1)
        sv_inner_group.buttonClicked.connect(self._prog_toggle_svincoli_inner)

        presenti_vbox.addWidget(self.prog_radio_sv_excel)

        # Soglia distanza (sotto "Campi Excel")
        self.prog_svincoli_excel_widget = QWidget()
        soglia_layout = QHBoxLayout(self.prog_svincoli_excel_widget)
        soglia_layout.setContentsMargins(20, 0, 0, 0)
        self.prog_soglia_distanza = QSpinBox()
        self.prog_soglia_distanza.setMinimum(0)
        self.prog_soglia_distanza.setMaximum(10000)
        self.prog_soglia_distanza.setValue(50)
        self.prog_soglia_distanza.setSuffix(" m")
        soglia_layout.addWidget(QLabel("Soglia distanza sospetto:"))
        soglia_layout.addWidget(self.prog_soglia_distanza)
        soglia_layout.addWidget(QLabel("(0 = disabilita)"))
        soglia_layout.addStretch()
        presenti_vbox.addWidget(self.prog_svincoli_excel_widget)

        presenti_vbox.addWidget(self.prog_radio_sv_layer)

        # Layer svincoli (sotto "Layer svincoli")
        self.prog_svincoli_widget = QWidget()
        sv_form = QFormLayout(self.prog_svincoli_widget)
        sv_form.setLabelAlignment(ALIGN_RIGHT)
        sv_form.setContentsMargins(20, 0, 0, 0)

        self.prog_layer_svincoli = QComboBox()
        self._popola_layer_combo(self.prog_layer_svincoli, "svincoli")
        sv_form.addRow("Layer svincoli:", self.prog_layer_svincoli)

        self.prog_campo_nome_svincolo = QComboBox()
        self.prog_campo_nome_svincolo.setEditable(True)
        self.prog_campo_nome_svincolo.addItem("nome")
        sv_form.addRow("Campo nome svincolo:", self.prog_campo_nome_svincolo)

        self.prog_svincoli_widget.setVisible(False)
        presenti_vbox.addWidget(self.prog_svincoli_widget)

        self.prog_svincoli_presenti_widget.setVisible(False)
        sv_group_layout.addWidget(self.prog_svincoli_presenti_widget)

        layout.addWidget(sv_group)
        layout.addSpacerItem(QSpacerItem(0, 4))

        self.btn_progressiva = QPushButton("▶  Assegna progressive")
        self.btn_progressiva.setFixedHeight(36)
        self.btn_progressiva.clicked.connect(self._run_progressiva)
        layout.addWidget(self.btn_progressiva)

        self.prog_progress_bar = QProgressBar()
        self.prog_progress_bar.setVisible(False)
        self.prog_progress_bar.setTextVisible(True)
        self.prog_progress_bar.setFormat("%v / %m  (%p%)")
        layout.addWidget(self.prog_progress_bar)

        layout.addStretch()
        return w

    def _prog_toggle_svincoli_mode(self, btn=None):
        """Mostra/nasconde la sezione svincoli presenti."""
        presenti = self.prog_radio_sv_presenti.isChecked()
        self.prog_svincoli_presenti_widget.setVisible(presenti)

    def _prog_toggle_svincoli_inner(self, btn=None):
        """Mostra/nasconde Excel vs Layer dentro 'Svincoli presenti'."""
        layer = self.prog_radio_sv_layer.isChecked()
        self.prog_svincoli_widget.setVisible(layer)
        self.prog_svincoli_excel_widget.setVisible(not layer)

    def _prog_toggle_calc_auto(self, attivo):
        self.prog_calc_auto_widget.setVisible(attivo)

    def _prog_aggiorna_valori_carr(self):
        """Popola le combo val_carr_a e val_carr_b con i valori distinti del campo Carr."""
        from qgis.core import QgsVectorLayer
        nome_layer = self.prog_layer_foto.currentText()
        nome_campo = self.prog_campo_carr.currentText()
        if not nome_layer or not nome_campo:
            return
        valori = set()
        layers = QgsProject.instance().mapLayersByName(nome_layer)
        if layers and isinstance(layers[0], QgsVectorLayer):
            if nome_campo not in [f.name() for f in layers[0].fields()]:
                return
            for feat in layers[0].getFeatures():
                v = feat[nome_campo]
                if v and str(v).strip() not in ("", "NULL", "None"):
                    valori.add(str(v).strip())
        valori_sorted = sorted(valori)
        for combo in [self.prog_val_carr_a, self.prog_val_carr_b]:
            current = combo.currentText()
            combo.clear()
            for v in valori_sorted:
                combo.addItem(v)
            idx = combo.findText(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)

    def _run_calcola_carreggiata(self):
        from .core import calcola_carreggiata_automatica
        from qgis.PyQt.QtWidgets import QMessageBox
        val_a = self.prog_val_auto_a.text().strip()
        val_b = self.prog_val_auto_b.text().strip()
        if not val_a or not val_b:
            self._log("❌ Inserire il valore da scrivere per A e per B.", color="#b00000")
            return
        self._set_buttons_enabled(False)
        self._log("\n── Calcolo automatico carreggiata ──")
        try:
            ok, msg = calcola_carreggiata_automatica(
                nome_layer_foto     = self.prog_layer_foto.currentText(),
                nome_layer_tratta_a = self.prog_tratta_a.currentText(),
                nome_layer_tratta_b = self.prog_tratta_b.currentText(),
                val_carr_a          = val_a,
                val_carr_b          = val_b,
                log_fn              = self._log,
            )
        except Exception as e:
            ok, msg = False, str(e)
        self._on_worker_done(ok, msg.split("\n\nWARNING:")[0] if ok else msg, self.btn_progressiva)
        self._prog_aggiorna_valori_carr()
        # Mostra popup warning se ci sono discrepanze
        if ok and "\n\nWARNING:" in msg:
            warning_text = msg.split("\n\nWARNING:")[1]
            dlg = QMessageBox(self)
            dlg.setWindowTitle("Discrepanze Carr / Carr_auto")
            dlg.setIcon(MSG_ICON_WARNING)
            dlg.setText(warning_text)
            dlg.setStandardButtons(MSG_BTN_OK)
            exec_dialog(dlg)

    def _prog_toggle_carreggiate_mode(self, btn=None):
        """Mostra/nasconde le sotto-sezioni carreggiata singola/doppia."""
        doppia = self.prog_radio_carr_doppia.isChecked()
        self.prog_singola_widget.setVisible(not doppia)
        self.prog_carr_widget.setVisible(doppia)
        if doppia:
            self._prog_aggiorna_valori_carr()

    # -----------------------------------------------------------------------
    # TAB 3 – Report Word
    # -----------------------------------------------------------------------

    def _build_tab_word(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        info = QLabel(
            "Legge i dati direttamente dal layer foto nel progetto QGIS "
            "e genera il documento Word con le foto nelle tabelle, "
            "più un report Excel di riepilogo."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        form.setLabelAlignment(ALIGN_RIGHT)

        # Layer foto
        self.word_layer_foto = QComboBox()
        self._popola_layer_combo(self.word_layer_foto, "Foto")
        row_word_layer = QHBoxLayout()
        row_word_layer.addWidget(self.word_layer_foto, stretch=1)
        btn_agg_word = QPushButton("🔄")
        btn_agg_word.setFixedWidth(32)
        btn_agg_word.setToolTip("Aggiorna lista layer")
        btn_agg_word.clicked.connect(self._aggiorna_tutti_combo)
        row_word_layer.addWidget(btn_agg_word)
        form.addRow("Layer foto:", row_word_layer)

        # File Word template
        row_word = QHBoxLayout()
        self.word_doc_path = QLineEdit()
        self.word_doc_path.setPlaceholderText("Seleziona il file Word template...")
        btn_word = QPushButton("📂")
        btn_word.setFixedWidth(32)
        btn_word.clicked.connect(lambda: self._browse_file(
            self.word_doc_path, "File Word (*.docx)"
        ))
        row_word.addWidget(self.word_doc_path)
        row_word.addWidget(btn_word)
        form.addRow("File Word:", row_word)

        layout.addLayout(form)

        # Opzioni
        opt_group = QGroupBox("Opzioni")
        opt_layout = QVBoxLayout(opt_group)

        self.chk_carr       = QCheckBox("Utilizza campo Carreggiata nella descrizione")
        self.chk_carr.setChecked(True)
        self.chk_lista      = QCheckBox("Genera elenco foto prima di ogni tabella")
        self.chk_prima_riga = QCheckBox("Elimina prima riga della tabella")
        self.chk_prima_riga.setChecked(True)

        opt_layout.addWidget(self.chk_carr)
        opt_layout.addWidget(self.chk_lista)
        opt_layout.addWidget(self.chk_prima_riga)

        # Risoluzione foto
        res_row = QHBoxLayout()
        res_row.addWidget(QLabel("Risoluzione foto:"))
        self.word_risoluzione = QComboBox()
        self.word_risoluzione.addItem("Originale",  0)
        self.word_risoluzione.addItem("330 ppi",  330)
        self.word_risoluzione.addItem("220 ppi",  220)
        self.word_risoluzione.addItem("150 ppi",  150)
        self.word_risoluzione.setCurrentIndex(1)   # default 330 ppi
        res_row.addWidget(self.word_risoluzione)
        res_row.addStretch()
        opt_layout.addLayout(res_row)

        layout.addWidget(opt_group)

        self.btn_word = QPushButton("▶  Genera report Word")
        self.btn_word.setFixedHeight(36)
        self.btn_word.clicked.connect(self._run_word)
        layout.addWidget(self.btn_word)

        self.word_progress_bar = QProgressBar()
        self.word_progress_bar.setVisible(False)
        self.word_progress_bar.setTextVisible(True)
        self.word_progress_bar.setFormat("%v / %m  (%p%)")
        layout.addWidget(self.word_progress_bar)

        layout.addStretch()
        return w

    # -----------------------------------------------------------------------
    # Helpers UI
    # -----------------------------------------------------------------------

    def _wrap_scroll(self, widget):
        """Avvolge un widget in una QScrollArea verticale."""
        scroll = QScrollArea()
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(FRAME_NOFRAME)
        scroll.setHorizontalScrollBarPolicy(SCROLLBAR_AS_NEEDED)
        scroll.setVerticalScrollBarPolicy(SCROLLBAR_AS_NEEDED)
        return scroll

    def _popola_layer_combo(self, combo, default=""):
        """Riempie una QComboBox con i nomi di tutti i layer vettoriali del progetto."""
        from qgis.core import QgsVectorLayer
        combo.clear()
        layers = QgsProject.instance().mapLayers().values()
        nomi = sorted([l.name() for l in layers if isinstance(l, QgsVectorLayer)])
        for nome in nomi:
            combo.addItem(nome)
        # Seleziona il default se presente
        idx = combo.findText(default)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _popola_campi_combo(self, combo, layer_combo, default=""):
        """Riempie una QComboBox con i campi del layer selezionato in layer_combo."""
        combo.clear()
        nome_layer = layer_combo.currentText()
        layers = QgsProject.instance().mapLayersByName(nome_layer)
        if layers:
            campi = sorted([f.name() for f in layers[0].fields()])
            for campo in campi:
                combo.addItem(campo)
        idx = combo.findText(default)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _aggiorna_tutti_combo(self):
        """Ricarica tutte le combo layer/campo dal progetto corrente."""
        sel_punti  = self.prog_layer_punti.currentText()
        sel_foto_p = self.prog_layer_foto.currentText()
        sel_campo  = self.prog_campo.currentText()
        sel_word   = self.word_layer_foto.currentText()
        sel_imp    = self.imp_layer_foto.currentText()
        sel_rev    = self.rev_layer_name.currentText()

        self._popola_layer_combo(self.prog_layer_foto,         sel_foto_p)
        self._popola_layer_combo(self.prog_layer_punti,        sel_punti)
        self._popola_campi_combo(self.prog_campo,              self.prog_layer_punti, sel_campo)
        self._popola_campi_combo(self.prog_campo_carr,         self.prog_layer_foto, "Carr")
        self._prog_aggiorna_valori_carr()
        self._popola_layer_combo(self.prog_layer_carr_a,       self.prog_layer_carr_a.currentText())
        self._popola_campi_combo(self.prog_campo_doppia,       self.prog_layer_carr_a, "progressiv")
        self._popola_layer_combo(self.prog_layer_carr_b,       self.prog_layer_carr_b.currentText())
        self._popola_campi_combo(self.prog_campo_doppia_b,     self.prog_layer_carr_b, "progressiv")
        self._popola_layer_combo(self.prog_tratta_a,           self.prog_tratta_a.currentText())
        self._popola_layer_combo(self.prog_tratta_b,           self.prog_tratta_b.currentText())
        self._popola_layer_combo(self.prog_layer_svincoli,     self.prog_layer_svincoli.currentText())
        self._popola_campi_combo(self.prog_campo_nome_svincolo, self.prog_layer_svincoli, "nome")
        self._popola_layer_combo(self.word_layer_foto,         sel_word)
        self._popola_layer_combo(self.imp_layer_foto,          sel_imp)
        self._popola_layer_combo(self.rev_layer_name,          sel_rev)
        self._popola_layer_combo(self.ett_layer_punti,         self.ett_layer_punti.currentText())
        self._popola_campi_combo(self.ett_campo_km,            self.ett_layer_punti, "km")
        self._popola_layer_combo(self.ett_layer_tratta,        self.ett_layer_tratta.currentText())
        self._log("🔄 Liste layer aggiornate.")

    def _imp_sfoglia_excel(self):
        """Apre il file Excel e popola le combo delle colonne."""
        path, _ = QFileDialog.getOpenFileName(self, "Seleziona file Excel", "", "File Excel (*.xlsx)")
        if not path:
            return
        self.imp_excel_path.setText(path)
        # Leggi le colonne
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            ws = wb.active
            colonne = [str(cell.value).strip() for cell in next(ws.iter_rows(max_row=1))
                       if cell.value is not None]
            wb.close()
            defaults = {"nome foto": "nome", "title": "title",
                        "comment": "comment", "note": "note",
                        "carreggiata": "carreggiata", "svincolo": "svincolo"}
            opzionali = {"title", "comment", "note", "carreggiata", "svincolo"}
            for combo, default_key in [
                (self.imp_col_nome,     "nome foto"),
                (self.imp_col_title,    "title"),
                (self.imp_col_comment,  "comment"),
                (self.imp_col_note,     "note"),
                (self.imp_col_carr,     "carreggiata"),
                (self.imp_col_svincolo, "svincolo"),
            ]:
                combo.clear()
                # Le combo opzionali hanno "— Non presente —" come prima voce
                if default_key in opzionali:
                    combo.addItem("— Non presente —")
                for col in colonne:
                    combo.addItem(col)
                # Prova a preselezionare la colonna con nome simile al default
                default = defaults[default_key]
                idx = next((i for i, c in enumerate(combo.itemText(j) for j in range(combo.count()))
                            if c.lower() == default.lower()), -1)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                else:
                    combo.setCurrentIndex(0)
            self._log(f"📋 {len(colonne)} colonne lette da '{path.split('/')[-1]}'.")
        except Exception as e:
            self._log(f"⚠ Impossibile leggere le colonne: {e}. Scrivi i nomi manualmente.")

    def _make_progress_fn(self, bar):
        """Restituisce una callback progress_fn(current, total) per la barra data."""
        def progress_fn(current, total):
            if total > 0:
                bar.setMaximum(total)
                bar.setValue(current)
                bar.setVisible(True)
                QApplication.processEvents()
        return progress_fn

    def _hide_progress(self, bar):
        bar.setValue(bar.maximum() if bar.maximum() > 0 else 0)
        QApplication.processEvents()
        bar.setVisible(False)

    def _browse_file(self, line_edit, file_filter):
        path, _ = QFileDialog.getOpenFileName(self, "Seleziona file", "", file_filter)
        if path:
            line_edit.setText(path)

    def _log(self, msg, color=None):
        """Aggiunge un messaggio al log con colore opzionale."""
        if color:
            self.log_area.setTextColor(QColor(color))
        self.log_area.append(msg)
        self.log_area.setTextColor(QColor("black"))
        self.log_area.ensureCursorVisible()

    def _set_buttons_enabled(self, enabled):
        for btn in [self.btn_progressiva, self.btn_word, self.btn_importa, self.btn_foto, self.btn_ett,
                    self.prog_btn_calc_carr]:
            btn.setEnabled(enabled)

    def _on_worker_done(self, ok, msg, btn):
        self._set_buttons_enabled(True)
        if ok:
            self._log(f"✅ {msg}", color="#1a6e1a")
        else:
            self._log(f"❌ {msg}", color="#b00000")

    # -----------------------------------------------------------------------
    # Avvio operazioni (in thread)
    # -----------------------------------------------------------------------

    def _run_progressiva(self):
        self._set_buttons_enabled(False)
        self._log("\n── Assegnazione progressive ──")
        progress_fn = self._make_progress_fn(self.prog_progress_bar)
        try:
            if self.prog_radio_carr_doppia.isChecked():
                val_a = self.prog_val_carr_a.currentText().strip()
                val_b = self.prog_val_carr_b.currentText().strip()
                if not val_a or not val_b:
                    ok, msg = False, "Inserire il valore carreggiata A e B prima di procedere."
                else:
                    ok, msg = assegna_progressive_carreggiate(
                        nome_layer_foto      = self.prog_layer_foto.currentText(),
                        campo_carreggiata    = self.prog_campo_carr.currentText(),
                        val_carr_a           = val_a,
                        nome_layer_punti_a   = self.prog_layer_carr_a.currentText(),
                        nome_campo_prog_a    = self.prog_campo_doppia.currentText(),
                        val_carr_b           = val_b,
                        nome_layer_punti_b   = self.prog_layer_carr_b.currentText(),
                        nome_campo_prog_b    = self.prog_campo_doppia_b.currentText(),
                        log_fn               = self._log,
                        progress_fn          = progress_fn,
                        usa_svincoli         = self.prog_radio_sv_presenti.isChecked() and self.prog_radio_sv_layer.isChecked(),
                        layer_svincoli       = self.prog_layer_svincoli.currentText() if (self.prog_radio_sv_presenti.isChecked() and self.prog_radio_sv_layer.isChecked()) else None,
                        campo_nome_svincolo  = self.prog_campo_nome_svincolo.currentText() if (self.prog_radio_sv_presenti.isChecked() and self.prog_radio_sv_layer.isChecked()) else None,
                        soglia_distanza      = self.prog_soglia_distanza.value() if (self.prog_radio_sv_presenti.isChecked() and self.prog_radio_sv_excel.isChecked()) else 0,
                    )
            else:
                ok, msg = assegna_progressive(
                    self.prog_layer_punti.currentText(),
                    self.prog_layer_foto.currentText(),
                    self.prog_campo.currentText(),
                    log_fn=self._log,
                    progress_fn=progress_fn,
                    usa_svincoli=self.prog_radio_sv_presenti.isChecked() and self.prog_radio_sv_layer.isChecked(),
                    layer_svincoli=self.prog_layer_svincoli.currentText() if (self.prog_radio_sv_presenti.isChecked() and self.prog_radio_sv_layer.isChecked()) else None,
                    campo_nome_svincolo=self.prog_campo_nome_svincolo.currentText() if (self.prog_radio_sv_presenti.isChecked() and self.prog_radio_sv_layer.isChecked()) else None,
                    soglia_distanza=self.prog_soglia_distanza.value() if (self.prog_radio_sv_presenti.isChecked() and self.prog_radio_sv_excel.isChecked()) else 0,
                )
        except Exception as e:
            ok, msg = False, str(e)
        self._hide_progress(self.prog_progress_bar)
        self._on_worker_done(ok, msg, self.btn_progressiva)

    def _run_codici(self, nome_layer=None):
        """Popola i codici difetti. Chiamato automaticamente dopo l'import."""
        if nome_layer is None:
            nome_layer = self.imp_layer_foto.currentText()
        try:
            ok, msg = popola_codici(nome_layer, log_fn=self._log)
        except Exception as e:
            ok, msg = False, str(e)
        if ok:
            self._log(f"✅ {msg}", color="#1a6e1a")
        else:
            self._log(f"❌ {msg}", color="#b00000")

    def _run_word(self):
        layer = self.word_layer_foto.currentText()
        word  = self.word_doc_path.text().strip()
        if not layer or not word:
            self._log("❌ Specifica il layer foto e seleziona il file Word.", color="#b00000")
            return
        self._set_buttons_enabled(False)
        self._log("\n── Generazione report Word ──")
        progress_fn = self._make_progress_fn(self.word_progress_bar)
        try:
            ok, msg = genera_report_word(
                layer,
                word,
                self.chk_carr.isChecked(),
                self.chk_lista.isChecked(),
                self.chk_prima_riga.isChecked(),
                log_fn=self._log,
                progress_fn=progress_fn,
                dpi=self.word_risoluzione.currentData(),
            )
        except Exception as e:
            ok, msg = False, str(e)
        self._hide_progress(self.word_progress_bar)
        self._on_worker_done(ok, msg, self.btn_word)

    # -----------------------------------------------------------------------
    # TAB 4 – Revisione Foto
    # -----------------------------------------------------------------------

    def _build_tab_revisione(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # --- Riga selezione layer ---
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Layer foto:"))
        self.rev_layer_name = QComboBox()
        self._popola_layer_combo(self.rev_layer_name, "Foto")
        top_row.addWidget(self.rev_layer_name, stretch=1)
        btn_agg_rev = QPushButton("🔄")
        btn_agg_rev.setFixedWidth(32)
        btn_agg_rev.setToolTip("Aggiorna lista layer")
        btn_agg_rev.clicked.connect(lambda: self._popola_layer_combo(
            self.rev_layer_name, self.rev_layer_name.currentText()))
        top_row.addWidget(btn_agg_rev)
        btn_carica = QPushButton("📂 Carica")
        btn_carica.setFixedWidth(90)
        btn_carica.clicked.connect(self._rev_carica_layer)
        top_row.addWidget(btn_carica)
        self.rev_progress_label = QLabel("")
        self.rev_progress_label.setAlignment(ALIGN_RIGHT | ALIGN_VCENTER)
        top_row.addWidget(self.rev_progress_label, stretch=1)
        layout.addLayout(top_row)

        # --- Nome file foto ---
        self.rev_nome_label = QLabel("")
        self.rev_nome_label.setAlignment(ALIGN_CENTER)
        self.rev_nome_label.setFont(QFont("Arial", 10, FONT_BOLD))
        layout.addWidget(self.rev_nome_label)

        # --- Immagine ---
        self.rev_img_label = QLabel("Carica un layer per iniziare")
        self.rev_img_label.setAlignment(ALIGN_CENTER)
        self.rev_img_label.setMinimumHeight(280)
        self.rev_img_label.setStyleSheet("background-color: #1e1e1e; color: #aaaaaa; border-radius: 6px;")
        layout.addWidget(self.rev_img_label, stretch=1)

        # --- Modifica Title / Comment ---
        edit_group = QGroupBox("Modifica")
        edit_layout = QFormLayout(edit_group)
        edit_layout.setLabelAlignment(ALIGN_RIGHT)

        self.rev_title_entry   = QLineEdit()
        self.rev_title_entry.textChanged.connect(self._rev_aggiorna_comment_stato)
        self.rev_title_entry.textChanged.connect(self._rev_valida)

        # Combo Puntuale/Ricorrente (solo per codici 1-10)
        self.rev_comment_combo = QComboBox()
        self.rev_comment_combo.addItem("Puntuale",   1)
        self.rev_comment_combo.addItem("Ricorrente", 2)

        btn_aggiorna = QPushButton("🔄 Aggiorna anteprima codice")
        btn_aggiorna.clicked.connect(self._rev_aggiorna_anteprima)

        self.rev_descr_entry = QLineEdit()
        self.rev_descr_entry.textChanged.connect(self._rev_valida)
        self.rev_note_entry  = QLineEdit()
        self.rev_note_entry.setReadOnly(True)
        self.rev_note_entry.setStyleSheet("background-color: #f0f0f0; color: #555555;")
        self.rev_prog_entry     = QLineEdit()
        self.rev_svincolo_entry = QLineEdit()
        edit_layout.addRow("Codice difetto:",    self.rev_title_entry)
        edit_layout.addRow("Puntuale/Ricorrente:", self.rev_comment_combo)
        edit_layout.addRow("Descrizione:",    self.rev_descr_entry)
        edit_layout.addRow("Note:",           self.rev_note_entry)

        # Prog e Svincolo nella stessa riga, allineati con gli altri campi
        prog_sv_widget = QWidget()
        prog_sv_layout = QHBoxLayout(prog_sv_widget)
        prog_sv_layout.setContentsMargins(0, 0, 0, 0)
        prog_sv_layout.addWidget(self.rev_prog_entry)
        prog_sv_layout.addWidget(QLabel("Svincolo:"))
        prog_sv_layout.addWidget(self.rev_svincolo_entry)
        edit_layout.addRow("Prog (m):", prog_sv_widget)

        edit_layout.addRow("",               btn_aggiorna)
        layout.addWidget(edit_group)

        # --- Warning validazione ---
        self.rev_warning_label = QLabel("")
        self.rev_warning_label.setWordWrap(True)
        self.rev_warning_label.setStyleSheet(
            "color: #b06000; background-color: #fff8e1; border: 1px solid #f0c040; "
            "border-radius: 4px; padding: 4px 8px;"
        )
        self.rev_warning_label.setVisible(False)
        layout.addWidget(self.rev_warning_label)

        # --- Navigazione + Salva ---
        nav_row = QHBoxLayout()
        self.btn_rev_prev = QPushButton("⏮ Indietro")
        self.btn_rev_prev.setFixedHeight(34)
        self.btn_rev_prev.clicked.connect(self._rev_prev)

        self.btn_rev_save = QPushButton("💾 Salva e avanti ⏭")
        self.btn_rev_save.setFixedHeight(34)
        self.btn_rev_save.setStyleSheet("background-color: #1a3a5c; color: white; border-radius:4px;")
        self.btn_rev_save.clicked.connect(self._rev_salva_e_avanti)

        nav_row.addWidget(self.btn_rev_prev)
        nav_row.addStretch()

        self.btn_rev_avanti = QPushButton("Avanti ⏭")
        self.btn_rev_avanti.setFixedHeight(34)
        self.btn_rev_avanti.clicked.connect(self._rev_avanti_senza_salvare)
        nav_row.addWidget(self.btn_rev_avanti)

        nav_row.addWidget(self.btn_rev_save)
        layout.addLayout(nav_row)

        # Stato interno
        self._rev_features  = []   # lista di QgsFeature
        self._rev_layer     = None
        self._rev_index     = 0

        return w

    # ---- helpers Revisione ------------------------------------------------

    def _rev_carica_layer(self):
        nome = self.rev_layer_name.currentText()
        layers = QgsProject.instance().mapLayersByName(nome)
        if not layers:
            self._log(f"❌ Layer '{nome}' non trovato.", color="#b00000")
            return

        self._rev_layer    = layers[0]
        self._rev_features = list(self._rev_layer.getFeatures())
        self._rev_index    = 0

        if not self._rev_features:
            self._log(f"❌ Il layer '{nome}' non contiene feature.", color="#b00000")
            return

        self._log(f"✅ {len(self._rev_features)} foto caricate dal layer '{nome}'.")
        self._rev_mostra()

    def _rev_mostra(self):
        if not self._rev_features:
            return

        feature = self._rev_features[self._rev_index]
        total   = len(self._rev_features)
        self.rev_progress_label.setText(f"{self._rev_index + 1} / {total}")

        # Nome file + progressiva
        fields_names = [f.name() for f in self._rev_layer.fields()]
        path = feature["Path"] if "Path" in fields_names else ""
        nome = feature["name"] if "name" in fields_names and feature["name"] else os.path.basename(str(path)) if path else f"Feature ID {feature.id()}"
        prog = feature["prog"] if "prog" in fields_names else None
        carr = feature["Carr"] if "Carr" in fields_names else None
        if prog is not None:
            prog_int = parse_progressiva_metri(prog)
            if prog_int is not None:
                km = prog_int // 1000
                m  = prog_int % 1000
                prog_str = f"  |  km {km}+{m:03d}"
            else:
                prog_str = f"  |  prog: {prog}"
        else:
            prog_str = ""
        carr_str = f"  |  Carr. {str(carr).strip()}" if carr and str(carr).strip() not in ("", "NULL", "None") else ""
        self.rev_nome_label.setText(f"{nome}{prog_str}{carr_str}")

        # Immagine
        if path and os.path.exists(str(path)):
            pix = QPixmap(str(path))
            if not pix.isNull():
                pix = pix.scaled(
                    self.rev_img_label.width() or 560,
                    280,
                    KEEP_ASPECT_RATIO,
                    SMOOTH_TRANSFORM
                )
                self.rev_img_label.setPixmap(pix)
            else:
                self.rev_img_label.setPixmap(QPixmap())
                self.rev_img_label.setText("Impossibile caricare l'immagine")
        else:
            self.rev_img_label.setPixmap(QPixmap())
            self.rev_img_label.setText("Percorso non trovato:\n" + str(path))

        # Title, Comment e descr_1
        title    = str(feature["Title"]        or "").strip() if "Title"        in fields_names else ""
        comment  = str(feature["Comment"]      or "").strip() if "Comment"      in fields_names else ""
        descr    = str(feature["descr_1"]or "").strip() if "descr_1"in fields_names else ""
        note     = str(feature["Note"]         or "").strip() if "Note"         in fields_names else ""
        prog_val = (str(feature["prog"]).strip() if feature["prog"] is not None else "") if "prog" in fields_names else ""
        sv_val   = str(feature["svincolo"]     or "").strip() if "svincolo"     in fields_names else ""

        # Abilita/disabilita combo in base al codice
        self._rev_aggiorna_comment_stato(title)

        self.rev_title_entry.setText(title)
        self.rev_prog_entry.setText(prog_val)
        self.rev_svincolo_entry.setText(sv_val)
        # Imposta la combo: 1=Puntuale, 2=Ricorrente, default Puntuale
        # (accetta anche "puntuale"/"diffuso" scritti come testo)
        val = normalizza_comment(comment)
        if val not in (1, 2):
            val = 1
        idx = self.rev_comment_combo.findData(val)
        self.rev_comment_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.rev_descr_entry.setText(descr)
        self.rev_note_entry.setText(note)

        # Valida e mostra warning
        self._rev_valida()

        # Abilita/disabilita pulsanti
        non_ultima = self._rev_index < total - 1
        self.btn_rev_prev.setEnabled(self._rev_index > 0)
        self.btn_rev_avanti.setEnabled(non_ultima)

        # Sull'ultima foto: "Salva e avanti" diventa "Salva"
        if non_ultima:
            self.btn_rev_save.setText("💾 Salva e avanti ⏭")
            self.btn_rev_save.clicked.disconnect()
            self.btn_rev_save.clicked.connect(self._rev_salva_e_avanti)
        else:
            self.btn_rev_save.setText("💾 Salva")
            self.btn_rev_save.clicked.disconnect()
            self.btn_rev_save.clicked.connect(self._rev_salva)
        self.btn_rev_save.setEnabled(True)

    def _rev_valida(self):
        """Mostra warning se codice o descrizione non sono validi."""
        if not hasattr(self, 'rev_warning_label'):
            return
        avvisi = []
        title = self.rev_title_entry.text().strip()
        descr = self.rev_descr_entry.text().strip()

        primo = _primo_codice_title(title)
        if not title or not primo:
            avvisi.append("⚠ Codice difetto vuoto.")
        elif primo not in CODICI_DICT:
            avvisi.append(f"⚠ Codice '{primo}' non trovato nel dizionario.")

        # Codice 20 = scartare: descrizione non obbligatoria
        primo_codice = primo
        if not descr and primo_codice != "20":
            avvisi.append("⚠ Descrizione vuota.")

        if avvisi:
            self.rev_warning_label.setText("  ".join(avvisi))
            self.rev_warning_label.setVisible(True)
        else:
            self.rev_warning_label.setVisible(False)

    def _rev_aggiorna_comment_stato(self, title=None):
        """Abilita la combo Puntuale/Ricorrente solo per codici 1-10."""
        if title is None:
            title = self.rev_title_entry.text().strip()
        if not title:
            self.rev_comment_combo.setEnabled(False)
            self.rev_comment_combo.setStyleSheet("background-color: #f0f0f0; color: #aaaaaa;")
            return
        try:
            first_number = int(_primo_codice_title(title).split(".")[0])
        except (ValueError, IndexError):
            first_number = 0
        attivo = (first_number not in (0, 11, 20) and first_number <= 10)
        self.rev_comment_combo.setEnabled(attivo)
        self.rev_comment_combo.setStyleSheet(
            "" if attivo else "background-color: #f0f0f0; color: #aaaaaa;"
        )

    def _rev_aggiorna_anteprima(self):
        """Aggiorna il campo Descrizione con la descrizione del codice inserito."""
        title = self.rev_title_entry.text().strip()
        if not title:
            return
        primo_codice = _primo_codice_title(title)
        info = CODICI_DICT.get(primo_codice)
        if info:
            self.rev_descr_entry.setText(info[2])
            self._log(f"  Codice {primo_codice}: {info[2]}")
        else:
            self._log(f"  ⚠ Codice '{primo_codice}' non trovato nel dizionario.")

    def _rev_salva(self):
        if not self._rev_layer or not self._rev_features:
            return

        from qgis.PyQt.QtWidgets import QMessageBox

        # Validazione prima di salvare
        new_title = self.rev_title_entry.text().strip()
        new_descr = self.rev_descr_entry.text().strip()
        primo_s   = _primo_codice_title(new_title)

        # 1. Codice vuoto o non nel dizionario → avviso bloccante, torna alla foto
        if not new_title or (primo_s and primo_s not in CODICI_DICT and primo_s != "20"):
            msg_txt = "Codice difetto vuoto." if not new_title else f"Codice '{primo_s}' non trovato nel dizionario."
            msg = QMessageBox(self)
            msg.setWindowTitle("Attenzione")
            msg.setIcon(MSG_ICON_WARNING)
            msg.setText(f"{msg_txt}\n\nCorreggi il codice prima di salvare.")
            msg.setStandardButtons(MSG_BTN_OK)
            exec_dialog(msg)
            return False

        # 2. Descrizione vuota (non per codice 20) → chiedi se scartare
        if not new_descr and primo_s != "20":
            msg = QMessageBox(self)
            msg.setWindowTitle("Descrizione vuota")
            msg.setIcon(MSG_ICON_QUESTION)
            msg.setText("Il campo Descrizione è vuoto.\n\nVuoi scartare la foto? (imposta codice 20)")
            msg.setStandardButtons(MSG_BTN_YES | MSG_BTN_NO)
            msg.setDefaultButton(MSG_BTN_NO)
            if exec_dialog(msg) == MSG_BTN_YES:
                # Imposta codice 20 e salva
                self.rev_title_entry.setText("20")
                new_title = "20"
                primo_s   = "20"
            else:
                # Torna alla foto senza salvare
                return False

        feature  = self._rev_features[self._rev_index]
        # Leggi il valore numerico dalla combo (1=Puntuale, 2=Ricorrente)
        # Solo se la combo è abilitata (codici 1-10), altrimenti salva stringa vuota
        if self.rev_comment_combo.isEnabled():
            new_comment = str(self.rev_comment_combo.currentData())
        else:
            new_comment = ""

        fields = [f.name() for f in self._rev_layer.fields()]
        # Traccia se siamo stati noi ad avviare l'editing
        # (per non chiudere sessioni aperte da altri strumenti)
        editing_avviato_da_noi = not self._rev_layer.isEditable()
        if editing_avviato_da_noi:
            self._rev_layer.startEditing()

        if "Title" in fields:
            self._rev_layer.changeAttributeValue(
                feature.id(),
                self._rev_layer.fields().indexFromName("Title"),
                new_title
            )
        if "Comment" in fields:
            self._rev_layer.changeAttributeValue(
                feature.id(),
                self._rev_layer.fields().indexFromName("Comment"),
                new_comment
            )

        new_descr   = self.rev_descr_entry.text().strip()
        new_prog    = self.rev_prog_entry.text().strip()
        new_sv      = self.rev_svincolo_entry.text().strip()

        if "descr_1" in fields:
            self._rev_layer.changeAttributeValue(
                feature.id(),
                self._rev_layer.fields().indexFromName("descr_1"),
                new_descr
            )
        if "prog" in fields and new_prog != "":
            parsed_prog = parse_progressiva_metri(new_prog)
            if parsed_prog is not None:
                self._rev_layer.changeAttributeValue(
                    feature.id(),
                    self._rev_layer.fields().indexFromName("prog"),
                    float(parsed_prog)
                )
            else:
                self._log(f"  ⚠ Progressiva '{new_prog}' non valida (usa metri o formato 12+300), non salvata.")
        if "svincolo" in fields:
            self._rev_layer.changeAttributeValue(
                feature.id(),
                self._rev_layer.fields().indexFromName("svincolo"),
                new_sv
            )

        # Salva solo se siamo stati noi ad aprire la sessione di editing
        if editing_avviato_da_noi:
            self._rev_layer.commitChanges()
        else:
            # Layer già in editing: salva solo le modifiche di questa feature
            # senza chiudere la sessione
            self._rev_layer.triggerRepaint()

        # Aggiorna la feature in memoria
        self._rev_features[self._rev_index] = self._rev_layer.getFeature(feature.id())

        self._log(f"✅ Feature ID {feature.id()} salvata → Title: '{new_title}' | Comment: '{new_comment}' | Descrizione: '{new_descr}'")
        return True

    def _rev_avanti_senza_salvare(self):
        if self._rev_index < len(self._rev_features) - 1:
            self._rev_index += 1
            self._rev_mostra()

    def _rev_salva_e_avanti(self):
        """Salva la feature corrente e passa alla successiva."""
        if self._rev_salva() is False:
            return
        if self._rev_index < len(self._rev_features) - 1:
            self._rev_index += 1
            self._rev_mostra()

    def _rev_prev(self):
        if self._rev_index > 0:
            self._rev_index -= 1
            self._rev_mostra()

    # -----------------------------------------------------------------------
    # TAB 0 – Importa Dati da Excel
    # -----------------------------------------------------------------------

    def _build_tab_importa(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        info = QLabel(
            "Legge un file Excel compilato in campo con le informazioni delle foto "
            "(codice difetto, commento, note) e le copia automaticamente nel layer foto "
            "facendo il match per nome file."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # ── File Excel ───────────────────────────────────────────────────
        file_group = QGroupBox("File e layer")
        file_layout = QFormLayout(file_group)
        file_layout.setLabelAlignment(ALIGN_RIGHT)

        row_excel = QHBoxLayout()
        self.imp_excel_path = QLineEdit()
        self.imp_excel_path.setPlaceholderText("Seleziona il file Excel compilato in campo...")
        btn_excel = QPushButton("📂")
        btn_excel.setFixedWidth(32)
        btn_excel.clicked.connect(self._imp_sfoglia_excel)
        row_excel.addWidget(self.imp_excel_path)
        row_excel.addWidget(btn_excel)
        file_layout.addRow("File Excel:", row_excel)

        row_imp_layer = QHBoxLayout()
        self.imp_layer_foto = QComboBox()
        self._popola_layer_combo(self.imp_layer_foto, "Foto")
        row_imp_layer.addWidget(self.imp_layer_foto, stretch=1)
        btn_agg_imp = QPushButton("🔄")
        btn_agg_imp.setFixedWidth(32)
        btn_agg_imp.setToolTip("Aggiorna lista layer")
        btn_agg_imp.clicked.connect(self._aggiorna_tutti_combo)
        row_imp_layer.addWidget(btn_agg_imp)
        file_layout.addRow("Layer foto:", row_imp_layer)

        layout.addWidget(file_group)

        # ── Mappatura colonne ─────────────────────────────────────────────
        col_group = QGroupBox("Mappatura colonne Excel → campi layer")
        col_layout = QFormLayout(col_group)
        col_layout.setLabelAlignment(ALIGN_RIGHT)

        self.imp_col_nome    = QComboBox(); self.imp_col_nome.setEditable(True)
        self.imp_col_title   = QComboBox(); self.imp_col_title.setEditable(True)
        self.imp_col_comment = QComboBox(); self.imp_col_comment.setEditable(True)
        self.imp_col_note    = QComboBox(); self.imp_col_note.setEditable(True)
        self.imp_col_carr     = QComboBox(); self.imp_col_carr.setEditable(True)
        self.imp_col_svincolo = QComboBox(); self.imp_col_svincolo.setEditable(True)
        col_layout.addRow("Colonna nome foto:",        self.imp_col_nome)
        col_layout.addRow("Colonna codice difetto:",   self.imp_col_title)
        col_layout.addRow("Colonna puntuale/ricorrente:", self.imp_col_comment)
        col_layout.addRow("Colonna Note:",             self.imp_col_note)
        col_layout.addRow("Colonna Carreggiata:",      self.imp_col_carr)
        col_layout.addRow("Colonna Svincolo:",         self.imp_col_svincolo)
        # Per nome foto: solo placeholder; per le altre: "— Non presente —" come prima opzione
        self.imp_col_nome.addItem("nome")
        for combo, val in [(self.imp_col_title, "title"),
                           (self.imp_col_comment, "comment"), (self.imp_col_note, "note"),
                           (self.imp_col_carr, "carreggiata"),
                           (self.imp_col_svincolo, "svincolo")]:
            combo.addItem("— Non presente —")
            combo.addItem(val)

        layout.addWidget(col_group)

        # ── Opzioni ───────────────────────────────────────────────────────
        opt_group = QGroupBox("Opzioni")
        opt_layout = QVBoxLayout(opt_group)

        self.imp_chk_sovrascrivi = QCheckBox(
            "Sovrascrivi Title/Comment anche se già compilati"
        )
        self.imp_chk_sovrascrivi.setChecked(True)
        opt_layout.addWidget(self.imp_chk_sovrascrivi)

        layout.addWidget(opt_group)

        # ── Pulsante ─────────────────────────────────────────────────────
        self.btn_importa = QPushButton("▶  Importa dati nel layer")
        self.btn_importa.setFixedHeight(36)
        self.btn_importa.clicked.connect(self._run_importa)
        layout.addWidget(self.btn_importa)

        self.imp_progress_bar = QProgressBar()
        self.imp_progress_bar.setVisible(False)
        self.imp_progress_bar.setTextVisible(True)
        self.imp_progress_bar.setFormat("%v / %m  (%p%)")
        layout.addWidget(self.imp_progress_bar)

        layout.addStretch()
        return w

    def _run_importa(self):
        excel = self.imp_excel_path.text().strip()
        if not excel:
            self._log("❌ Seleziona il file Excel prima di procedere.", color="#b00000")
            return
        def _col(combo):
            v = combo.currentText().strip()
            return "" if v == "— Non presente —" else v

        self._set_buttons_enabled(False)
        self._log("\n── Importazione dati da Excel ──")
        progress_fn = self._make_progress_fn(self.imp_progress_bar)
        try:
            ok, msg = importa_dati_da_excel(
                excel_path        = excel,
                nome_layer_foto   = self.imp_layer_foto.currentText(),
                col_nome_foto     = _col(self.imp_col_nome),
                col_title         = _col(self.imp_col_title),
                col_comment       = _col(self.imp_col_comment),
                col_note          = _col(self.imp_col_note),
                col_carr          = _col(self.imp_col_carr),
                col_svincolo      = _col(self.imp_col_svincolo),
                sovrascrivi       = self.imp_chk_sovrascrivi.isChecked(),
                log_fn            = self._log,
                progress_fn       = progress_fn,
            )
        except Exception as e:
            ok, msg = False, str(e)
        self._hide_progress(self.imp_progress_bar)
        self._on_worker_done(ok, msg, self.btn_importa)

        # Se l'import è andato a buon fine, popola i codici automaticamente
        if ok:
            self._log("\n── Popolamento automatico codici difetti ──")
            self._run_codici(nome_layer=self.imp_layer_foto.currentText())



    # -----------------------------------------------------------------------
    # TAB – Importa Foto
    # -----------------------------------------------------------------------

    def _build_tab_foto(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        info = QLabel(
            "Legge le coordinate GPS dall'EXIF delle foto e crea un layer "
            "vettoriale puntuale in QGIS. Richiede Pillow (già installata)."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # ── Cartella foto ─────────────────────────────────────────────────
        src_group = QGroupBox("Sorgente")
        src_layout = QFormLayout(src_group)
        src_layout.setLabelAlignment(ALIGN_RIGHT)

        row_folder = QHBoxLayout()
        self.foto_cartella = QLineEdit()
        self.foto_cartella.setPlaceholderText("Seleziona la cartella con le foto...")
        btn_folder = QPushButton("📂")
        btn_folder.setFixedWidth(32)
        btn_folder.clicked.connect(self._foto_sfoglia_cartella)
        row_folder.addWidget(self.foto_cartella)
        row_folder.addWidget(btn_folder)
        src_layout.addRow("Cartella foto:", row_folder)

        self.foto_sottocartelle = QCheckBox("Includi sottocartelle")
        self.foto_sottocartelle.setChecked(True)
        src_layout.addRow("", self.foto_sottocartelle)

        layout.addWidget(src_group)

        # ── Filtri ────────────────────────────────────────────────────────
        filter_group = QGroupBox("Filtri")
        filter_layout = QFormLayout(filter_group)
        filter_layout.setLabelAlignment(ALIGN_RIGHT)

        # Estensioni
        ext_row = QHBoxLayout()
        self.foto_ext_jpg  = QCheckBox("JPG/JPEG")
        self.foto_ext_png  = QCheckBox("PNG")
        self.foto_ext_tiff = QCheckBox("TIFF")
        self.foto_ext_heic = QCheckBox("HEIC")
        self.foto_ext_jpg.setChecked(True)
        ext_row.addWidget(self.foto_ext_jpg)
        ext_row.addWidget(self.foto_ext_png)
        ext_row.addWidget(self.foto_ext_tiff)
        ext_row.addWidget(self.foto_ext_heic)
        ext_row.addStretch()
        filter_layout.addRow("Estensioni:", ext_row)

        # Filtro data
        self.foto_chk_data = QCheckBox("Filtra per data")
        self.foto_chk_data.setChecked(False)
        self.foto_chk_data.toggled.connect(self._foto_toggle_data)
        filter_layout.addRow("", self.foto_chk_data)

        self.foto_data_widget = QWidget()
        data_layout = QHBoxLayout(self.foto_data_widget)
        data_layout.setContentsMargins(0, 0, 0, 0)
        self.foto_data_da = QDateEdit()
        self.foto_data_da.setCalendarPopup(True)
        self.foto_data_da.setDate(QDate.currentDate().addDays(-30))
        self.foto_data_a  = QDateEdit()
        self.foto_data_a.setCalendarPopup(True)
        self.foto_data_a.setDate(QDate.currentDate())
        data_layout.addWidget(QLabel("Da:"))
        data_layout.addWidget(self.foto_data_da)
        data_layout.addWidget(QLabel("A:"))
        data_layout.addWidget(self.foto_data_a)
        data_layout.addStretch()
        self.foto_data_widget.setVisible(False)
        filter_layout.addRow(self.foto_data_widget)

        layout.addWidget(filter_group)

        # ── Layer di output ───────────────────────────────────────────────
        out_group = QGroupBox("Layer di output")
        out_layout = QFormLayout(out_group)
        out_layout.setLabelAlignment(ALIGN_RIGHT)

        self.foto_layer_nome = QLineEdit("Foto")
        out_layout.addRow("Nome layer:", self.foto_layer_nome)

        self.foto_crs_widget = QgsProjectionSelectionWidget()
        self.foto_crs_widget.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
        out_layout.addRow("CRS output:", self.foto_crs_widget)

        layout.addWidget(out_group)

        # ── Pulsante ─────────────────────────────────────────────────────
        self.btn_foto = QPushButton("▶  Importa foto")
        self.btn_foto.setFixedHeight(36)
        self.btn_foto.clicked.connect(self._run_importa_foto)
        layout.addWidget(self.btn_foto)

        self.foto_progress_bar = QProgressBar()
        self.foto_progress_bar.setVisible(False)
        self.foto_progress_bar.setTextVisible(True)
        self.foto_progress_bar.setFormat("%v / %m  (%p%)")
        layout.addWidget(self.foto_progress_bar)

        layout.addStretch()
        return w

    def _foto_sfoglia_cartella(self):
        cartella = QFileDialog.getExistingDirectory(self, "Seleziona cartella foto")
        if cartella:
            self.foto_cartella.setText(cartella)

    def _foto_toggle_data(self, attivo):
        self.foto_data_widget.setVisible(attivo)

    def _run_importa_foto(self):
        cartella = self.foto_cartella.text().strip()
        if not cartella:
            self._log("❌ Seleziona la cartella delle foto.", color="#b00000")
            return

        estensioni = []
        if self.foto_ext_jpg.isChecked():  estensioni += [".jpg", ".jpeg"]
        if self.foto_ext_png.isChecked():  estensioni += [".png"]
        if self.foto_ext_tiff.isChecked(): estensioni += [".tif", ".tiff"]
        if self.foto_ext_heic.isChecked(): estensioni += [".heic"]
        if not estensioni:
            self._log("❌ Seleziona almeno un'estensione.", color="#b00000")
            return

        data_da = self.foto_data_da.date().toPyDate() if self.foto_chk_data.isChecked() else None
        data_a  = self.foto_data_a.date().toPyDate()  if self.foto_chk_data.isChecked() else None

        self._set_buttons_enabled(False)
        self._log("\n── Importazione foto ──")
        progress_fn = self._make_progress_fn(self.foto_progress_bar)

        try:
            ok, msg = importa_foto_da_cartella(
                cartella         = cartella,
                nome_layer       = self.foto_layer_nome.text().strip() or "Foto",
                estensioni       = estensioni,
                sottocartelle    = self.foto_sottocartelle.isChecked(),
                crs_epsg         = self.foto_crs_widget.crs().authid(),
                data_da          = data_da,
                data_a           = data_a,
                log_fn           = self._log,
                progress_fn      = progress_fn,
            )
        except Exception as e:
            ok, msg = False, str(e)

        self._hide_progress(self.foto_progress_bar)
        self._on_worker_done(ok, msg, self.btn_foto)
        # Aggiorna le combo layer dopo l'import
        self._aggiorna_tutti_combo()

    # -----------------------------------------------------------------------
    # TAB – Ettometriche
    # -----------------------------------------------------------------------

    def _build_tab_ettometriche(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        info = QLabel(
            "Genera punti ettometrici lungo una tratta interpolando "
            "tra punti di riferimento con progressive note. "
            "Il layer di output contiene etichette km automatiche."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # ── Layer di input ────────────────────────────────────────────────
        inp_group = QGroupBox("Layer di input")
        inp_layout = QFormLayout(inp_group)
        inp_layout.setLabelAlignment(ALIGN_RIGHT)

        row_punti = QHBoxLayout()
        self.ett_layer_punti = QComboBox()
        self._popola_layer_combo(self.ett_layer_punti, "progressive")
        self.ett_layer_punti.currentIndexChanged.connect(
            lambda: self._popola_campi_combo(self.ett_campo_km, self.ett_layer_punti))
        row_punti.addWidget(self.ett_layer_punti, stretch=1)
        btn_agg_ett = QPushButton("🔄")
        btn_agg_ett.setFixedWidth(32)
        btn_agg_ett.setToolTip("Aggiorna lista layer")
        btn_agg_ett.clicked.connect(self._aggiorna_tutti_combo)
        row_punti.addWidget(btn_agg_ett)
        inp_layout.addRow("Layer punti riferimento:", row_punti)

        self.ett_campo_km = QComboBox()
        self._popola_campi_combo(self.ett_campo_km, self.ett_layer_punti, "km")
        inp_layout.addRow("Campo progressive:", self.ett_campo_km)

        self.ett_layer_tratta = QComboBox()
        self._popola_layer_combo(self.ett_layer_tratta, "tratta")
        inp_layout.addRow("Layer tratta (polilinea):", self.ett_layer_tratta)

        layout.addWidget(inp_group)

        # ── Parametri ─────────────────────────────────────────────────────
        par_group = QGroupBox("Parametri")
        par_layout = QFormLayout(par_group)
        par_layout.setLabelAlignment(ALIGN_RIGHT)

        self.ett_passo = QSpinBox()
        self.ett_passo.setMinimum(1)
        self.ett_passo.setMaximum(10000)
        self.ett_passo.setValue(100)
        self.ett_passo.setSuffix(" m")
        par_layout.addRow("Passo di discretizzazione:", self.ett_passo)

        tolleranza_row = QHBoxLayout()
        self.ett_tolleranza = QSpinBox()
        self.ett_tolleranza.setMinimum(0)
        self.ett_tolleranza.setMaximum(100000)
        self.ett_tolleranza.setValue(1000)
        self.ett_tolleranza.setSuffix(" m")
        tolleranza_row.addWidget(self.ett_tolleranza)
        tolleranza_row.addWidget(QLabel("(avvisa se discrepanza supera soglia)"))
        tolleranza_row.addStretch()
        par_layout.addRow("Tolleranza discrepanza:", tolleranza_row)

        # Distanza massima dei punti dalla polilinea (filtro spaziale)
        max_dist_row = QHBoxLayout()
        self.ett_max_dist = QSpinBox()
        self.ett_max_dist.setMinimum(1)
        self.ett_max_dist.setMaximum(100000)
        self.ett_max_dist.setValue(50)
        self.ett_max_dist.setSuffix(" m")
        max_dist_row.addWidget(self.ett_max_dist)
        max_dist_row.addWidget(QLabel("(scarta punti più lontani della soglia)"))
        max_dist_row.addStretch()
        par_layout.addRow("Distanza max punti da tratta:", max_dist_row)

        self.ett_nome_output = QLineEdit("progressive ettometriche")
        par_layout.addRow("Nome layer output:", self.ett_nome_output)

        layout.addWidget(par_group)

        # ── Pulsante ─────────────────────────────────────────────────────
        self.btn_ett = QPushButton("▶  Genera ettometriche")
        self.btn_ett.setFixedHeight(36)
        self.btn_ett.clicked.connect(self._run_ettometriche)
        layout.addWidget(self.btn_ett)

        self.ett_progress_bar = QProgressBar()
        self.ett_progress_bar.setVisible(False)
        self.ett_progress_bar.setTextVisible(True)
        self.ett_progress_bar.setFormat("%v / %m  (%p%)")
        layout.addWidget(self.ett_progress_bar)

        layout.addStretch()
        return w

    def _run_ettometriche(self):
        layer_punti = self.ett_layer_punti.currentText()
        campo_km    = self.ett_campo_km.currentText()
        layer_tratta = self.ett_layer_tratta.currentText()
        nome_output = self.ett_nome_output.text().strip() or "progressive ettometriche"

        if not layer_punti or not campo_km or not layer_tratta:
            self._log("❌ Seleziona layer punti, campo progressive e layer tratta.", color="#b00000")
            return

        self._set_buttons_enabled(False)
        self._log("\n── Generazione ettometriche ──")
        progress_fn = self._make_progress_fn(self.ett_progress_bar)

        try:
            ok, msg = genera_ettometriche(
                nome_layer_punti   = layer_punti,
                campo_km           = campo_km,
                nome_layer_tratta  = layer_tratta,
                passo              = self.ett_passo.value(),
                tolleranza         = self.ett_tolleranza.value(),
                max_dist_da_tratta = float(self.ett_max_dist.value()),
                nome_output        = nome_output,
                log_fn             = self._log,
                progress_fn        = progress_fn,
            )
        except Exception as e:
            import traceback
            ok, msg = False, traceback.format_exc()

        self._hide_progress(self.ett_progress_bar)
        self._on_worker_done(ok, msg, self.btn_ett)
        self._aggiorna_tutti_combo()
