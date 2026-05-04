"""CasaQuant Unified — Pipeline/recalc API routes."""

from fastapi import APIRouter

from app.dependencies import DBDep

router = APIRouter()


@router.post("/recalc")
async def trigger_recalc(db: DBDep):
    """Trigger the full 6-step recalc pipeline."""
    # TODO: queue via Celery
    return {"status": "queued", "message": "Recalc pipeline queued"}


@router.get("/status")
async def get_pipeline_status():
    """Get current pipeline status."""
    # TODO: query job_runs table
    return {"status": "idle", "last_run": None}
