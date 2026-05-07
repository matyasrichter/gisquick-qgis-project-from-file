"""QGIS server entrypoint for the gisquick_qgis_server_processing plugin."""


def serverClassFactory(server_iface):
    """Create the server plugin instance."""
    from .gisquick_qgis_server_processing_plugin import GisquickQgisServerProcessingServerPlugin

    return GisquickQgisServerProcessingServerPlugin(server_iface)
