import os
from qgis.PyQt.QtGui import QIcon
from .compat import QAction, exec_dialog
from .dialog import RoadInspectorDialog
from .splash import SplashScreen


class RoadInspectorPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
        self.action = QAction(icon, "VISTA", self.iface.mainWindow())
        self.action.setToolTip("Apri VISTA")
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("VISTA", self.action)

    def unload(self):
        self.iface.removeToolBarIcon(self.action)
        self.iface.removePluginMenu("VISTA", self.action)
        if self.dialog:
            self.dialog.close()

    def run(self):
        # Mostra lo splash screen ad ogni avvio
        splash = SplashScreen(self.iface.mainWindow())
        exec_dialog(splash)
        if self.dialog is None:
            self.dialog = RoadInspectorDialog(self.iface)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
