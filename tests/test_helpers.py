"""Tests for pure-logic helper functions in gisquick_project_from_file_handler.py.

These functions contain no QGIS layer or project I/O — they are tested
with plain pytest and standard library mocks only.
"""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from gisquick_project_from_file.config import GisquickProjectFromFileConfig, load_config
from gisquick_project_from_file.gisquick_project_from_file_handler import (
    GisquickProjectFromFileHandler,
    _extract_bearer_token,
    _get_header,
    _media_kind,
)


# ---------------------------------------------------------------------------
# Helpers shared across test modules
# ---------------------------------------------------------------------------

def _make_header_request(headers: dict):
    """Return a mock request whose .header() does case-insensitive lookup."""
    req = MagicMock(spec=[])  # no auto-attributes

    def header(name):
        for k, v in headers.items():
            if k.lower() == name.lower():
                return v
        return None

    req.header = header
    return req


# ---------------------------------------------------------------------------
# _media_kind
# ---------------------------------------------------------------------------

class TestMediaKind:

    # --- vector extensions ---

    @pytest.mark.parametrize("ext", [".geojson", ".json", ".gpkg", ".shp", ".fgb", ".gml", ".kml", ".csv"])
    def test_vector_extensions(self, ext):
        assert _media_kind(ext, "") == "vector"

    def test_extension_case_insensitive(self):
        assert _media_kind(".GeoJSON", "") == "vector"
        assert _media_kind(".JSON", "") == "vector"

    # --- raster extensions ---

    @pytest.mark.parametrize("ext", [".tif", ".tiff", ".vrt", ".img", ".jp2", ".png", ".jpg", ".jpeg"])
    def test_raster_extensions(self, ext):
        assert _media_kind(ext, "") == "raster"

    # --- mime-type fallback (unknown extension) ---

    @pytest.mark.parametrize("mime", [
        "application/geo+json",
        "application/geopackage+sqlite3",
        "application/vnd.google-earth.kml+xml",
    ])
    def test_vector_mime_types(self, mime):
        assert _media_kind("", mime) == "vector"

    @pytest.mark.parametrize("mime", ["image/tiff", "image/png", "image/jpeg"])
    def test_image_mime_prefix_is_raster(self, mime):
        assert _media_kind("", mime) == "raster"

    def test_mime_case_insensitive(self):
        assert _media_kind("", "Application/Geo+JSON") == "vector"

    # --- unknown ---

    def test_unknown_extension_and_mime(self):
        assert _media_kind(".xyz", "") == "unknown"

    def test_empty_extension_and_mime(self):
        assert _media_kind("", "") == "unknown"

    # --- extension takes precedence over mime ---

    def test_extension_wins_over_mime(self):
        assert _media_kind(".geojson", "application/geo+json") == "vector"


# ---------------------------------------------------------------------------
# _get_header
# ---------------------------------------------------------------------------

class TestGetHeader:

    def test_returns_matching_header(self):
        req = _make_header_request({"Authorization": "Token abc"})
        assert _get_header(req, "Authorization") == "Token abc"

    def test_case_insensitive_lookup(self):
        req = _make_header_request({"authorization": "Token xyz"})
        assert _get_header(req, "Authorization") == "Token xyz"

    def test_missing_header_returns_empty_string(self):
        req = _make_header_request({})
        assert _get_header(req, "Authorization") == ""



# ---------------------------------------------------------------------------
# _extract_bearer_token
# ---------------------------------------------------------------------------

class TestExtractBearerToken:

    def _req(self, auth_header):
        return _make_header_request({"Authorization": auth_header} if auth_header is not None else {})

    def test_valid_token(self):
        assert _extract_bearer_token(self._req("Token abc123")) == "abc123"

    def test_lowercase_token_prefix(self):
        assert _extract_bearer_token(self._req("token mysecret")) == "mysecret"

    def test_surrounding_whitespace_is_stripped(self):
        assert _extract_bearer_token(self._req("Token   padded  ")) == "padded"

    def test_bearer_scheme_not_supported(self):
        assert _extract_bearer_token(self._req("Bearer abc123")) == ""

    def test_no_authorization_header(self):
        assert _extract_bearer_token(self._req(None)) == ""

    def test_empty_authorization_header(self):
        assert _extract_bearer_token(self._req("")) == ""


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------

class TestLoadConfig:

    def test_returns_config_with_secret(self):
        with patch.dict(os.environ, {"GISQUICK_PROJECT_FROM_FILE_SHARED_SECRET": "supersecret"}):
            cfg = load_config()
        assert isinstance(cfg, GisquickProjectFromFileConfig)
        assert cfg.shared_secret == "supersecret"

    def test_strips_whitespace(self):
        with patch.dict(os.environ, {"GISQUICK_PROJECT_FROM_FILE_SHARED_SECRET": "  s3cr3t  "}):
            cfg = load_config()
        assert cfg.shared_secret == "s3cr3t"

    def test_returns_empty_string_when_env_unset(self):
        env = {k: v for k, v in os.environ.items() if k != "GISQUICK_PROJECT_FROM_FILE_SHARED_SECRET"}
        with patch.dict(os.environ, env, clear=True):
            cfg = load_config()
        assert cfg.shared_secret == ""


# ---------------------------------------------------------------------------
# _read_json_payload
# ---------------------------------------------------------------------------

class TestReadJsonPayload:

    def _req(self, body):
        req = MagicMock()
        req.data.return_value = body
        return req

    def test_valid_json(self):
        payload = {"job_dir": "/tmp/job", "files": []}
        result = GisquickProjectFromFileHandler._read_json_payload(self._req(json.dumps(payload).encode()))
        assert result == payload

    def test_none_body_raises(self):
        with pytest.raises(ValueError):
            GisquickProjectFromFileHandler._read_json_payload(self._req(None))

    def test_empty_body_raises(self):
        with pytest.raises(ValueError):
            GisquickProjectFromFileHandler._read_json_payload(self._req(b""))

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError):
            GisquickProjectFromFileHandler._read_json_payload(self._req(b"{not valid json}"))

    def test_unicode_json(self):
        payload = {"name": "\u00e9l\u00e8ve"}
        result = GisquickProjectFromFileHandler._read_json_payload(
            self._req(json.dumps(payload).encode("utf-8"))
        )
        assert result["name"] == "\u00e9l\u00e8ve"
