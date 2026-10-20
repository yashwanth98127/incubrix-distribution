import os
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.db import init_db
from app.core.errors import IncuBrixError
from app.routes import health, connector_routes, jobs_routes, destinations_routes, certification_routes, publish_routes
from app.routes import catalogue_routes, recommend_routes

configure_logging()
logger = get_logger(component="app")

app = FastAPI(
    title="IncuBrix Distribution: Long-Tail Destination Network",
    version="1.0.0",
    description="Connector service for forums, developer blogs, newsletters and partner sites.",
)


_scheduler = None


@app.on_event("startup")
def on_startup():
    global _scheduler
    init_db()
    if os.environ.get("INCUBRIX_DISABLE_SCHEDULER") != "1":
        from app.core.recertification import start_scheduler
        _scheduler = start_scheduler()
    logger.info("startup", simulation_mode=settings.SIMULATION_MODE, env=settings.ENV)


@app.on_event("shutdown")
def on_shutdown():
    if _scheduler:
        _scheduler.shutdown(wait=False)


@app.middleware("http")
async def correlation_and_timing(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-Id") or uuid.uuid4().hex
    start = time.time()
    request.state.correlation_id = correlation_id
    try:
        response = await call_next(request)
    except IncuBrixError as e:
        response = JSONResponse(status_code=e.http_status, content=e.to_envelope())
    duration_ms = round((time.time() - start) * 1000, 2)
    response.headers["X-Correlation-Id"] = correlation_id
    logger.info("request", method=request.method, path=request.url.path,
                status=response.status_code, duration_ms=duration_ms, correlation_id=correlation_id)
    return response


@app.exception_handler(IncuBrixError)
async def incubrix_error_handler(request: Request, exc: IncuBrixError):
    return JSONResponse(status_code=exc.http_status, content=exc.to_envelope())


app.include_router(health.router)
app.include_router(connector_routes.router)
app.include_router(jobs_routes.router)
app.include_router(destinations_routes.router)
app.include_router(certification_routes.router)
app.include_router(publish_routes.router)
app.include_router(catalogue_routes.router)
app.include_router(recommend_routes.router)


@app.get("/openapi.yaml", include_in_schema=False)
def openapi_yaml():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "openapi.yaml")
    return FileResponse(path, media_type="application/yaml")


@app.get("/")
def root():
    return {
        "service": "incubrix-distribution",
        "docs": "/docs",
        "openapi": "/openapi.yaml (static file in repo) or /openapi.json (live)",
        "simulation_mode": settings.SIMULATION_MODE,
    }
