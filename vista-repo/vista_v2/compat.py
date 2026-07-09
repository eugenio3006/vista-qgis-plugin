"""
Strato di compatibilità QGIS 3 (Qt5 / PyQt5) ↔ QGIS 4 (Qt6 / PyQt6).

Differenze gestite:
  • enum Qt: in PyQt6 sono "scoped" (Qt.AlignmentFlag.AlignCenter invece di
    Qt.AlignCenter). Qui ogni costante viene risolta provando prima la forma
    non-scoped (PyQt5) e poi quella scoped (PyQt6).
  • exec_() rimosso in PyQt6 → helper exec_dialog().
  • QAction spostata da QtWidgets (Qt5) a QtGui (Qt6).
  • QgsField: in QGIS 4 il costruttore con QVariant.Type è stato rimosso
    in favore di QMetaType.Type → factory crea_campo().
  • QgsPalLayerSettings.AroundPoint → Qgis.LabelPlacement.AroundPoint
    (QGIS ≥ 3.26 / 4.x) → helper placement_around_point().
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import QFrame, QMessageBox
from qgis.core import QgsField

# QAction: QtWidgets in Qt5, QtGui in Qt6
try:
    from qgis.PyQt.QtGui import QAction          # Qt6 (e qgis.PyQt shim)
except ImportError:
    from qgis.PyQt.QtWidgets import QAction      # Qt5


def _enum(owner, scope_name, member):
    """
    Restituisce owner.member (Qt5, enum non-scoped) oppure
    owner.scope_name.member (Qt6, enum scoped).
    """
    val = getattr(owner, member, None)
    if val is not None:
        return val
    return getattr(getattr(owner, scope_name), member)


# ── Qt ──────────────────────────────────────────────────────────────────────
ALIGN_CENTER  = _enum(Qt, "AlignmentFlag", "AlignCenter")
ALIGN_RIGHT   = _enum(Qt, "AlignmentFlag", "AlignRight")
ALIGN_VCENTER = _enum(Qt, "AlignmentFlag", "AlignVCenter")
ALIGN_JUSTIFY = _enum(Qt, "AlignmentFlag", "AlignJustify")

KEEP_ASPECT_RATIO = _enum(Qt, "AspectRatioMode", "KeepAspectRatio")
SMOOTH_TRANSFORM  = _enum(Qt, "TransformationMode", "SmoothTransformation")

WIN_DIALOG    = _enum(Qt, "WindowType", "Dialog")
WIN_FRAMELESS = _enum(Qt, "WindowType", "FramelessWindowHint")
WIN_MAX_BTN   = _enum(Qt, "WindowType", "WindowMaximizeButtonHint")

SCROLLBAR_AS_NEEDED = _enum(Qt, "ScrollBarPolicy", "ScrollBarAsNeeded")

# ── QFont / QFrame / QMessageBox ───────────────────────────────────────────
FONT_BOLD = _enum(QFont, "Weight", "Bold")

FRAME_HLINE   = _enum(QFrame, "Shape", "HLine")
FRAME_NOFRAME = _enum(QFrame, "Shape", "NoFrame")

MSG_ICON_WARNING  = _enum(QMessageBox, "Icon", "Warning")
MSG_ICON_QUESTION = _enum(QMessageBox, "Icon", "Question")
MSG_BTN_OK  = _enum(QMessageBox, "StandardButton", "Ok")
MSG_BTN_YES = _enum(QMessageBox, "StandardButton", "Yes")
MSG_BTN_NO  = _enum(QMessageBox, "StandardButton", "No")


def exec_dialog(dlg):
    """exec_() esiste solo in PyQt5, exec() in entrambi i binding recenti."""
    fn = getattr(dlg, "exec_", None) or dlg.exec
    return fn()


# ── QgsField ────────────────────────────────────────────────────────────────
def _tipi_campo():
    """
    QGIS 3 usa QVariant.Type, QGIS 4 richiede QMetaType.Type.
    Prova il vecchio costruttore; se fallisce passa a QMetaType.
    """
    try:
        from qgis.PyQt.QtCore import QVariant
        tipi = {
            "string": QVariant.String,
            "double": QVariant.Double,
            "int":    QVariant.Int,
        }
        QgsField("compat_test", tipi["string"])   # verifica che sia accettato
        return tipi
    except Exception:
        from qgis.PyQt.QtCore import QMetaType
        return {
            "string": QMetaType.Type.QString,
            "double": QMetaType.Type.Double,
            "int":    QMetaType.Type.Int,
        }


_TIPI_CAMPO = _tipi_campo()


def crea_campo(nome, tipo):
    """Crea un QgsField compatibile. tipo: 'string' | 'double' | 'int'."""
    return QgsField(nome, _TIPI_CAMPO[tipo])


# ── Etichettatura ───────────────────────────────────────────────────────────
def placement_around_point():
    """Enum di posizionamento etichette compatibile con tutte le versioni."""
    try:
        from qgis.core import Qgis
        return Qgis.LabelPlacement.AroundPoint        # QGIS ≥ 3.26 e 4.x
    except (ImportError, AttributeError):
        from qgis.core import QgsPalLayerSettings
        return QgsPalLayerSettings.AroundPoint        # QGIS 3.0 – 3.24
