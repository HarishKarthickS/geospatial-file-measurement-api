"""Input validation and conversion of vector files into API feature records."""

from __future__ import annotations

import json
import math
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import geopandas as gpd
import pandas as pd
from fastapi import HTTPException
from shapely.geometry import mapping

MAX_UPLOAD_BYTES = 100 * 1024 * 1024
ALLOWED_EXTENSIONS = {".zip", ".kml"}


def _validate_archive(archive_path: Path, destination: Path) -> Path:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            if not members:
                raise HTTPException(422, "The ZIP archive is empty.")
            total_uncompressed = sum(member.file_size for member in members)
            if total_uncompressed > MAX_UPLOAD_BYTES * 5:
                raise HTTPException(413, "The uncompressed Shapefile archive is too large.")

            shapefiles: list[PurePosixPath] = []
            for member in members:
                normalized = PurePosixPath(member.filename.replace("\\", "/"))
                if normalized.is_absolute() or ".." in normalized.parts:
                    raise HTTPException(422, "The ZIP archive contains an unsafe file path.")
                if member.is_dir():
                    continue
                suffix = normalized.suffix.lower()
                if suffix in {".shp", ".shx", ".dbf", ".prj", ".cpg"}:
                    shapefiles.append(normalized)

            shp_files = [path for path in shapefiles if path.suffix.lower() == ".shp"]
            if len(shp_files) != 1:
                raise HTTPException(422, "The ZIP must contain exactly one .shp file.")
            shp = shp_files[0]
            stem = shp.with_suffix("")
            siblings = {path.as_posix().lower() for path in shapefiles}
            for required_suffix in (".shx", ".dbf"):
                if (stem.as_posix() + required_suffix).lower() not in siblings:
                    raise HTTPException(422, f"The Shapefile is missing its {required_suffix} file.")

            archive.extractall(destination)
            extracted_shp = destination.joinpath(*shp.parts)
            return extracted_shp
    except zipfile.BadZipFile as exc:
        raise HTTPException(422, "The uploaded .zip file is invalid.") from exc


def _json_value(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if pd.isna(value):
        return None
    try:
        return json.loads(json.dumps(value, default=str, allow_nan=False))
    except (TypeError, ValueError):
        return str(value)


def read_features(filename: str, content: bytes) -> tuple[list[dict[str, Any]], str | None]:
    """Read a KML or zipped Shapefile and return serializable feature records."""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, "Only .zip Shapefiles and .kml files are supported.")

    with tempfile.TemporaryDirectory(prefix="geo-upload-") as temp_dir:
        root = Path(temp_dir)
        if suffix == ".zip":
            source = root / "upload.zip"
            source.write_bytes(content)
            data_path = _validate_archive(source, root / "extracted")
            driver = "ESRI Shapefile"
        else:
            data_path = root / "upload.kml"
            data_path.write_bytes(content)
            driver = "KML"

        try:
            frame = gpd.read_file(data_path, driver=driver, engine="pyogrio")
        except Exception as exc:
            raise HTTPException(422, f"Unable to read geospatial file: {exc}") from exc

    crs = frame.crs.to_string() if frame.crs is not None else None
    records: list[dict[str, Any]] = []
    for index, row in frame.iterrows():
        geometry = row.geometry
        attributes = {
            str(key): _json_value(value)
            for key, value in row.items()
            if key != frame.geometry.name
        }
        records.append(
            {
                "feature_id": str(index),
                "geometry_type": geometry.geom_type if geometry is not None else None,
                "geometry": mapping(geometry) if geometry is not None else None,
                "properties": attributes,
            }
        )
    return records, crs
