"""
API Routes
──────────
POST /api/v1/upload              – upload CSV, get session_id
POST /api/v1/rules/generate      – generate rules from scenario prompt
POST /api/v1/rules/evaluate      – evaluate rules against uploaded dataset
GET  /api/v1/sessions/{id}       – get session metadata
DELETE /api/v1/sessions/{id}     – delete session
GET  /api/v1/health              – LLM + service health check
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from app.core.llm_client import get_llm_client
from app.models.schemas import (
    EvaluateRequest,
    EvaluationMetrics,
    GenerateRulesRequest,
    GenerateRulesResponse,
    RuleMode,
    SchemaType,
    UploadResponse,
)
from app.services.dataset_service import (
    delete_session,
    ingest_csv,
    list_sessions,
    load_session,
)
from app.services.evaluator import evaluate_dataset
from app.services.rule_generator import generate_rules

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


# ─── Health ──────────────────────────────────────────────────────────────────

@router.get("/health", tags=["system"])
async def health_check():
    llm_status = await get_llm_client().health()
    return {
        "service": "fraud-rule-engine",
        "version": "1.0.0",
        "llm": llm_status,
    }


# ─── Upload ──────────────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["dataset"],
    summary="Upload a fraud dataset CSV",
)
async def upload_dataset(file: UploadFile = File(...)):
    """
    Upload a CSV file (EMVCo or EMVCo 3DS schema).
    Returns a `session_id` to use in subsequent evaluate calls.
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only CSV files are supported.",
        )
    raw = await file.read()
    try:
        result = await ingest_csv(raw, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return result


# ─── Rule Generation ─────────────────────────────────────────────────────────

@router.post(
    "/rules/generate",
    response_model=GenerateRulesResponse,
    tags=["rules"],
    summary="Generate fraud detection rules from a scenario prompt",
)
async def api_generate_rules(req: GenerateRulesRequest):
    """
    **Normal mode**: pass `scenario` (text or preset name) and optionally
    a `session_id` to let the engine tailor rules to your exact columns.

    **Assisted mode**: additionally pass `blueprint` (the blueprint JSON
    produced by the scenario pipeline) and set `mode="assisted"`.

    The endpoint calls the local Ollama model and returns structured rules
    ready to be passed to `/rules/evaluate`.
    """
    # If a session_id is embedded in the request extras, resolve columns
    session_id = getattr(req, "session_id", None)
    schema_type = req.schema_type

    if session_id:
        try:
            df, schema_type = load_session(session_id)
            if not req.available_columns:
                req.available_columns = list(df.columns)
            if not req.schema_type:
                req.schema_type = schema_type
        except FileNotFoundError:
            pass  # fall through with whatever columns were supplied

    try:
        result = await generate_rules(req, schema_type)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    return result


# ─── Evaluation ──────────────────────────────────────────────────────────────

@router.post(
    "/rules/evaluate/{session_id}",
    response_model=EvaluationMetrics,
    tags=["rules"],
    summary="Evaluate selected rules against an uploaded dataset",
)
async def api_evaluate_rules(session_id: str, req: EvaluateRequest):
    """
    Evaluate one or more fraud rules against a previously uploaded dataset.

    - `rules` – full list of FraudRule objects (from `/rules/generate`)
    - `selected_rule_ids` – subset to evaluate; omit to run all rules
    """
    try:
        df, schema = load_session(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    try:
        metrics = evaluate_dataset(df, req.rules, schema, req.selected_rule_ids)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return metrics


# ─── Session management ───────────────────────────────────────────────────────

@router.get(
    "/sessions/{session_id}",
    tags=["dataset"],
    summary="Get session metadata",
)
async def get_session(session_id: str):
    try:
        df, schema = load_session(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return {
        "session_id": session_id,
        "rows": len(df),
        "schema_type": schema,
        "columns": list(df.columns),
    }


@router.delete(
    "/sessions/{session_id}",
    tags=["dataset"],
    summary="Delete a session and its cached dataset",
)
async def delete_session_endpoint(session_id: str):
    removed = delete_session(session_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    return {"deleted": True, "session_id": session_id}


@router.get("/sessions", tags=["dataset"], summary="List active sessions")
async def list_sessions_endpoint():
    return {"sessions": list_sessions()}
