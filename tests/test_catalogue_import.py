"""Advanced: CSV import validates, de-duplicates, checks reachability and
enriches with a row-by-row error report."""
import io


CSV_HEADER = "name,url,platform_key,connector_key,audience_tags,category,description\n"


def test_import_rejects_bad_urls_and_dupes(client):
    csv_text = CSV_HEADER + (
        "Good Forum,https://example.com/good,discourse,discourse,ai;founders,tech,AI and founder discussions\n"
        "Bad URL Row,not-a-url,discourse,discourse,,,\n"
        "Duplicate of Good,https://example.com/good,discourse,discourse,,,\n"
        "Missing Fields,,,,,,\n"
    )
    resp = client.post(
        "/api/v1/catalogue/import",
        files={"file": ("destinations.csv", io.BytesIO(csv_text.encode()), "text/csv")},
        params={"check_reachability": "false"},
    )
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    import time
    for _ in range(20):
        status = client.get(f"/api/v1/jobs/{job_id}").json()
        if status["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.3)

    assert status["status"] == "succeeded", status
    result = status["result"]
    assert result["imported"] == 1
    assert any("duplicate" in e["error"] for e in result["errors"])
    assert any("bad URL" in e["error"] for e in result["errors"])
    assert any("missing required field" in e["error"] for e in result["errors"])


def test_imported_destination_gets_relevance_score(client):
    csv_text = CSV_HEADER + "AI Forum,https://ai-forum.example.com,discourse,discourse,ai;founders,tech,A forum for AI founders and builders\n"
    resp = client.post(
        "/api/v1/catalogue/import",
        files={"file": ("destinations.csv", io.BytesIO(csv_text.encode()), "text/csv")},
        params={"check_reachability": "false"},
    )
    job_id = resp.json()["job_id"]
    import time
    for _ in range(20):
        status = client.get(f"/api/v1/jobs/{job_id}").json()
        if status["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.3)
    assert status["status"] == "succeeded"

    listing = client.get("/api/v1/destinations").json()
    match = [d for d in listing if d["name"] == "AI Forum"]
    assert match
    assert match[0]["relevance_score"] >= 3
