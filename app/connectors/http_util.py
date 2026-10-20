"""Shared HTTP helper: maps platform HTTP responses to shared error codes
(Appendix A error_map) and backs off on 429 using the platform's reset time."""
import time
import httpx

from app.core.errors import IncuBrixError

MAX_UNAVAILABLE_RETRIES = 5


def call_platform(method: str, url: str, manifest: dict, *, headers: dict | None = None,
                   json: dict | None = None, content: bytes | None = None,
                   timeout: float = 10.0) -> httpx.Response:
    """`content` sends pre-serialized bytes verbatim (required when the
    caller has already signed those exact bytes, e.g. HMAC-signed webhooks --
    httpx's own JSON encoder is not guaranteed to produce byte-identical
    output to a caller's json.dumps(), which would break the signature)."""
    error_map = manifest.get("error_map", {})
    headers = headers or {}
    attempts = 0
    while True:
        attempts += 1
        try:
            with httpx.Client(timeout=timeout) as client:
                if content is not None:
                    resp = client.request(method, url, headers=headers, content=content)
                else:
                    resp = client.request(method, url, headers=headers, json=json)
        except httpx.RequestError as e:
            if attempts <= MAX_UNAVAILABLE_RETRIES:
                time.sleep(min(0.2 * attempts, 2.0))
                continue
            raise IncuBrixError("PLATFORM_UNAVAILABLE", f"{url} unreachable after {attempts} attempts: {e}")

        if resp.status_code < 400:
            return resp

        code = error_map.get(str(resp.status_code), "INTERNAL_ERROR")

        if resp.status_code == 429:
            reset_after = resp.headers.get("Retry-After") or resp.headers.get("X-RateLimit-Reset-After")
            raise IncuBrixError(
                "PLATFORM_RATE_LIMIT",
                f"platform rate limited (429); back off using reset time",
                details={"reset_after_seconds": float(reset_after) if reset_after else None, "body": _safe_body(resp)},
            )
        if resp.status_code == 401:
            raise IncuBrixError("CONNECTION_AUTH_EXPIRED", "token expired or revoked", details={"body": _safe_body(resp)})
        if resp.status_code == 422:
            raise IncuBrixError("PLATFORM_CONTENT_REJECTED", "platform refused the content", details={"body": _safe_body(resp)})
        if resp.status_code in (502, 503, 504):
            if attempts <= MAX_UNAVAILABLE_RETRIES:
                time.sleep(min(0.2 * attempts, 2.0))
                continue
            raise IncuBrixError("PLATFORM_UNAVAILABLE", "platform unavailable after retries", details={"body": _safe_body(resp)})

        raise IncuBrixError(code, f"platform returned {resp.status_code}", details={"body": _safe_body(resp)})


def _safe_body(resp: httpx.Response):
    try:
        return resp.json()
    except Exception:
        return resp.text[:500]
