"""QGIS server entrypoint for the create_project plugin."""


def serverClassFactory(server_iface):
    """Create the server plugin instance."""
    from .create_project_plugin import CreateProjectServerPlugin

    return CreateProjectServerPlugin(server_iface)
