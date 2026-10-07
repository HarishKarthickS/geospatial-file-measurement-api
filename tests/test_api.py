from fastapi.testclient import TestClient

from app import main, storage


def test_upload_file_information_and_measurements(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "DATABASE_PATH", tmp_path / "api.sqlite3")
    monkeypatch.setattr(
        main,
        "read_features",
        lambda filename, content: (
            [
                {
                    "feature_id": "0",
                    "geometry_type": "LineString",
                    "geometry": {"type": "LineString", "coordinates": [[0, 0], [0.01, 0]]},
                    "properties": {"name": "road"},
                }
            ],
            "EPSG:4326",
        ),
    )

    with TestClient(main.app) as client:
        upload = client.post(
            "/api/files/",
            files={"file": ("survey.kml", b"<kml />", "application/vnd.google-earth.kml+xml")},
        )
        assert upload.status_code == 201
        uploaded = upload.json()
        assert uploaded["filename"] == "survey.kml"
        assert uploaded["feature_count"] == 1
        assert uploaded["crs"] == "EPSG:4326"
        assert uploaded["status"] == "COMPLETED"

        file_id = uploaded["id"]
        details = client.get(f"/api/files/{file_id}/")
        assert details.status_code == 200
        assert details.json()["id"] == file_id

        measurements = client.get(f"/api/files/{file_id}/measurements/")
        assert measurements.status_code == 200
        feature = measurements.json()["features"][0]
        assert feature["measurement_status"] == "COMPLETED"
        assert feature["length_m"] > 1_000
        assert feature["properties"] == {"name": "road"}

        assert client.get("/api/files/missing/").status_code == 404


def test_upload_rejects_unsupported_file_extension():
    with TestClient(main.app) as client:
        response = client.post("/api/files/", files={"file": ("data.geojson", b"{}")})
    assert response.status_code == 415
