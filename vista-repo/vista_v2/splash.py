"""
Schermata di benvenuto del plugin VISTA.
Rimane aperta finché l'utente clicca "Avanti →".
"""

import os
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont, QPixmap, QIcon
from .compat import (ALIGN_CENTER, ALIGN_JUSTIFY, KEEP_ASPECT_RATIO,
                     SMOOTH_TRANSFORM, WIN_DIALOG, WIN_FRAMELESS,
                     FONT_BOLD, FRAME_HLINE)


VERSION = "1.2.0"
AUTORE  = "DGISA Ufficio 10 Monitoraggio e digitalizzazione delle infrastrutture / Ansfisa"        # ← modifica qui
DESCRIZIONE = (
    "VISTA è un plugin per QGIS dedicato all'ispezione e al monitoraggio "
    "delle infrastrutture stradali. Permette di gestire il workflow completo: "
    "dall'importazione delle foto georeferenziate, all'associazione dei codici "
    "difetto, all'assegnazione delle progressive ettometriche, fino alla "
    "generazione automatica dei verbali di ispezione in formato Word."
)
ISTRUZIONI = [
    ("📏", "Calcolo ettometriche", "Genera punti ettometrici lungo una tratta interpolando tra punti di riferimento con progressive note"),
    ("📷", "Importa Foto",         "Legge le coordinate GPS dall'EXIF delle foto e crea un layer vettoriale puntuale in QGIS"),
    ("📥", "Importa Dati",         "Carica da Excel i codici difetto, i commenti e le note direttamente nel layer foto"),
    ("📍", "Attribuzione progressiva",          "Assegna la progressiva ettometrica a ogni foto tramite il layer di riferimento"),
    ("🖼️",  "Revisione Foto",      "Naviga le foto, verifica e correggi i dati direttamente sul layer QGIS"),
    ("📄", "Report Word",          "Genera il verbale Word con le foto inserite nelle tabelle, più un report Excel"),
]


class SplashScreen(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("VISTA")
        self.setWindowFlags(WIN_DIALOG | WIN_FRAMELESS)
        self.setFixedSize(560, 600)
        self.setModal(True)

        plugin_dir = os.path.dirname(__file__)

        # Icona barra del titolo
        icon_path = os.path.join(plugin_dir, "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Logo grande: cerca logo.png, altrimenti usa icon.png
        logo_path = os.path.join(plugin_dir, "logo.png")
        if not os.path.exists(logo_path):
            logo_path = icon_path

        self._build_ui(logo_path)

    def _build_ui(self, logo_path):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ───────────────────────────────────────────────────────
        header = QFrame()
        header.setFixedHeight(210)
        header.setStyleSheet("background-color: #1a3a5c;")
        header_layout = QVBoxLayout(header)
        header_layout.setAlignment(ALIGN_CENTER)
        header_layout.setSpacing(10)

        if os.path.exists(logo_path):
            logo_lbl = QLabel()
            pix = QPixmap(logo_path).scaled(
                100, 100, KEEP_ASPECT_RATIO, SMOOTH_TRANSFORM
            )
            logo_lbl.setPixmap(pix)
            logo_lbl.setAlignment(ALIGN_CENTER)
            header_layout.addWidget(logo_lbl)

        name_lbl = QLabel("VISTA")
        name_lbl.setFont(QFont("Arial", 28, FONT_BOLD))
        name_lbl.setStyleSheet("color: #ffffff; letter-spacing: 6px;")
        name_lbl.setAlignment(ALIGN_CENTER)
        header_layout.addWidget(name_lbl)

        ver_lbl = QLabel(f"versione {VERSION}  ·  {AUTORE}")
        ver_lbl.setFont(QFont("Arial", 10))
        ver_lbl.setStyleSheet("color: #a8c8e8;")
        ver_lbl.setAlignment(ALIGN_CENTER)
        header_layout.addWidget(ver_lbl)

        root.addWidget(header)

        # ── Body ─────────────────────────────────────────────────────────
        body = QFrame()
        body.setStyleSheet("background-color: #f4f6f9;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(28, 20, 28, 16)
        body_layout.setSpacing(14)

        desc_lbl = QLabel(DESCRIZIONE)
        desc_lbl.setWordWrap(True)
        desc_lbl.setFont(QFont("Arial", 10))
        desc_lbl.setStyleSheet("color: #333333;")
        desc_lbl.setAlignment(ALIGN_JUSTIFY)
        body_layout.addWidget(desc_lbl)

        sep = QFrame()
        sep.setFrameShape(FRAME_HLINE)
        sep.setStyleSheet("color: #cccccc;")
        body_layout.addWidget(sep)

        istr_title = QLabel("Come si usa")
        istr_title.setFont(QFont("Arial", 11, FONT_BOLD))
        istr_title.setStyleSheet("color: #1a3a5c;")
        body_layout.addWidget(istr_title)

        for emoji, tab, descr in ISTRUZIONI:
            row = QHBoxLayout()
            row.setSpacing(10)

            emoji_lbl = QLabel(emoji)
            emoji_lbl.setFixedWidth(26)
            emoji_lbl.setFont(QFont("Arial", 14))
            emoji_lbl.setAlignment(ALIGN_CENTER)
            row.addWidget(emoji_lbl)

            tab_lbl = QLabel(f"<b>{tab}</b>")
            tab_lbl.setFixedWidth(110)
            tab_lbl.setFont(QFont("Arial", 10))
            tab_lbl.setStyleSheet("color: #1a3a5c;")
            row.addWidget(tab_lbl)

            descr_lbl = QLabel(descr)
            descr_lbl.setFont(QFont("Arial", 10))
            descr_lbl.setStyleSheet("color: #555555;")
            descr_lbl.setWordWrap(True)
            row.addWidget(descr_lbl, stretch=1)

            body_layout.addLayout(row)

        body_layout.addStretch()

        # ── Footer ───────────────────────────────────────────────────────
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 8, 0, 0)
        footer.addStretch()

        btn_avanti = QPushButton("Avanti →")
        btn_avanti.setFixedSize(120, 34)
        btn_avanti.setStyleSheet(
            "QPushButton {"
            "  background-color: #1a3a5c; color: white;"
            "  border-radius: 6px; font-size: 11px; font-weight: bold;"
            "}"
            "QPushButton:hover { background-color: #2a5a8c; }"
        )
        btn_avanti.clicked.connect(self.accept)
        footer.addWidget(btn_avanti)

        body_layout.addLayout(footer)
        root.addWidget(body, stretch=1)
