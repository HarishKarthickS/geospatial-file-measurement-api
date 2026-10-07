from app.measurements import measure_features


def test_polygon_and_line_are_measured_in_metric_units():
    features = [
        {
            "feature_id": "parcel",
            "geometry_type": "Polygon",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [0.01, 0], [0.01, 0.01], [0, 0.01], [0, 0]]],
            },
            "properties": {},
        },
        {
            "feature_id": "road",
            "geometry_type": "LineString",
            "geometry": {
                "type": "LineString",
                "coordinates": [[0, 0], [0.01, 0]],
            },
            "properties": {},
        },
    ]

    results = measure_features(features, "EPSG:4326")

    assert results[0]["measurement_status"] == "COMPLETED"
    assert 1_000_000 < results[0]["area_m2"] < 1_300_000
    assert results[0]["length_m"] is None
    assert results[1]["measurement_status"] == "COMPLETED"
    assert 1_000 < results[1]["length_m"] < 1_200
    assert results[1]["area_m2"] is None


def test_point_unsupported_and_missing_crs_are_reported_without_failure():
    features = [
        {"feature_id": "point", "geometry_type": "Point", "geometry": {"type": "Point", "coordinates": [0, 0]}},
        {"feature_id": "collection", "geometry_type": "GeometryCollection", "geometry": {"type": "GeometryCollection", "geometries": []}},
        {"feature_id": "line", "geometry_type": "LineString", "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}},
    ]

    results = measure_features(features, None)

    assert results[0]["measurement_status"] == "NOT_REQUIRED"
    assert results[1]["measurement_status"] == "UNSUPPORTED"
    assert results[2]["measurement_status"] == "SKIPPED"
    assert "CRS" in results[2]["message"]
