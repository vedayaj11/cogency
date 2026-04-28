from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class SyncStatus(BaseModel):
    connected: bool
    cdc_lag_seconds: int | None
    backfill_progress: float | None
    api_usage_percent: float | None


@router.get("/sync_status", response_model=SyncStatus)
async def sync_status() -> SyncStatus:
    # TODO(salesforce-sync): wire to packages/salesforce once sync workers are live
    return SyncStatus(
        connected=False, cdc_lag_seconds=None, backfill_progress=None, api_usage_percent=None
    )
