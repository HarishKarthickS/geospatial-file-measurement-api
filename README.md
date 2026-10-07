# Geospatial File Measurement API

A FastAPI backend that accepts KML files and ZIP archives containing a Shapefile, extracts feature metadata, and calculates metric area and length measurements.

## Features

- Upload `.kml` or `.zip` (Shapefile `.shp`, `.shx`, and `.dbf` required).
- Extract feature ID, geometry type and coordinates, properties, and dataset CRS.
- Calculate polygon area in square metres and line length in metres after projecting coordinates.
- Return a per-feature status for points, unsupported geometry, missing CRS, and calculation failures.
- Persist processed records in SQLite so file information remains available between requests.
- Interactive OpenAPI documentation at `/docs`.

## Setup

Requires Python 3.10 or newer. GeoPandas and Pyogrio use GDAL-backed vector drivers to read geospatial files.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

The server listens at `http://127.0.0.1:8000`; interactive API documentation is available at `http://127.0.0.1:8000/docs`.

SQLite data is stored in `data/geospatial.sqlite3` by default. Set `DATABASE_PATH` to use a different location. Uploads are limited to 100 MiB; the uncompressed contents of a Shapefile ZIP are limited to 500 MiB.

Run the automated checks with:

```powershell
pytest
```

## API

### `POST /api/files/`

Uploads and processes a `.kml` file or a `.zip` containing exactly one Shapefile. Submit the multipart form field as `file`.

```bash
curl -X POST http://127.0.0.1:8000/api/files/ \
  -F "file=@survey.kml"
```

Example response (`201 Created`):

```json
{
  "id": "9fc4945f-599e-4296-a814-3179daf7a204",
  "filename": "survey.kml",
  "feature_count": 120,
  "crs": "EPSG:4326",
  "status": "COMPLETED"
}
```

### `GET /api/files/{id}/`

Returns the uploaded file's metadata. Unknown IDs return `404 Not Found`.

```json
{
  "id": "9fc4945f-599e-4296-a814-3179daf7a204",
  "filename": "survey.kml",
  "feature_count": 120,
  "crs": "EPSG:4326",
  "status": "COMPLETED"
}
```

### `GET /api/files/{id}/measurements/`

Returns one entry per feature, including its geometry, properties, geometry type, measurement fields, and measurement status.

```json
{
  "file_id": "9fc4945f-599e-4296-a814-3179daf7a204",
  "crs": "EPSG:4326",
  "features": [
    {
      "feature_id": "0",
      "geometry_type": "Polygon",
      "geometry": {"type": "Polygon", "coordinates": []},
      "properties": {"name": "parcel A"},
      "area_m2": 123456.78,
      "length_m": null,
      "measurement_status": "COMPLETED",
      "message": null
    },
    {
      "feature_id": "1",
      "geometry_type": "Point",
      "geometry": {"type": "Point", "coordinates": [0, 0]},
      "properties": {},
      "area_m2": null,
      "length_m": null,
      "measurement_status": "NOT_REQUIRED",
      "message": "Point geometries do not require measurement."
    }
  ]
}
```

Polygons and multipolygons receive `area_m2`; lines, multilines, and linear rings receive `length_m`. Point geometries have `NOT_REQUIRED` status. Unsupported geometries have `UNSUPPORTED` status. Missing or invalid CRS produces `SKIPPED` for geometries that require measurement.

## Architecture

- `app/main.py` defines the FastAPI routes and delegates file parsing, measurement, and persistence.
- `app/geospatial.py` validates upload format and Shapefile ZIP contents, reads features with GeoPandas/Pyogrio, and converts values to JSON-compatible records.
- `app/measurements.py` transforms each feature to an appropriate projected CRS and calculates measurements.
- `app/storage.py` stores file metadata and extracted features in SQLite.

The upload request is read with a 100 MiB limit. ZIP entries are checked for unsafe paths and links and required Shapefile parts before extraction into a temporary directory. GeoPandas reads the data; feature records and CRS are persisted before a file ID is returned. Temporary source files are discarded after processing.

Area uses a feature-centered Lambert azimuthal equal-area projection. Length uses the feature's local UTM zone, with a global equal-area projection fallback for polar coordinates. Both calculations therefore use projected metres rather than latitude/longitude degrees. Feature-centered projections work well for local and regional survey features; datasets spanning very large distances or crossing projection boundaries may need a domain-specific projection strategy.

## Design Decisions

- **FastAPI** provides typed request handling, generated OpenAPI docs, and a compact service structure.
- **GeoPandas with Pyogrio** offers a consistent feature model for KML and Shapefile readers. A KML driver must be available in the installed GDAL build.
- **SQLite** keeps the example self-contained and survives process restarts. A production deployment with concurrent workers could use PostgreSQL/PostGIS and object storage.
- **Synchronous processing** keeps upload behavior easy to reason about for typical survey files. Large jobs could be moved to a background queue with explicit `PENDING` and `FAILED` states.
- **Geometry is returned with measurements** to keep results tied to the original feature and expose the requested feature content.
- **Projection is selected per feature** to handle localized data in multiple UTM zones. A known project CRS could instead be configured for a given survey area.

## Learning

This project practices secure multipart upload handling, vector data processing with GDAL-backed tools, JSON serialization of geometry and attributes, durable API persistence, and projection-aware measurement calculations. The main learning was that geometry measurements only make sense when the CRS and the geometry's geographic extent are considered together.

## Future Scope

- Add authentication, quotas, and configurable upload limits.
- Add background processing and progress/status endpoints for large files.
- Add PostGIS storage, pagination, and filtering by geometry or attribute.
- Support GeoJSON and GeoPackage, plus multi-layer KML and ZIP archives.
- Add configurable measurement units and project-specific CRS selection.
- Add deployment manifests, observability, and richer validation reports.
