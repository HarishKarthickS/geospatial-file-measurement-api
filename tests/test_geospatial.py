from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi import HTTPException

from app.geospatial import _validate_archive, read_features


def test_reads_kml_features_and_crs():
    content = b'''<?xml version="1.0"?>
    <kml xmlns="http://www.opengis.net/kml/2.2"><Document>
      <Placemark><name>parcel</name><Polygon><outerBoundaryIs><LinearRing>
        <coordinates>0,0 0.01,0 0.01,0.01 0,0.01 0,0</coordinates>
      </LinearRing></outerBoundaryIs></Polygon></Placemark>
    </Document></kml>'''

    features, crs = read_features("survey.kml", content)

    assert crs == "EPSG:4326"
    assert len(features) == 1
    assert features[0]["geometry_type"] == "Polygon"
    assert features[0]["properties"]["Name"] == "parcel"


def test_rejects_unsafe_zip_member_path(tmp_path):
    archive_path = tmp_path / "unsafe.zip"
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("../outside.shp", b"not a shapefile")

    with pytest.raises(HTTPException, match="unsafe file path"):
        _validate_archive(archive_path, tmp_path / "extracted")
