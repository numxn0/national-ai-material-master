from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.analytics import AnalyticsSummaryResponse
from app.services.analytics import build_analytics_summary

router = APIRouter(prefix="/analytics", tags=["Production Analytics"])


@router.get("/summary", response_model=AnalyticsSummaryResponse)
async def get_analytics_summary(
    days: int = Query(30, ge=1, le=365, description="Rolling time range in days for timeline buckets"),
    db: Session = Depends(get_db),
):
    return AnalyticsSummaryResponse(**build_analytics_summary(db, days=days))
