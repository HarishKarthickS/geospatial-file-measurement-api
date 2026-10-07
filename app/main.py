"""FastAPI routes for geospatial file uploads and measurements."""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile

from app.geospatial import MAX_UPLOAD_BYTES, read_features
from app.measurements import measure_features
from app.storage import get_file, initialize, save_file

app = FastAPI(
    title="Geospatial File Measurement API",
    description="Upload KML or zipped Shapefile data and retrieve feature measurements.",
    version="1.0.0",
)


@app.on_event("startup")
def startup() -> None:
    initialize()


@app.post("/api/files/", status_code=201, tags=["files"])
async def upload_file(file: UploadFile = File(...)) -> dict:
    filename = file.filename or ""
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "The uploaded file exceeds the 100 MiB limit.")
    if not content:
        raise HTTPException(422, "The uploaded file is empty.")

    features, crs = read_features(filename, content)
    file_id = str(uuid4())
    save_file(file_id, filename, features, crs)
    return {
        "id": file_id,
        "filename": filename,
        "feature_count": len(features),
        "crs": crs,
        "status": "COMPLETED",
    }


@app.get("/api/files/{file_id}/", tags=["files"])
def file_information(file_id: str) -> dict:
    uploaded = get_file(file_id)
    if uploaded is None:
        raise HTTPException(404, "File not found.")
    return {key: uploaded[key] for key in ("id", "filename", "feature_count", "crs", "status")}


@app.get("/api/files/{file_id}/measurements/", tags=["measurements"])
def file_measurements(file_id: str) -> dict:
    uploaded = get_file(file_id)
    if uploaded is None:
        raise HTTPException(404, "File not found.")
    return {
        "file_id": file_id,
        "crs": uploaded["crs"],
        "features": measure_features(uploaded["features"], uploaded["crs"]),
    }
