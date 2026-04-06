from __future__ import annotations

from qgis.core import Qgis, QgsMessageLog
from qgis.server import QgsServerOgcApi

from .create_project_handler import CreateProjectHandler


class CreateProjectServerPlugin:
    API_NAME = "create-project"
    API_VERSION = "1.0"
    API_ROOT = "/create-project"

    def __init__(self, server_iface):
        self._server_iface = server_iface
        self._api = None
        self._register_api()

    def _log(self, message: str, is_warning: bool = False) -> None:
        if QgsMessageLog is None:
            return
        if Qgis is None:
            QgsMessageLog.logMessage(message, "CreateProject")
            return
        level = Qgis.Warning if is_warning else Qgis.Info
        QgsMessageLog.logMessage(message, "CreateProject", level=level)

    def _register_api(self) -> None:
        if QgsServerOgcApi is None:
            self._log("QGIS server API bindings are not available", is_warning=True)
            return
        api = QgsServerOgcApi(
            self._server_iface,
            self.API_ROOT,
            self.API_NAME,
            "Create QGIS project from pre-downloaded job files",
            self.API_VERSION,
        )
        api.registerHandler(CreateProjectHandler())
        self._server_iface.serviceRegistry().registerApi(api)
        self._api = api
        self._log("Create project API registered")

    def unload(self) -> None:
        if self._api is None:
            return
        self._server_iface.serviceRegistry().unregisterApi(self.API_NAME, self.API_VERSION)
        self._api = None
        self._log("Create project API unregistered")
