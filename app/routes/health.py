from fastapi import APIRouter
from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/ready")
def ready():
    from app.core.db import SessionLocal
    try:
        db = SessionLocal()
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ready" if db_ok else "not_ready", "simulation_mode": settings.SIMULATION_MODE, "db_ok": db_ok}
