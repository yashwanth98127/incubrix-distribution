"""Shared error codes (Appendix A) and the Integration Standard JSON error envelope."""
from fastapi import HTTPException


# code -> (retryable, http_status)
ERROR_CODES = {
    "DEST_SPEC_VIOLATION": (False, 422),
    "DEST_RULE_FREQUENCY_CAP": (True, 429),
    "DEST_RULE_SELF_PROMO_BANNED": (False, 422),
    "DEST_RULE_LINK_POLICY": (False, 422),
    "DEST_RULE_DISCLOSURE_REQUIRED": (False, 422),
    "CONNECTION_AUTH_EXPIRED": (True, 401),
    "PLATFORM_RATE_LIMIT": (True, 429),
    "PLATFORM_QUOTA_EXHAUSTED": (True, 429),
    "PLATFORM_CONTENT_REJECTED": (False, 422),
    "PLATFORM_UNAVAILABLE": (True, 503),
    "CONNECTOR_DISABLED": (False, 403),
    "VALIDATION_ERROR": (False, 400),
    "NOT_FOUND": (False, 404),
    "IDEMPOTENCY_CONFLICT": (False, 409),
    "CERTIFICATION_FAILED": (False, 422),
    "INTERNAL_ERROR": (True, 500),
}


class IncuBrixError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        if code not in ERROR_CODES:
            code = "INTERNAL_ERROR"
        self.code = code
        self.message = message
        self.details = details or {}
        self.retryable, self.http_status = ERROR_CODES[code]
        super().__init__(message)

    def to_envelope(self) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "retryable": self.retryable,
                "details": self.details,
            }
        }

    def to_http_exception(self) -> HTTPException:
        return HTTPException(status_code=self.http_status, detail=self.to_envelope())
