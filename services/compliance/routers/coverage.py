"""Coverage-matrix endpoints: framework controls × evaluators × latest scores.

GET /api/coverage-matrix                    platform coverage (no scores)
GET /api/systems/{id}/coverage-matrix       per-system matrix overlaid with the
                                            latest score each evaluator produced
"""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from ...shared.database import db_manager
from ...shared.auth import get_current_active_user
from ...shared.models import AISystem
from ...shared.schemas import ApiResponse, UserResponse
from ..framework import coverage

logger = structlog.get_logger()

router = APIRouter()

_PLUGINS_DIR = Path("/app/plugins/evaluators")
if not _PLUGINS_DIR.is_dir():  # local dev / tests run from repo root
    _PLUGINS_DIR = Path(__file__).resolve().parents[4] / "plugins" / "evaluators"


def _primary_score(result: dict, primary_key: str | None = None) -> float | None:
    """primary_output_key value if present, else first numeric *_score key."""
    if not isinstance(result, dict):
        return None
    if primary_key and isinstance(result.get(primary_key), (int, float)):
        return float(result[primary_key])
    for key, value in result.items():
        if isinstance(value, (int, float)) and key.endswith("_score"):
            return float(value)
    return None


@router.get("/coverage-matrix", response_model=ApiResponse[dict])
async def platform_coverage_matrix(
    current_user: UserResponse = Depends(get_current_active_user),
):
    """Which framework controls have evaluator coverage (no scores)."""
    matrix = coverage.build_matrix(coverage.scan_evaluator_refs(_PLUGINS_DIR))
    return ApiResponse(success=True, data=matrix, message="Platform coverage matrix")


@router.get("/systems/{system_id}/coverage-matrix", response_model=ApiResponse[dict])
async def system_coverage_matrix(
    system_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen),
):
    """Coverage matrix overlaid with each evaluator's latest score for this system."""
    system = (await db.execute(
        select(AISystem).where(
            AISystem.system_id == system_id,
            AISystem.user_id == current_user.user_id,
        ))).scalar_one_or_none()
    if not system:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="System not found")

    rows = (await db.execute(text("""
        SELECT details, completed_at FROM compliance_test_executions
        WHERE system_id = :sid AND status = 'completed' AND details IS NOT NULL
        ORDER BY completed_at DESC
    """), {"sid": system_id})).fetchall()

    # latest score per evaluator, newest execution wins
    primary_keys = coverage.scan_primary_output_keys(_PLUGINS_DIR)
    latest: dict = {}
    for details_raw, _ in rows:
        details = details_raw if isinstance(details_raw, dict) else json.loads(details_raw or "{}")
        for name, wrapper in (details.get("evaluator_results") or {}).items():
            if name in latest:
                continue
            result = wrapper.get("result", wrapper) if isinstance(wrapper, dict) else {}
            if isinstance(result, dict) and "error" in result:
                latest[name] = None  # ran but failed
                continue
            latest[name] = _primary_score(result, primary_keys.get(name))

    matrix = coverage.build_matrix(coverage.scan_evaluator_refs(_PLUGINS_DIR), latest)
    matrix["system_id"] = system_id
    matrix["evaluations_seen"] = len(latest)
    return ApiResponse(success=True, data=matrix, message="System coverage matrix")
