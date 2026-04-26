"""
CSV Upload & Session Service
──────────────────────────────
Handles file upload, parsing, schema detection and in-memory session caching.
Sessions are keyed by a UUID and stored as parquet in SESSION_DIR.
"""
from __future__ import annotations

import io
import logging
import os
import uuid
from pathlib import Path

import pandas as pd

from app.core.config import get_settings
from app.core.schema_detector import detect_schema
from app.models.schemas import DatasetSummary, SchemaType, UploadResponse
from app.services.evaluator import _dataset_summary

logger   = logging.getLogger(__name__)
settings = get_settings()


def _session_path(session_id: str) -> Path:
    return Path(settings.SESSION_DIR) / f"{session_id}.parquet"


def _ensure_session_dir() -> None:
    Path(settings.SESSION_DIR).mkdir(parents=True, exist_ok=True)


# ─── Upload ───────────────────────────────────────────────────────────────────

async def ingest_csv(file_bytes: bytes, filename: str) -> UploadResponse:
    """
    Parse CSV bytes, detect schema, persist to parquet, return metadata.
    Raises ValueError on parse failure or oversized files.
    """
    _ensure_session_dir()

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise ValueError(
            f"File too large ({len(file_bytes) // (1024*1024)} MB). "
            f"Maximum is {settings.MAX_UPLOAD_MB} MB."
        )

    try:
        df = pd.read_csv(
            io.BytesIO(file_bytes),
            low_memory=False,
            encoding="utf-8-sig",   # handles BOM (the ﻿ in money_laundering.csv)
        )
    except Exception as exc:
        raise ValueError(f"Failed to parse CSV: {exc}") from exc

    if df.empty:
        raise ValueError("Uploaded CSV is empty.")

    # Drop unnamed index columns introduced by some exporters
    df = df.loc[:, ~df.columns.str.match(r"^Unnamed")]

    schema_type = detect_schema(list(df.columns))
    session_id  = str(uuid.uuid4())

    # Persist as parquet for fast retrieval in evaluate endpoint
    df.to_parquet(_session_path(session_id), index=False)

    summary = _dataset_summary(df, schema_type)

    logger.info(
        "Ingested %s | session=%s | rows=%d | schema=%s",
        filename, session_id, len(df), schema_type,
    )

    return UploadResponse(
        session_id=session_id,
        filename=filename,
        rows=len(df),
        schema_type=schema_type,
        columns=list(df.columns),
        dataset_summary=summary,
    )


# ─── Session retrieval ────────────────────────────────────────────────────────

def load_session(session_id: str) -> tuple[pd.DataFrame, SchemaType]:
    """
    Load a previously uploaded dataset from the session cache.
    Returns (DataFrame, SchemaType).
    Raises FileNotFoundError if the session has expired or never existed.
    """
    path = _session_path(session_id)
    if not path.exists():
        raise FileNotFoundError(
            f"Session '{session_id}' not found. "
            "Please re-upload your dataset."
        )

    df          = pd.read_parquet(path)
    schema_type = detect_schema(list(df.columns))
    return df, schema_type


def delete_session(session_id: str) -> bool:
    path = _session_path(session_id)
    if path.exists():
        path.unlink()
        return True
    return False


def list_sessions() -> list[str]:
    _ensure_session_dir()
    return [
        p.stem
        for p in Path(settings.SESSION_DIR).glob("*.parquet")
    ]
