"""pytest configuration for create_project tests.

Requires pytest-qgis and a QGIS installation accessible to Python
(e.g. via `uv venv --system-site-packages` or equivalent).
"""
import sys
from pathlib import Path

import pytest

# Make the plugin package importable as `create_project.*`
_plugins_dir = str(Path(__file__).resolve().parents[2])
if _plugins_dir not in sys.path:
    sys.path.insert(0, _plugins_dir)


@pytest.fixture(scope="session", autouse=True)
def _qgis_session(qgis_app):
    """Initialize QGIS once for the entire test session.

    The `qgis_app` fixture is provided by pytest-qgis.  Making it
    session-scoped and autouse means every test can safely instantiate
    QgsVectorLayer, QgsProject, etc. without requesting the fixture
    explicitly.
    """
    yield
