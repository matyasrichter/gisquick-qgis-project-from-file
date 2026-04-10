"""QGIS server entrypoint for the gisquick_project_from_file plugin."""


def serverClassFactory(server_iface):
    """Create the server plugin instance."""
    from .gisquick_project_from_file_plugin import GisquickProjectFromFileServerPlugin

    return GisquickProjectFromFileServerPlugin(server_iface)
