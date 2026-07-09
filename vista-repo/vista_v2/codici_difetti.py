"""
Carica il dizionario dei codici difetti da codici.txt
nella stessa cartella del plugin.
"""

import os
import ast

CODICI_DICT = {}


def _carica():
    global CODICI_DICT
    percorso = os.path.join(os.path.dirname(__file__), "codici.txt")
    if not os.path.exists(percorso):
        return
    try:
        testo = open(percorso, encoding="utf-8").read()
        idx = testo.find("codici_dict")
        if idx == -1:
            return
        # Valuta solo il letterale del dizionario (niente exec di codice arbitrario)
        idx_graffa = testo.find("{", idx)
        if idx_graffa == -1:
            return
        dato = ast.literal_eval(testo[idx_graffa:].strip())
        if isinstance(dato, dict):
            CODICI_DICT = dato
    except Exception:
        pass


_carica()
