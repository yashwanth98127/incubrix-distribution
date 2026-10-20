"""Advanced: catalogue import pipeline. Validates a CSV of destinations,
de-duplicates (normalised URL + platform), checks reachability, enriches,
and produces a row-by-row error report. Designed for 1,000 rows in well
under 5 minutes (it's pure I/O-bound HEAD requests, run concurrently)."""
import csv
import io
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from sqlalchemy.orm import Session

from app.core.models import Destination
from app.core.ai_adapter import get_ai_adapter
from app.routes.destinations_routes import _normalize_url

URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)
REQUIRED_COLUMNS = {"name", "url", "platform_key", "connector_key"}


def _check_reachable(url: str) -> tuple[bool, int | None]:
    try:
        with httpx.Client(timeout=5.0, follow_redirects=True) as c:
            r = c.head(url)
            if r.status_code >= 400:
                r = c.get(url)
            return r.status_code < 400, r.status_code
    except Exception:
        return False, None


def import_csv(db: Session, csv_text: str, check_reachability: bool = True) -> dict:
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    if rows and not REQUIRED_COLUMNS.issubset(set(reader.fieldnames or [])):
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        return {"imported": 0, "errors": [{"row": 0, "error": f"missing required columns: {missing}"}]}

    errors = []
    seen_keys = set()
    candidates = []

    for i, row in enumerate(rows, start=2):  # header is row 1
        name = (row.get("name") or "").strip()
        url = (row.get("url") or "").strip()
        platform_key = (row.get("platform_key") or "").strip()
        connector_key = (row.get("connector_key") or "").strip()

        if not name or not url or not platform_key or not connector_key:
            errors.append({"row": i, "url": url, "error": "missing required field(s)"})
            continue
        if not URL_RE.match(url):
            errors.append({"row": i, "url": url, "error": "bad URL format"})
            continue

        normalized = _normalize_url(url)
        dedupe_key = (normalized, platform_key)
        if dedupe_key in seen_keys:
            errors.append({"row": i, "url": url, "error": "duplicate (normalised URL + platform)"})
            continue
        if db.query(Destination).filter(Destination.normalized_url == normalized).first():
            errors.append({"row": i, "url": url, "error": "already exists in catalogue"})
            continue
        seen_keys.add(dedupe_key)
        candidates.append((i, row, normalized))

    reachability: dict[str, tuple[bool, int | None]] = {}
    if check_reachability and candidates:
        with ThreadPoolExecutor(max_workers=32) as ex:
            futures = {ex.submit(_check_reachable, row["url"]): (i, row["url"]) for i, row, _ in candidates}
            for fut in as_completed(futures):
                i, url = futures[fut]
                reachability[url] = fut.result()

    ai = get_ai_adapter()
    imported = 0
    for i, row, normalized in candidates:
        url = row["url"]
        reachable, status_code = reachability.get(url, (True, None)) if check_reachability else (True, None)
        if check_reachability and not reachable:
            errors.append({"row": i, "url": url, "error": f"unreachable (status={status_code})"})
            continue

        audience_tags = [t.strip() for t in (row.get("audience_tags") or "").split(";") if t.strip()]
        description = row.get("description", "") or f"{row['name']} {row.get('category', '')}"
        score, reason = ai.score_relevance(description, audience_tags or ["ai", "video", "marketing", "saas", "creators", "founders"])

        dest = Destination(
            name=row["name"], url=url, normalized_url=normalized,
            platform_key=row["platform_key"], connector_key=row["connector_key"],
            surface=row.get("surface", "default"), category=row.get("category", ""),
            audience_tags=audience_tags, language=row.get("language", "en") or "en",
            geo=row.get("geo", ""), est_audience=int(row.get("est_audience") or 0),
            rules_url=row.get("rules_url", ""), relevance_score=score, relevance_reason=reason,
            level="L0", instance_params={"base_url": row.get("base_url", "")} if row.get("base_url") else {},
        )
        db.add(dest)
        imported += 1

    db.commit()
    return {
        "total_rows": len(rows), "imported": imported,
        "duplicates": sum(1 for e in errors if "duplicate" in e["error"] or "already exists" in e["error"]),
        "errors": errors,
    }
