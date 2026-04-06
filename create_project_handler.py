from __future__ import annotations

import hmac
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from qgis.PyQt.QtCore import QRegularExpression
from qgis.server import QgsServerOgcApi, QgsServerOgcApiHandler, QgsServerRequest

from .config import load_config

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
    if hasattr(request, "header"):
        value = request.header(name)
        if value:
            return str(value)
    if hasattr(request, "headers"):
        headers = request.headers()
        if isinstance(headers, dict):
            for key, value in headers.items():
                if str(key).lower() == name.lower():
                    return str(value)
    return ""


def _extract_bearer_token(request: Any) -> str:
    auth_header = _get_header(request, "Authorization").strip()
    if auth_header.lower().startswith("token "):
        return auth_header[6:].strip()
    return ""


class CreateProjectHandler(QgsServerOgcApiHandler):

    def __init__(self):
        super().__init__()
        self._config = load_config()

    def path(self):
        return QRegularExpression(r"^(?:/create-project)?/?$")

    def operationId(self):
        return "createProject"

    def summary(self):
        return "Create a QGIS project from pre-downloaded job files"

    def description(self):
        return (
            "Loads files from a job directory as QGIS vector/raster layers, "
            "creates a QGIS project, saves it as results.qgs, and returns the filename."
        )

    def linkTitle(self):
        return "Create project"

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
            self._write_json(context, {"error": "Missing server request context"}, 500)
            return

        if request.method() != QgsServerRequest.PostMethod:
            self._write_json(context, {"error": "Only POST is supported"}, 405)
            return

        # Auth
        token = _extract_bearer_token(request)
        if not token:
            self._write_json(context, {"error": "Missing auth token"}, 401)
            return
        expected = self._config.shared_secret
        if not expected:
            self._write_json(context, {"error": "CREATE_PROJECT_SHARED_SECRET is not configured"}, 401)
            return
        if not hmac.compare_digest(token, expected):
            self._write_json(context, {"error": "Invalid auth token"}, 401)
            return

        # Parse body
        try:
            payload = self._read_json_payload(request)
        except ValueError as exc:
            self._write_json(context, {"error": str(exc)}, 400)
            return

        job_dir_str = payload.get("job_dir", "")
        files = payload.get("files", [])
        if not isinstance(job_dir_str, str) or not job_dir_str.strip():
            self._write_json(context, {"error": "job_dir must be a non-empty string"}, 400)
            return
        if not isinstance(files, list) or not files:
            self._write_json(context, {"error": "files must be a non-empty list"}, 400)
            return

        job_dir = Path("/publish") / Path(job_dir_str)

        # Load layers
        layers = self._load_layers(job_dir, files)
        if not layers:
            self._write_json(context, {"error": f"No files could be loaded as QGIS layers. Tried files: [{', '.join(str(job_dir / f['path']) for f in files)}]"}, 422)
            return

        # Build and save project
        from qgis.core import QgsProject

        project = QgsProject()
        for layer in layers:
            project.addMapLayer(layer)

        project_path = job_dir / "results.qgs"
        if not project.write(str(project_path)):
            self._write_json(context, {"error": "Failed to write project file"}, 500)
            return

        self._write_json(context, {"project_file": "results.qgs"}, 200)

    @staticmethod
    def _normalize_geojson_if_feature_array(path: Path) -> None:
        """Rewrite path in-place as a FeatureCollection if it contains a bare Feature array.

        Some API responses return ``[Feature, ...]`` instead of the standard
        ``{"type": "FeatureCollection", "features": [...]}`` wrapper.  OGR does
        not recognise the bare-array format, so we normalise it before loading.
        """
        if path.suffix.lower() not in {".json", ".geojson"}:
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(data, list):
            return
        if not data or not isinstance(data[0], dict) or data[0].get("type") != "Feature":
            return
        path.write_text(
            json.dumps({"type": "FeatureCollection", "features": data}, ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def _load_layers(job_dir: Path, files: List[Dict[str, Any]]) -> list:
        from qgis.core import QgsRasterLayer, QgsVectorLayer

        loaded = []
        for entry in files:
            if not isinstance(entry, dict):
                continue
            rel_path = entry.get("path", "")
            mime_type = entry.get("type", "") or ""
            if not isinstance(rel_path, str) or not rel_path:
                continue
            # Reject paths with separators or traversal
            if "/" in rel_path or "\\" in rel_path or ".." in rel_path:
                continue

            full_path = job_dir / rel_path
            if not full_path.is_file():
                continue

            name = full_path.stem
            kind = _media_kind(full_path.suffix, mime_type)

            layer = None
            if kind == "vector":
                CreateProjectHandler._normalize_geojson_if_feature_array(full_path)
                layer = QgsVectorLayer(str(full_path), name, "ogr")
                if not layer.isValid():
                    layer = None
            elif kind == "raster":
                layer = QgsRasterLayer(str(full_path), name)
                if not layer.isValid():
                    layer = None
            else:
                # Unknown extension: try vector then raster
                candidate = QgsVectorLayer(str(full_path), name, "ogr")
                if candidate.isValid():
                    layer = candidate
                else:
                    candidate = QgsRasterLayer(str(full_path), name)
                    if candidate.isValid():
                        layer = candidate

            if layer is not None:
                loaded.append(layer)

        return loaded

    @staticmethod
    def _read_json_payload(request) -> Dict[str, Any]:
        raw_data = request.data()
        if raw_data is None:
            raise ValueError("Request body is required")
        if hasattr(raw_data, "data"):
            try:
                data_bytes = bytes(raw_data)
            except TypeError:
                data_bytes = raw_data.data()
        else:
            try:
                data_bytes = bytes(raw_data)
            except TypeError:
                data_bytes = str(raw_data).encode("utf-8")
        if not data_bytes:
            raise ValueError("Request body is empty")
        try:
            return json.loads(data_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Request body must be valid JSON") from exc

    @staticmethod
    def _write_json(context, payload: Dict[str, Any], status_code: int) -> None:
        response = context.response()
        if response is None:
            return
        response.setStatusCode(int(status_code))
        body = json.dumps(payload, ensure_ascii=False)
        if hasattr(response, "setHeader"):
            response.setHeader("Content-Type", "application/json")
        elif hasattr(response, "setResponseHeader"):
            response.setResponseHeader("Content-Type", "application/json")
        response.write(body)
