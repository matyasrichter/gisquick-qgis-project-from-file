from __future__ import annotations

from qgis.core import Qgis, QgsMessageLog
from qgis.server import QgsServerOgcApi

from .gisquick_qgis_server_processing_handler import GisquickQgisServerProcessingHandler


class GisquickQgisServerProcessingServerPlugin:
    API_NAME = "gisquick-qgis-server-processing"
    API_VERSION = "1.0"
    API_ROOT = "/gisquick-qgis-server-processing"

    def __init__(self, server_iface):
        self._server_iface = server_iface
        self._api = None
        self._register_api()

    def _log(self, message: str, is_warning: bool = False) -> None:
        if QgsMessageLog is None:
            return
        if Qgis is None:
            QgsMessageLog.logMessage(message, "GisquickQgisServerProcessing")
            return
        level = Qgis.Warning if is_warning else Qgis.Info
        QgsMessageLog.logMessage(message, "GisquickQgisServerProcessing", level=level)

    def _register_api(self) -> None:
        if QgsServerOgcApi is None:
            self._log("QGIS server API bindings are not available", is_warning=True)
            return
        api = QgsServerOgcApi(
            self._server_iface,
            self.API_ROOT,
            self.API_NAME,
            "Gisquick - Create QGIS project from pre-downloaded job files",
            self.API_VERSION,
        )
        api.registerHandler(GisquickQgisServerProcessingHandler())
        self._server_iface.serviceRegistry().registerApi(api)
        self._api = api
        self._log("Gisquick qgis-server-processing API registered")

    def unload(self) -> None:
        if self._api is None:
            return
        self._server_iface.serviceRegistry().unregisterApi(self.API_NAME, self.API_VERSION)
        self._api = None
        self._log("Gisquick qgis-server-processing API unregistered")
