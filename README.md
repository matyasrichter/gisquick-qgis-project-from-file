# gisquick_project_from_file QGIS Server Plugin

## Running tests

Tests run inside Docker against a real QGIS installation (QGIS 3.28).

**Run all tests:**

```bash
make test
```

**Run a subset of tests** (pass any pytest flags via `PYTEST_ARGS`):

```bash
make test PYTEST_ARGS="-k features_array"
make test PYTEST_ARGS="-x -v tests/test_handler.py"
```


### Why Docker?

QGIS cannot be installed via pip — it must be installed at the system level and exposes its Python bindings (`qgis.core`, `qgis.server`, etc.) as part of that installation. The tests load real `QgsVectorLayer` and `QgsRasterLayer` objects, so they need a live QGIS instance to run against.

Docker provides a reproducible environment with QGIS pre-installed. `make test` builds an image from `.devcontainer/Dockerfile` (based on `qgis/qgis:release-3_28`), adds `pytest` and `pytest-qgis`, then mounts the plugin directory into the container and runs `pytest tests/`. QGIS is initialised once per session via the `qgis_app` fixture provided by `pytest-qgis`.
