"""Health check and deployment compliance matrix."""
from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/v1/compliance")
async def compliance() -> dict[str, Any]:
    """Which database types are usable on this deployment (drivers + type
    rules). Public: contains no user data, only server capabilities."""
    from ..utils.compliance import build_compliance_matrix
    return build_compliance_matrix()
