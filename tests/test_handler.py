"""Integration tests for GisquickProjectFromFileHandler using a real QGIS installation.

_load_layers() and the full handleRequest() flow are exercised against the
real QgsVectorLayer / QgsRasterLayer / QgsProject C++ objects provided by
the pytest-qgis `qgis_app` fixture (initialised once per session in
conftest.py).  Only the server context/request objects are mocked, since
those belong to QGIS Server and cannot be constructed in isolation.
"""
from __future__ import annotations

import json
import os
import struct
import zlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from qgis.core import QgsWkbTypes
from qgis.server import QgsServerRequest

from gisquick_project_from_file.gisquick_project_from_file_handler import GisquickProjectFromFileHandler


# ---------------------------------------------------------------------------
# GeoJSON fixture — LineString supplied by the user
# ---------------------------------------------------------------------------

LINESTRING_GEOJSON = json.dumps(
    {
        "type": "LineString",
        "coordinates": [
            [9.2550938, 46.8118687],
            [9.2551718, 46.8119188],
            [9.2552499, 46.8119689],
            [9.2553279, 46.8120189],
            [9.2554059, 46.812069],
            [9.2554839, 46.8121191],
            [9.255562, 46.8121691],
            [9.25564, 46.8122192],
            [9.255718, 46.8122693],
            [9.2557961, 46.8123193],
            [9.2558741, 46.8123694],
            [9.2559521, 46.8124195],
            [9.2560302, 46.8124695],
            [9.2561082, 46.8125196],
            [9.2561862, 46.8125697],
            [9.2562643, 46.8126197],
            [9.2563423, 46.8126698],
            [9.2564203, 46.8127199],
            [9.2564984, 46.8127699],
            [9.2565764, 46.81282],
            [9.2566544, 46.8128701],
            [9.2567325, 46.8129201],
            [9.2568105, 46.8129702],
            [9.2568885, 46.8130203],
            [9.2569666, 46.8130703],
            [9.2570446, 46.8131204],
            [9.2571226, 46.8131705],
            [9.2572007, 46.8132205],
            [9.2572787, 46.8132706],
            [9.2573567, 46.8133207],
            [9.2574348, 46.8133707],
            [9.2575128, 46.8134208],
            [9.2575908, 46.8134709],
            [9.2576689, 46.8135209],
            [9.2577469, 46.813571],
            [9.2578249, 46.8136211],
            [9.257903, 46.8136711],
            [9.257981, 46.8137212],
            [9.2580591, 46.8137713],
            [9.2581371, 46.8138213],
            [9.2582151, 46.8138714],
            [9.2582932, 46.8139215],
            [9.2583712, 46.8139715],
            [9.2584492, 46.8140216],
            [9.2585273, 46.8140717],
            [9.2586053, 46.8141217],
            [9.2586833, 46.8141718],
            [9.2587614, 46.8142219],
            [9.2588394, 46.8142719],
            [9.2589175, 46.814322],
            [9.2589955, 46.8143721],
            [9.2590735, 46.8144221],
        ],
    }
)

POINT_GEOJSON = json.dumps({"type": "Point", "coordinates": [9.255, 46.812]})

POLYGON_FEATURES_ARRAY_JSON = json.dumps(
    [
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [9.238672341598535, 46.819057030602934],
                        [9.238860038465532, 46.81927206680878],
                        [9.239626262713852, 46.81998146664754],
                        [9.240490111296259, 46.820635889216476],
                        [9.24144326546957, 46.82122902997797],
                        [9.242476545218144, 46.8217551745738],
                        [9.243579997686165, 46.8222092539378],
                        [9.244742993098457, 46.8225868931909],
                        [9.24595432724342, 46.822884453844615],
                        [9.247202329526782, 46.82309906890389],
                        [9.248474975549767, 46.82322867052869],
                        [9.249760003120368, 46.823272009986134],
                        [9.25068263894047, 46.823240893596235],
                        [9.250956902756107, 46.82332572788313],
                        [9.252080355219666, 46.823592170617204],
                        [9.253234355982633, 46.823787664007824],
                        [9.253490396261025, 46.82382266960208],
                        [9.254805930991006, 46.8239553276858],
                        [9.25613427877728, 46.82399582519745],
                        [9.257461769433135, 46.82394374538726],
                        [9.258774741609832, 46.823799624226005],
                        [9.26005968359537, 46.823564944880715],
                        [9.261303372561741, 46.82324212242854],
                        [9.262493010817504, 46.82283447896746],
                        [9.26263502481465, 46.822779471022486],
                        [9.263814318259458, 46.82226390707748],
                        [9.264906892425069, 46.82166505619999],
                        [9.26590031875916, 46.820989732286414],
                        [9.266783298082839, 46.820245619092454],
                        [9.267392730461875, 46.81960266359902],
                        [9.26749841881166, 46.81951497395252],
                        [9.268262038839028, 46.81881469272314],
                        [9.268922988528999, 46.818066821645616],
                        [9.269475025547825, 46.81727842894117],
                        [9.269912937620308, 46.81645696548973],
                        [9.269981133992603, 46.81627631397389],
                        [9.27053827520877, 46.8155188324533],
                        [9.271014514080582, 46.81466586359924],
                        [9.271120568683898, 46.814397014804086],
                        [9.271271194109625, 46.8141456683735],
                        [9.271637681210313, 46.81331372422366],
                        [9.271885546065663, 46.81246138702294],
                        [9.272012481927709, 46.811596608492074],
                        [9.27201731045455, 46.81072745604003],
                        [9.271899992487574, 46.80986203749333],
                        [9.271661628197714, 46.80900842546278],
                        [9.271603485125317, 46.808872691824284],
                        [9.271605006509866, 46.8088678601634],
                        [9.271661952970302, 46.80863785390214],
                        [9.271810521489998, 46.80780355902215],
                        [9.271845073219401, 46.80696338588733],
                        [9.271765312058758, 46.80612466388045],
                        [9.271571939082248, 46.80529470938803],
                        [9.271266646238532, 46.804480761983946],
                        [9.270852101415194, 46.80368992129481],
                        [9.270331925003473, 46.80292908509684],
                        [9.26975780974524, 46.80218214291705],
                        [9.269102437287726, 46.801422291177815],
                        [9.268341779569916, 46.80071020463829],
                        [9.267483163975152, 46.80005273907685],
                        [9.26653486009086, 46.79945622415994],
                        [9.2655060000431, 46.79892640256441],
                        [9.264406490570767, 46.798468374752304],
                        [9.263246917685452, 46.798086549927916],
                        [9.262038444832488, 46.79778460364593],
                        [9.260792705529767, 46.79756544247625],
                        [9.259521691512518, 46.79743117606348],
                        [9.258237637454307, 46.79738309684826],
                        [9.256952903366486, 46.79742166764402],
                        [9.255679855799945, 46.7975465171881],
                        [9.254430748984287, 46.79775644370979],
                        [9.25321760703999, 46.798049426480986],
                        [9.252052108389286, 46.79842264523941],
                        [9.250945473470857, 46.79887250729838],
                        [9.249908356832632, 46.79939468208458],
                        [9.248950744636097, 46.79998414277287],
                        [9.248081858554816, 46.80063521462051],
                        [9.247310066989964, 46.801341629537916],
                        [9.246642804456954, 46.80209658637354],
                        [9.246086499920255, 46.80289281633549],
                        [9.24569408938447, 46.80363292585175],
                        [9.24560891899769, 46.8036422202631],
                        [9.244224532578118, 46.80390241469064],
                        [9.242889869464578, 46.80426498625854],
                        [9.242753885644937, 46.80430797977582],
                        [9.241583863267719, 46.804728172649945],
                        [9.240481333915653, 46.805227060978076],
                        [9.239457486124078, 46.80579958291714],
                        [9.238522711058065, 46.80643992934564],
                        [9.237686497091728, 46.80714160273872],
                        [9.236957333497195, 46.80789748302897],
                        [9.236342624220818, 46.80869989978827],
                        [9.235848612624057, 46.80954071000152],
                        [9.235480317957116, 46.810411380646386],
                        [9.235417277054776, 46.810594373765916],
                        [9.235191563506708, 46.81141983007986],
                        [9.235078916250842, 46.812256138400684],
                        [9.235080321717437, 46.81309601443622],
                        [9.235195772975219, 46.813932142482564],
                        [9.235424269607117, 46.81475723914733],
                        [9.235763826243018, 46.815564116803436],
                        [9.236211489681523, 46.81634574621973],
                        [9.236450425028018, 46.81671177107797],
                        [9.237025028078744, 46.81748881052976],
                        [9.237706435597133, 46.81822404986083],
                        [9.238488260381358, 46.81891059274517],
                        [9.238672341598535, 46.819057030602934],
                    ]
                ],
            },
            "properties": {
                "buffer_distance_m": 1000.0,
                "original_geometry_type": "LineString",
                "utm_crs": "EPSG:32632",
            },
        }
    ]
)


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def _write_minimal_png(path: Path) -> None:
    """Write a valid 1×1 white RGB PNG — the smallest raster GDAL can open."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    idat = chunk(b"IDAT", zlib.compress(b"\x00\xFF\xFF\xFF"))  # filter=None, white pixel
    iend = chunk(b"IEND", b"")
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend)


# ---------------------------------------------------------------------------
# Mock context / request helpers
# ---------------------------------------------------------------------------

SECRET = "testsecret"


def _make_context(method="POST", auth_header=None, body=None, request_is_none=False):
    """Build a minimal mock QgsServerApiContext for handleRequest()."""
    context = MagicMock()

    if request_is_none:
        context.request.return_value = None
        return context

    request = MagicMock()
    request.method.return_value = (
        QgsServerRequest.PostMethod if method == "POST" else QgsServerRequest.GetMethod
    )

    def _header(name):
        if name.lower() == "authorization" and auth_header is not None:
            return auth_header
        return None

    request.header = _header
    del request.headers  # disable the dict-based fallback path in _get_header

    request.data.return_value = (
        body if isinstance(body, (bytes, type(None))) else body.encode()
    )

    context.request.return_value = request
    return context


def _make_handler(secret=SECRET):
    with patch.dict(os.environ, {"GISQUICK_PROJECT_FROM_FILE_SHARED_SECRET": secret}):
        return GisquickProjectFromFileHandler()


def _status(ctx) -> int:
    return ctx.response().setStatusCode.call_args[0][0]


def _body(ctx) -> dict:
    return json.loads(ctx.response().write.call_args[0][0])


# ---------------------------------------------------------------------------
# _load_layers — real QGIS layer loading
# ---------------------------------------------------------------------------

class TestLoadLayers:

    # --- GeoJSON (user-supplied LineString fixture) ---

    def test_geojson_linestring_is_valid_vector_layer(self, tmp_path):
        (tmp_path / "track.geojson").write_text(LINESTRING_GEOJSON, encoding="utf-8")

        layers = GisquickProjectFromFileHandler._load_layers(tmp_path, [{"path": "track.geojson"}])

        assert len(layers) == 1
        assert layers[0].isValid()
        assert layers[0].geometryType() == QgsWkbTypes.LineGeometry

    def test_geojson_linestring_has_correct_feature_count(self, tmp_path):
        (tmp_path / "track.geojson").write_text(LINESTRING_GEOJSON, encoding="utf-8")

        layers = GisquickProjectFromFileHandler._load_layers(tmp_path, [{"path": "track.geojson"}])

        assert layers[0].featureCount() == 1

    # --- other vector extensions ---

    def test_json_extension_loads_vector_layer(self, tmp_path):
        (tmp_path / "pt.json").write_text(POINT_GEOJSON, encoding="utf-8")

        layers = GisquickProjectFromFileHandler._load_layers(tmp_path, [{"path": "pt.json"}])

        assert len(layers) == 1
        assert layers[0].isValid()
        assert layers[0].geometryType() == QgsWkbTypes.PointGeometry

    # --- features array (list of GeoJSON Feature objects, not a FeatureCollection) ---

    def test_json_features_array_loads_as_valid_vector_layer(self, tmp_path):
        (tmp_path / "features.json").write_text(POLYGON_FEATURES_ARRAY_JSON, encoding="utf-8")

        layers = GisquickProjectFromFileHandler._load_layers(tmp_path, [{"path": "features.json"}])

        assert len(layers) == 1
        assert layers[0].isValid()

    def test_json_features_array_has_polygon_geometry(self, tmp_path):
        (tmp_path / "features.json").write_text(POLYGON_FEATURES_ARRAY_JSON, encoding="utf-8")

        layers = GisquickProjectFromFileHandler._load_layers(tmp_path, [{"path": "features.json"}])

        assert layers[0].geometryType() == QgsWkbTypes.PolygonGeometry

    def test_json_features_array_has_correct_feature_count(self, tmp_path):
        (tmp_path / "features.json").write_text(POLYGON_FEATURES_ARRAY_JSON, encoding="utf-8")

        layers = GisquickProjectFromFileHandler._load_layers(tmp_path, [{"path": "features.json"}])

        assert layers[0].featureCount() == 1

    # --- raster ---

    def test_png_extension_loads_raster_layer(self, tmp_path):
        _write_minimal_png(tmp_path / "image.png")

        layers = GisquickProjectFromFileHandler._load_layers(tmp_path, [{"path": "image.png"}])

        assert len(layers) == 1
        assert layers[0].isValid()

    # --- invalid content for extension ---

    def test_corrupt_geojson_not_added(self, tmp_path):
        """A .geojson file with garbage content must not be added (isValid → False)."""
        (tmp_path / "bad.geojson").write_bytes(b"\x00\x01\x02CORRUPT")

        layers = GisquickProjectFromFileHandler._load_layers(tmp_path, [{"path": "bad.geojson"}])

        assert layers == []

    # --- path traversal / separator rejection (no QGIS I/O needed) ---

    def test_path_with_forward_slash_rejected(self, tmp_path):
        layers = GisquickProjectFromFileHandler._load_layers(
            tmp_path, [{"path": "subdir/data.geojson"}]
        )
        assert layers == []

    def test_path_with_backslash_rejected(self, tmp_path):
        layers = GisquickProjectFromFileHandler._load_layers(
            tmp_path, [{"path": "sub\\data.geojson"}]
        )
        assert layers == []

    def test_path_with_dotdot_rejected(self, tmp_path):
        layers = GisquickProjectFromFileHandler._load_layers(
            tmp_path, [{"path": "..secret.geojson"}]
        )
        assert layers == []

    # --- missing / malformed entries ---

    def test_nonexistent_file_skipped(self, tmp_path):
        layers = GisquickProjectFromFileHandler._load_layers(
            tmp_path, [{"path": "ghost.geojson"}]
        )
        assert layers == []

    def test_non_dict_entry_skipped(self, tmp_path):
        layers = GisquickProjectFromFileHandler._load_layers(tmp_path, ["not_a_dict"])
        assert layers == []

    def test_empty_files_list_returns_empty(self, tmp_path):
        layers = GisquickProjectFromFileHandler._load_layers(tmp_path, [])
        assert layers == []

    # --- unknown extension: OGR auto-detection ---

    def test_unknown_ext_with_geojson_content_loaded_as_vector(self, tmp_path):
        """OGR sniffs file content, so a .xyz file containing valid GeoJSON loads."""
        (tmp_path / "data.xyz").write_text(LINESTRING_GEOJSON, encoding="utf-8")

        layers = GisquickProjectFromFileHandler._load_layers(tmp_path, [{"path": "data.xyz"}])

        assert len(layers) == 1
        assert layers[0].isValid()

    def test_unknown_ext_with_png_content_falls_back_to_raster(self, tmp_path):
        """A PNG renamed to .xyz: OGR rejects it → GDAL opens it as raster."""
        _write_minimal_png(tmp_path / "data.xyz")

        layers = GisquickProjectFromFileHandler._load_layers(tmp_path, [{"path": "data.xyz"}])

        assert len(layers) == 1
        assert layers[0].isValid()

    def test_unknown_ext_with_garbage_content_skipped(self, tmp_path):
        (tmp_path / "data.xyz").write_bytes(b"\x00\x01GARBAGE")

        layers = GisquickProjectFromFileHandler._load_layers(tmp_path, [{"path": "data.xyz"}])

        assert layers == []

    # --- mime type override for unknown extension ---

    def test_geo_json_mime_opens_geojson_with_unknown_extension(self, tmp_path):
        """MIME type routes to QgsVectorLayer even when extension is unknown."""
        (tmp_path / "data.bin").write_text(LINESTRING_GEOJSON, encoding="utf-8")

        layers = GisquickProjectFromFileHandler._load_layers(
            tmp_path, [{"path": "data.bin", "type": "application/geo+json"}]
        )

        assert len(layers) == 1
        assert layers[0].isValid()

    # --- multiple files ---

    def test_multiple_files_all_loaded(self, tmp_path):
        (tmp_path / "track.geojson").write_text(LINESTRING_GEOJSON, encoding="utf-8")
        _write_minimal_png(tmp_path / "image.png")

        layers = GisquickProjectFromFileHandler._load_layers(
            tmp_path,
            [{"path": "track.geojson"}, {"path": "image.png"}],
        )

        assert len(layers) == 2
        assert all(layer.isValid() for layer in layers)


# ---------------------------------------------------------------------------
# handleRequest — server context mocked, QGIS layer/project objects are real
# ---------------------------------------------------------------------------

class TestHandleRequest:

    # --- 500: missing request context ---

    def test_500_when_request_is_none(self):
        handler = _make_handler()
        ctx = _make_context(request_is_none=True)
        handler.handleRequest(ctx)
        assert _status(ctx) == 500

    # --- 405: wrong HTTP method ---

    def test_405_for_get_method(self):
        handler = _make_handler()
        ctx = _make_context(method="GET")
        handler.handleRequest(ctx)
        assert _status(ctx) == 405

    # --- 401: authentication failures ---

    def test_401_when_no_auth_header(self):
        handler = _make_handler()
        ctx = _make_context(auth_header=None)
        handler.handleRequest(ctx)
        assert _status(ctx) == 401

    def test_401_when_wrong_token(self):
        handler = _make_handler()
        ctx = _make_context(auth_header="Token wrongtoken")
        handler.handleRequest(ctx)
        assert _status(ctx) == 401

    def test_401_when_secret_not_configured(self):
        handler = _make_handler(secret="")
        ctx = _make_context(auth_header=f"Token {SECRET}")
        handler.handleRequest(ctx)
        assert _status(ctx) == 401

    # --- 400: malformed payload ---

    def test_400_when_body_is_missing(self):
        handler = _make_handler()
        ctx = _make_context(auth_header=f"Token {SECRET}", body=None)
        handler.handleRequest(ctx)
        assert _status(ctx) == 400

    def test_400_when_body_is_invalid_json(self):
        handler = _make_handler()
        ctx = _make_context(auth_header=f"Token {SECRET}", body=b"not json")
        handler.handleRequest(ctx)
        assert _status(ctx) == 400

    def test_400_when_job_dir_missing(self):
        handler = _make_handler()
        body = json.dumps({"files": [{"path": "x.geojson"}]}).encode()
        ctx = _make_context(auth_header=f"Token {SECRET}", body=body)
        handler.handleRequest(ctx)
        assert _status(ctx) == 400

    def test_400_when_job_dir_empty_string(self):
        handler = _make_handler()
        body = json.dumps({"job_dir": "   ", "files": [{"path": "x.geojson"}]}).encode()
        ctx = _make_context(auth_header=f"Token {SECRET}", body=body)
        handler.handleRequest(ctx)
        assert _status(ctx) == 400

    def test_400_when_files_key_missing(self):
        handler = _make_handler()
        body = json.dumps({"job_dir": "/tmp"}).encode()
        ctx = _make_context(auth_header=f"Token {SECRET}", body=body)
        handler.handleRequest(ctx)
        assert _status(ctx) == 400

    def test_400_when_files_is_empty_list(self, tmp_path):
        handler = _make_handler()
        body = json.dumps({"job_dir": str(tmp_path), "files": []}).encode()
        ctx = _make_context(auth_header=f"Token {SECRET}", body=body)
        handler.handleRequest(ctx)
        assert _status(ctx) == 400

    # --- 422: no files could be loaded ---

    def test_422_when_no_layers_load(self, tmp_path):
        """Referencing a non-existent file results in an empty layer list."""
        handler = _make_handler()
        body = json.dumps(
            {"job_dir": str(tmp_path), "files": [{"path": "ghost.geojson"}]}
        ).encode()
        ctx = _make_context(auth_header=f"Token {SECRET}", body=body)
        handler.handleRequest(ctx)
        assert _status(ctx) == 422

    # --- 500: project write failure ---

    def test_500_when_project_write_fails(self, tmp_path):
        """Simulate QgsProject.write() returning False (e.g. permission denied)."""
        (tmp_path / "track.geojson").write_text(LINESTRING_GEOJSON, encoding="utf-8")
        handler = _make_handler()
        body = json.dumps(
            {"job_dir": str(tmp_path), "files": [{"path": "track.geojson"}]}
        ).encode()
        ctx = _make_context(auth_header=f"Token {SECRET}", body=body)

        with patch("qgis.core.QgsProject.write", return_value=False):
            handler.handleRequest(ctx)

        assert _status(ctx) == 500

    # --- 200: full happy-path integration ---

    def test_200_returns_project_file_name(self, tmp_path):
        (tmp_path / "track.geojson").write_text(LINESTRING_GEOJSON, encoding="utf-8")
        handler = _make_handler()
        body = json.dumps(
            {"job_dir": str(tmp_path), "files": [{"path": "track.geojson"}]}
        ).encode()
        ctx = _make_context(auth_header=f"Token {SECRET}", body=body)

        handler.handleRequest(ctx)

        assert _status(ctx) == 200
        assert _body(ctx)["project_file"] == "results.qgs"

    def test_200_project_file_exists_on_disk(self, tmp_path):
        (tmp_path / "track.geojson").write_text(LINESTRING_GEOJSON, encoding="utf-8")
        handler = _make_handler()
        body = json.dumps(
            {"job_dir": str(tmp_path), "files": [{"path": "track.geojson"}]}
        ).encode()
        ctx = _make_context(auth_header=f"Token {SECRET}", body=body)

        handler.handleRequest(ctx)

        assert (tmp_path / "results.qgs").exists()

    def test_200_project_contains_loaded_layer(self, tmp_path):
        """The saved project XML must reference the loaded GeoJSON layer."""
        (tmp_path / "track.geojson").write_text(LINESTRING_GEOJSON, encoding="utf-8")
        handler = _make_handler()
        body = json.dumps(
            {"job_dir": str(tmp_path), "files": [{"path": "track.geojson"}]}
        ).encode()
        ctx = _make_context(auth_header=f"Token {SECRET}", body=body)

        handler.handleRequest(ctx)

        project_xml = (tmp_path / "results.qgs").read_text(encoding="utf-8")
        assert "track" in project_xml

    def test_200_vector_layer_registered_for_wfs(self, tmp_path):
        (tmp_path / "track.geojson").write_text(LINESTRING_GEOJSON, encoding="utf-8")
        handler = _make_handler()
        body = json.dumps(
            {"job_dir": str(tmp_path), "files": [{"path": "track.geojson"}]}
        ).encode()
        ctx = _make_context(auth_header=f"Token {SECRET}", body=body)

        handler.handleRequest(ctx)

        project_xml = (tmp_path / "results.qgs").read_text(encoding="utf-8")
        assert "WFSLayers" in project_xml

    def test_200_raster_only_has_no_wfs_layers_entry(self, tmp_path):
        _write_minimal_png(tmp_path / "image.png")
        handler = _make_handler()
        body = json.dumps(
            {"job_dir": str(tmp_path), "files": [{"path": "image.png"}]}
        ).encode()
        ctx = _make_context(auth_header=f"Token {SECRET}", body=body)

        handler.handleRequest(ctx)

        project_xml = (tmp_path / "results.qgs").read_text(encoding="utf-8")
        assert "WFSLayers" not in project_xml

    def test_200_raster_and_vector_both_saved(self, tmp_path):
        (tmp_path / "track.geojson").write_text(LINESTRING_GEOJSON, encoding="utf-8")
        _write_minimal_png(tmp_path / "image.png")
        handler = _make_handler()
        body = json.dumps(
            {
                "job_dir": str(tmp_path),
                "files": [{"path": "track.geojson"}, {"path": "image.png"}],
            }
        ).encode()
        ctx = _make_context(auth_header=f"Token {SECRET}", body=body)

        handler.handleRequest(ctx)

        assert _status(ctx) == 200
        project_xml = (tmp_path / "results.qgs").read_text(encoding="utf-8")
        assert "track" in project_xml
        assert "image" in project_xml
