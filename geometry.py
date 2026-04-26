from __future__ import annotations

import json
import logging
from pathlib import Path

_log = logging.getLogger(__name__)


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


def _orient_polygon_ccw(geom):
    """Return geom with exterior rings CCW and hole rings CW (RFC 7946).

    Works with Polygon and MultiPolygon geometries.  Ring orientation is
    determined by the shoelace signed-area formula; rings with the wrong
    winding order are reversed.  The closing point (first == last) is
    preserved correctly after reversal.
    """
    from qgis.core import QgsGeometry, QgsWkbTypes

    def _signed_area(ring):
        area = 0.0
        for i in range(len(ring) - 1):
            area += ring[i].x() * ring[i + 1].y() - ring[i + 1].x() * ring[i].y()
        return area / 2.0

    def _orient_rings(polygon):
        result = []
        for idx, ring in enumerate(polygon):
            want_ccw = idx == 0  # exterior CCW; holes CW
            if (_signed_area(ring) > 0) != want_ccw:
                ring = list(reversed(ring))
            result.append(ring)
        return result

    if QgsWkbTypes.isMultiType(geom.wkbType()):
        parts = geom.asMultiPolygon()
        if not parts:
            return geom
        return QgsGeometry.fromMultiPolygonXY([_orient_rings(p) for p in parts])
    else:
        polygon = geom.asPolygon()
        if not polygon:
            return geom
        return QgsGeometry.fromPolygonXY(_orient_rings(polygon))


def _fix_vector_layer_geometries(layer) -> None:
    """Validate and fix feature geometries in-place via an edit session.

    For polygon layers, normalises ring orientation to RFC 7946 / WFS
    GeoJSON convention (exterior CCW, holes CW) via _orient_polygon_ccw().
    Any geometry that remains GEOS-invalid after that step is repaired with
    makeValid().  Only opens an edit session when at least one geometry
    actually needs changing.
    """
    from qgis.core import QgsGeometry, QgsWkbTypes

    is_polygon_layer = layer.geometryType() == QgsWkbTypes.PolygonGeometry
    fixes = {}

    for feature in layer.getFeatures():
        geom = feature.geometry()
        if geom.isEmpty():
            continue

        new_geom = QgsGeometry(geom)

        if is_polygon_layer:
            new_geom = _orient_polygon_ccw(new_geom)

        if not new_geom.isGeosValid():
            valid = new_geom.makeValid()
            if not valid.isEmpty():
                new_geom = valid

        if new_geom.asWkb() != geom.asWkb():
            fixes[feature.id()] = new_geom

    if not fixes:
        return

    if layer.startEditing():
        for fid, new_geom in fixes.items():
            layer.changeGeometry(fid, new_geom)
        layer.commitChanges()
    else:
        _log.warning("Could not start editing layer '%s' to fix geometries", layer.name())
