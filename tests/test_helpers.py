"""Tests for pure-logic helper functions in gisquick_qgis_server_processing_handler.py.

These functions contain no QGIS layer or project I/O — they are tested
with plain pytest and standard library mocks only.
"""
from __future__ import annotations

import io
import json
import os
import tarfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gisquick_qgis_server_processing.archives import (
    archive_stem,
    extract_archive,
    is_archive,
    scan_spatial_files,
)
from gisquick_qgis_server_processing.config import GisquickQgisServerProcessingConfig, load_config
from gisquick_qgis_server_processing.gisquick_qgis_server_processing_handler import (
    GisquickQgisServerProcessingHandler,
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
        with patch.dict(os.environ, {"GISQUICK_QGIS_SERVER_PROCESSING_SHARED_SECRET": "supersecret"}):
            cfg = load_config()
        assert isinstance(cfg, GisquickQgisServerProcessingConfig)
        assert cfg.shared_secret == "supersecret"

    def test_strips_whitespace(self):
        with patch.dict(os.environ, {"GISQUICK_QGIS_SERVER_PROCESSING_SHARED_SECRET": "  s3cr3t  "}):
            cfg = load_config()
        assert cfg.shared_secret == "s3cr3t"

    def test_returns_empty_string_when_env_unset(self):
        env = {k: v for k, v in os.environ.items() if k != "GISQUICK_QGIS_SERVER_PROCESSING_SHARED_SECRET"}
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
        result = GisquickQgisServerProcessingHandler._read_json_payload(self._req(json.dumps(payload).encode()))
        assert result == payload

    def test_none_body_raises(self):
        with pytest.raises(ValueError):
            GisquickQgisServerProcessingHandler._read_json_payload(self._req(None))

    def test_empty_body_raises(self):
        with pytest.raises(ValueError):
            GisquickQgisServerProcessingHandler._read_json_payload(self._req(b""))

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError):
            GisquickQgisServerProcessingHandler._read_json_payload(self._req(b"{not valid json}"))

    def test_unicode_json(self):
        payload = {"name": "\u00e9l\u00e8ve"}
        result = GisquickQgisServerProcessingHandler._read_json_payload(
            self._req(json.dumps(payload).encode("utf-8"))
        )
        assert result["name"] == "\u00e9l\u00e8ve"


# ---------------------------------------------------------------------------
# archives \u2014 is_archive
# ---------------------------------------------------------------------------

class TestIsArchive:

    @pytest.mark.parametrize("name", [
        "data.zip", "DATA.ZIP", "results.tar", "output.tgz",
        "output.tbz2", "output.txz", "results.tar.gz",
        "results.tar.bz2", "results.tar.xz",
    ])
    def test_archive_extensions_recognised(self, name):
        assert is_archive(name) is True

    @pytest.mark.parametrize("name", [
        "data.gpkg", "track.geojson", "image.png", "notes.txt", "data.gz",
    ])
    def test_non_archive_extensions_not_recognised(self, name):
        assert is_archive(name) is False


# ---------------------------------------------------------------------------
# archives \u2014 archive_stem
# ---------------------------------------------------------------------------

class TestArchiveStem:

    @pytest.mark.parametrize("name,expected", [
        ("results.zip", "results"),
        ("results.tar", "results"),
        ("results.tgz", "results"),
        ("results.tbz2", "results"),
        ("results.txz", "results"),
        ("results.tar.gz", "results"),
        ("results.tar.bz2", "results"),
        ("results.tar.xz", "results"),
        ("my.results.zip", "my.results"),
        ("my.results.tar.gz", "my.results"),
    ])
    def test_stem_stripped_correctly(self, name, expected):
        assert archive_stem(name) == expected


# ---------------------------------------------------------------------------
# archives \u2014 extract_archive
# ---------------------------------------------------------------------------

def _make_zip(path: Path, members: dict[str, bytes]) -> None:
    """Write a zip file containing the given {member_name: content} dict."""
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)


def _make_tar_gz(path: Path, members: dict[str, bytes]) -> None:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in members.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    path.write_bytes(buf.getvalue())


class TestExtractArchive:

    def test_zip_extracts_single_file(self, tmp_path):
        archive = tmp_path / "data.zip"
        _make_zip(archive, {"data.geojson": b'{"type":"Point","coordinates":[0,0]}'})
        dest = tmp_path / "data"

        extract_archive(archive, dest)

        assert (dest / "data.geojson").is_file()

    def test_tar_gz_extracts_single_file(self, tmp_path):
        archive = tmp_path / "data.tar.gz"
        _make_tar_gz(archive, {"track.geojson": b'{"type":"Point","coordinates":[1,2]}'})
        dest = tmp_path / "data"

        extract_archive(archive, dest)

        assert (dest / "track.geojson").is_file()

    def test_zip_slip_raises_before_extracting(self, tmp_path):
        archive = tmp_path / "evil.zip"
        _make_zip(archive, {"../../evil.txt": b"bad"})
        dest = tmp_path / "dest"

        with pytest.raises(ValueError, match="ZIP slip"):
            extract_archive(archive, dest)

        assert not (tmp_path.parent / "evil.txt").exists()

    def test_tar_slip_raises_before_extracting(self, tmp_path):
        archive = tmp_path / "evil.tar.gz"
        _make_tar_gz(archive, {"../../evil.txt": b"bad"})
        dest = tmp_path / "dest"

        with pytest.raises(ValueError, match="ZIP slip"):
            extract_archive(archive, dest)

    def test_dest_dir_created_if_absent(self, tmp_path):
        archive = tmp_path / "data.zip"
        _make_zip(archive, {"f.txt": b"hello"})
        dest = tmp_path / "new" / "subdir"

        extract_archive(archive, dest)

        assert dest.is_dir()

    def test_corrupt_zip_raises(self, tmp_path):
        archive = tmp_path / "corrupt.zip"
        archive.write_bytes(b"not a zip file at all")
        dest = tmp_path / "dest"

        with pytest.raises(Exception):
            extract_archive(archive, dest)


# ---------------------------------------------------------------------------
# archives \u2014 scan_spatial_files
# ---------------------------------------------------------------------------

class TestScanSpatialFiles:

    SPATIAL_EXTENSIONS = frozenset({".gpkg", ".geojson", ".shp", ".tif", ".png"})

    def test_finds_spatial_files(self, tmp_path):
        (tmp_path / "data.gpkg").write_bytes(b"")
        (tmp_path / "track.geojson").write_bytes(b"")
        (tmp_path / "image.tif").write_bytes(b"")

        result = scan_spatial_files(tmp_path, self.SPATIAL_EXTENSIONS)

        names = {f.name for f in result}
        assert names == {"data.gpkg", "track.geojson", "image.tif"}

    def test_ignores_non_spatial_files(self, tmp_path):
        (tmp_path / "data.dbf").write_bytes(b"")
        (tmp_path / "data.shx").write_bytes(b"")
        (tmp_path / "notes.txt").write_bytes(b"")
        (tmp_path / "data.shp").write_bytes(b"")

        result = scan_spatial_files(tmp_path, self.SPATIAL_EXTENSIONS)

        assert [f.name for f in result] == ["data.shp"]

    def test_recurses_into_subdirectories(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.geojson").write_bytes(b"")

        result = scan_spatial_files(tmp_path, self.SPATIAL_EXTENSIONS)

        assert len(result) == 1
        assert result[0].name == "nested.geojson"

    def test_extension_check_is_case_insensitive(self, tmp_path):
        (tmp_path / "DATA.GEOJSON").write_bytes(b"")

        result = scan_spatial_files(tmp_path, self.SPATIAL_EXTENSIONS)

        assert len(result) == 1

    def test_empty_directory_returns_empty_list(self, tmp_path):
        assert scan_spatial_files(tmp_path, self.SPATIAL_EXTENSIONS) == []
