from __future__ import annotations

import hmac
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from qgis.PyQt.QtCore import QRegularExpression
from qgis.server import QgsServerOgcApi, QgsServerOgcApiHandler, QgsServerRequest

from .config import load_config
from .geometry import (
    _fix_vector_layer_geometries,
    _normalize_geojson_if_feature_array,
    _orient_polygon_ccw,
)

_log = logging.getLogger(__name__)

_VECTOR_EXTENSIONS = {".gpkg", ".geojson", ".json", ".shp", ".fgb", ".gml", ".kml", ".csv"}
_RASTER_EXTENSIONS = {".tif", ".tiff", ".vrt", ".img", ".jp2", ".png", ".jpg", ".jpeg"}
_VECTOR_MIME = {
    "application/geopackage+sqlite3",
    "application/geo+json",
    "application/vnd.google-earth.kml+xml",
}


def _media_kind(extension: str, mime_type: str) -> str:
    """Return 'vector', 'raster', or 'unknown'."""
    ext = extension.lower()
    if ext in _VECTOR_EXTENSIONS:
        return "vector"
    if ext in _RASTER_EXTENSIONS:
        return "raster"
    mime = (mime_type or "").lower()
    if mime in _VECTOR_MIME:
        return "vector"
    if mime.startswith("image/"):
        return "raster"
    return "unknown"


def _get_header(request: Any, name: str) -> str:
    value = request.header(name)
    return str(value) if value else ""


def _extract_bearer_token(request: Any) -> str:
    auth_header = _get_header(request, "Authorization").strip()
    if auth_header.lower().startswith("token "):
        return auth_header[6:].strip()
    return ""


def _read_json_payload(request) -> Dict[str, Any]:
    raw_data = request.data()
    if raw_data is None:
        raise ValueError("Request body is required")
    data_bytes = bytes(raw_data)
    if not data_bytes:
        raise ValueError("Request body is empty")
    try:
        return json.loads(data_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Request body must be valid JSON") from exc


def _write_json(context, payload: Dict[str, Any], status_code: int) -> None:
    response = context.response()
    if response is None:
        return
    response.setStatusCode(int(status_code))
    body = json.dumps(payload, ensure_ascii=False)
    response.setResponseHeader("Content-Type", "application/json")
    response.write(body)


def _load_vector(full_path: Path, name: str):
    from qgis.core import QgsVectorLayer

    _normalize_geojson_if_feature_array(full_path)
    layer = QgsVectorLayer(str(full_path), name, "ogr")
    if not layer.isValid():
        return None
    _fix_vector_layer_geometries(layer)
    return layer


def _load_raster(full_path: Path, name: str):
    from qgis.core import QgsRasterLayer

    layer = QgsRasterLayer(str(full_path), name)
    return layer if layer.isValid() else None


def _load_unknown(full_path: Path, name: str):
    layer = _load_vector(full_path, name)
    if layer is not None:
        return layer
    return _load_raster(full_path, name)


_LOADERS = {
    "vector": _load_vector,
    "raster": _load_raster,
    "unknown": _load_unknown,
}


class GisquickProjectFromFileHandler(QgsServerOgcApiHandler):

    def __init__(self):
        super().__init__()
        self._config = load_config()

    def path(self):
        return QRegularExpression(r"^(?:/gisquick-project-from-file)?/?$")

    def operationId(self):
        return "gisquickProjectFromFile"

    def summary(self):
        return "Gisquick - Create a QGIS project from pre-downloaded job files"

    def description(self):
        return (
            "Loads files from a job directory as QGIS vector/raster layers, "
            "creates a QGIS project, saves it as results.qgs, and returns the filename."
        )

    def linkTitle(self):
        return "Gisquick - Project from file"

    def linkType(self):
        return QgsServerOgcApi.data

    def schema(self, _context):
        return {
            "summary": self.summary(),
            "description": self.description(),
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["job_dir", "files"],
                            "properties": {
                                "job_dir": {"type": "string"},
                                "files": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "required": ["path"],
                                        "properties": {
                                            "path": {"type": "string"},
                                            "type": {"type": "string"},
                                        },
                                    },
                                },
                            },
                        }
                    }
                },
            },
            "responses": {
                "200": {"description": "Project created successfully"},
                "400": {"description": "Invalid request payload"},
                "401": {"description": "Authentication failed"},
                "422": {"description": "No files could be loaded as QGIS layers"},
                "500": {"description": "Failed to save the project file"},
            },
        }

    def handleRequest(self, context):
        request = context.request()
        if request is None:
            _write_json(context, {"error": "Missing server request context"}, 500)
            return

        if request.method() != QgsServerRequest.PostMethod:
            _write_json(context, {"error": "Only POST is supported"}, 405)
            return

        if err := self._authenticate(request):
            _write_json(context, {"error": err}, 401)
            return

        payload, err = self._parse_payload(request)
        if err:
            _write_json(context, {"error": err}, 400)
            return

        job_dir = Path("/publish") / Path(payload["job_dir"])
        layers = self._load_layers(job_dir, payload["files"])
        if not layers:
            _write_json(context, {"error": f"No files could be loaded as QGIS layers. Tried files: [{', '.join(str(job_dir / f['path']) for f in payload['files'])}]"}, 422)
            return

        from qgis.core import QgsProject, QgsVectorLayer

        project = QgsProject()
        for layer in layers:
            project.addMapLayer(layer)

        vector_ids = [layer.id() for layer in layers if isinstance(layer, QgsVectorLayer)]
        if vector_ids:
            project.writeEntry("WFSLayers", "/", vector_ids)

        project_path = job_dir / "results.qgs"
        if not project.write(str(project_path)):
            _write_json(context, {"error": "Failed to write project file"}, 500)
            return

        _write_json(context, {"project_file": "results.qgs"}, 200)

    def _authenticate(self, request) -> Optional[str]:
        """Return None on success, or an error message on failure."""
        token = _extract_bearer_token(request)
        if not token:
            return "Missing auth token"
        expected = self._config.shared_secret
        if not expected:
            return "GISQUICK_PROJECT_FROM_FILE_SHARED_SECRET is not configured"
        if not hmac.compare_digest(token, expected):
            return "Invalid auth token"
        return None

    def _parse_payload(self, request) -> Tuple[Dict, Optional[str]]:
        """Return (payload, None) on success, or ({}, error_message) on failure."""
        try:
            payload = _read_json_payload(request)
        except ValueError as exc:
            return {}, str(exc)
        job_dir_str = payload.get("job_dir", "")
        files = payload.get("files", [])
        if not isinstance(job_dir_str, str) or not job_dir_str.strip():
            return {}, "job_dir must be a non-empty string"
        if not isinstance(files, list) or not files:
            return {}, "files must be a non-empty list"
        return payload, None

    @staticmethod
    def _load_layers(job_dir: Path, files: List[Dict[str, Any]]) -> list:
        loaded = []
        for entry in files:
            if not isinstance(entry, dict):
                continue
            rel_path = entry.get("path", "")
            mime_type = entry.get("type", "") or ""
            if not isinstance(rel_path, str) or not rel_path:
                continue
            if "/" in rel_path or "\\" in rel_path or ".." in rel_path:
                continue

            full_path = job_dir / rel_path
            if not full_path.is_file():
                continue

            name = full_path.stem
            kind = _media_kind(full_path.suffix, mime_type)
            layer = _LOADERS[kind](full_path, name)
            if layer is not None:
                loaded.append(layer)

        return loaded

    # Shims for test-facing static method calls on the class
    @staticmethod
    def _fix_vector_layer_geometries(layer) -> None:
        return _fix_vector_layer_geometries(layer)

    @staticmethod
    def _orient_polygon_ccw(geom):
        return _orient_polygon_ccw(geom)

    @staticmethod
    def _read_json_payload(request) -> Dict[str, Any]:
        return _read_json_payload(request)
