"""Exposes every connector method over HTTP exactly per Appendix A:
POST /connector/v1/{connector_key}/{method} with JSON bodies, so IncuBrix's
real Connector Runtime can call these connectors unchanged (Must-have #1).
"""
from fastapi import APIRouter, Request
from app.connectors.registry import get_connector
from app.core.errors import IncuBrixError
from app.core.schemas import (
    ValidateRequest, PublishRequest, StatusRequest, DeleteRequest,
    MetricsRequest, RefreshAuthRequest, AssistPackRequest,
)

router = APIRouter(prefix="/connector/v1", tags=["connector-contract"])

METHOD_MAP = {
    "validate": ("validate", ValidateRequest),
    "publish": ("publish", PublishRequest),
    "get_status": ("get_status", StatusRequest),
    "delete": ("delete", DeleteRequest),
    "fetch_metrics": ("fetch_metrics", MetricsRequest),
    "refresh_auth": ("refresh_auth", RefreshAuthRequest),
    "build_assist_pack": ("build_assist_pack", AssistPackRequest),
}


@router.post("/{connector_key}/{method}")
async def call_connector_method(connector_key: str, method: str, request: Request):
    if method not in METHOD_MAP:
        raise IncuBrixError("NOT_FOUND", f"unknown connector method '{method}'")

    connector = get_connector(connector_key)
    attr, schema = METHOD_MAP[method]
    body = await request.json()
    try:
        req = schema(**body)
    except Exception as e:
        raise IncuBrixError("VALIDATION_ERROR", f"invalid request body: {e}")

    try:
        fn = getattr(connector, attr)
        result = fn(req)
    except IncuBrixError as e:
        raise e
    except Exception as e:
        raise IncuBrixError("INTERNAL_ERROR", str(e))

    return result.model_dump()


@router.get("/{connector_key}/manifest")
def get_manifest(connector_key: str):
    connector = get_connector(connector_key)
    return connector.load_manifest()
