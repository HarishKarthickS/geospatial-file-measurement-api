"""CRS-aware measurement calculations for vector feature records."""

from __future__ import annotations

from typing import Any

from pyproj import CRS, Transformer
from shapely.geometry import shape
from shapely.ops import transform


def _measurement_crs(geometry: Any, source_crs: CRS, *, equal_area: bool) -> CRS:
    """Pick a local metric CRS centered on a feature's WGS84 centroid."""
    to_wgs84 = Transformer.from_crs(source_crs, CRS.from_epsg(4326), always_xy=True)
    geographic_geometry = transform(to_wgs84.transform, geometry)
    centroid = geographic_geometry.centroid
    longitude = ((centroid.x + 180.0) % 360.0) - 180.0
    latitude = max(-90.0, min(90.0, centroid.y))

    if equal_area:
        return CRS.from_proj4(
            f"+proj=laea +lat_0={latitude:.8f} +lon_0={longitude:.8f} "
            "+datum=WGS84 +units=m +no_defs"
        )
    if -80.0 <= latitude <= 84.0:
        zone = max(1, min(60, int((longitude + 180.0) // 6.0) + 1))
        epsg = (32600 if latitude >= 0 else 32700) + zone
        return CRS.from_epsg(epsg)
    return CRS.from_epsg(6933)


def _project_and_measure(
    geometry: Any,
    source_crs: CRS,
    *,
    equal_area: bool,
) -> float:
    target_crs = _measurement_crs(geometry, source_crs, equal_area=equal_area)
    transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    projected = transform(transformer.transform, geometry)
    return float(projected.area if equal_area else projected.length)


def measure_features(
    features: list[dict[str, Any]], crs_value: str | None
) -> list[dict[str, Any]]:
    """Return feature records augmented with metric measurements and status."""
    source_crs: CRS | None = None
    if crs_value:
        try:
            source_crs = CRS.from_user_input(crs_value)
        except Exception:
            source_crs = None

    results: list[dict[str, Any]] = []
    for feature in features:
        geometry_type = feature.get("geometry_type")
        geometry_data = feature.get("geometry")
        result: dict[str, Any] = {
            "feature_id": feature["feature_id"],
            "geometry_type": geometry_type,
            "geometry": geometry_data,
            "properties": feature.get("properties", {}),
            "area_m2": None,
            "length_m": None,
            "measurement_status": "COMPLETED",
            "message": None,
        }

        if geometry_data is None or not geometry_type:
            result["measurement_status"] = "SKIPPED"
            result["message"] = "Feature has no geometry."
        elif geometry_type in {"Point", "MultiPoint"}:
            result["measurement_status"] = "NOT_REQUIRED"
            result["message"] = "Point geometries do not require measurement."
        elif geometry_type not in {
            "Polygon",
            "MultiPolygon",
            "LineString",
            "MultiLineString",
            "LinearRing",
        }:
            result["measurement_status"] = "UNSUPPORTED"
            result["message"] = f"Measurement is not supported for {geometry_type}."
        elif source_crs is None:
            result["measurement_status"] = "SKIPPED"
            result["message"] = "A valid source CRS is required for measurement."
        else:
            try:
                geometry = shape(geometry_data)
                if geometry.is_empty:
                    result["measurement_status"] = "SKIPPED"
                    result["message"] = "Feature geometry is empty."
                elif geometry_type in {"Polygon", "MultiPolygon"}:
                    result["area_m2"] = _project_and_measure(
                        geometry, source_crs, equal_area=True
                    )
                else:
                    result["length_m"] = _project_and_measure(
                        geometry, source_crs, equal_area=False
                    )
            except Exception as exc:
                result["measurement_status"] = "ERROR"
                result["message"] = f"Unable to calculate measurement: {exc}"

        results.append(result)
    return results
