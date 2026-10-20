#!/usr/bin/env python3
"""Batch runner (Integration Standard point 10): runs a folder/file of test
inputs against the running API and writes all results to one output folder.

Input format: a folder of *.json files, each shaped like:
  {
    "kind": "publish" | "certify" | "catalogue_import" | "recommend",
    "destination": {...}        # for publish/certify: either inline destination fields
                                  # (created first) or "destination_id" of an existing one
    "rendition": {...}          # for publish/recommend
    "csv_path": "..."           # for catalogue_import
  }

Usage:
  python scripts/batch_runner.py --input test_pack/inputs --output test_pack/outputs --base-url http://localhost:8080
"""
import argparse
import json
import os
import sys
import time
import uuid

import httpx


def poll_job(client: httpx.Client, base_url: str, job_id: str, timeout_s: float = 60.0) -> dict:
    start = time.time()
    while time.time() - start < timeout_s:
        resp = client.get(f"{base_url}/api/v1/jobs/{job_id}")
        data = resp.json()
        if data.get("status") in ("succeeded", "failed"):
            return data
        time.sleep(0.3)
    return {"status": "timeout", "job_id": job_id}


def run_one(client: httpx.Client, base_url: str, spec: dict) -> dict:
    kind = spec.get("kind")
    result = {"kind": kind, "input": spec}

    if kind == "publish":
        destination_id = spec.get("destination_id")
        if not destination_id and spec.get("destination"):
            r = client.post(f"{base_url}/api/v1/destinations", json=spec["destination"])
            r.raise_for_status()
            destination_id = r.json()["id"]
        idem_key = spec.get("idempotency_key") or f"batch-{uuid.uuid4().hex}"
        r = client.post(f"{base_url}/api/v1/publish", headers={"Idempotency-Key": idem_key},
                         json={"destination_id": destination_id, "rendition": spec["rendition"]})
        result["accepted"] = r.status_code
        if r.status_code == 202:
            result["job"] = poll_job(client, base_url, r.json()["job_id"])
        else:
            result["error_response"] = r.json()

    elif kind == "certify":
        destination_id = spec.get("destination_id")
        if not destination_id and spec.get("destination"):
            r = client.post(f"{base_url}/api/v1/destinations", json=spec["destination"])
            r.raise_for_status()
            destination_id = r.json()["id"]
        r = client.post(f"{base_url}/api/v1/destinations/{destination_id}/certify")
        result["accepted"] = r.status_code
        if r.status_code == 202:
            result["job"] = poll_job(client, base_url, r.json()["job_id"])
        else:
            result["error_response"] = r.json()

    elif kind == "catalogue_import":
        with open(spec["csv_path"], "rb") as f:
            r = client.post(f"{base_url}/api/v1/catalogue/import",
                             files={"file": (os.path.basename(spec["csv_path"]), f, "text/csv")},
                             params={"check_reachability": spec.get("check_reachability", False)})
        result["accepted"] = r.status_code
        if r.status_code == 202:
            result["job"] = poll_job(client, base_url, r.json()["job_id"], timeout_s=300)
        else:
            result["error_response"] = r.json()

    elif kind == "recommend":
        r = client.post(f"{base_url}/api/v1/recommend", json=spec.get("body", {}))
        result["status_code"] = r.status_code
        result["response"] = r.json()

    else:
        result["error"] = f"unknown kind '{kind}'"

    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="folder of *.json test inputs, or a single .json file")
    ap.add_argument("--output", required=True, help="output folder for one result file per input")
    ap.add_argument("--base-url", default=os.environ.get("INCUBRIX_BASE_URL", "http://localhost:8080"))
    args = ap.parse_args()

    os.makedirs(args.output, exist_ok=True)

    if os.path.isdir(args.input):
        input_files = sorted(
            os.path.join(args.input, f) for f in os.listdir(args.input) if f.endswith(".json")
        )
    else:
        input_files = [args.input]

    if not input_files:
        print(f"No .json input files found in {args.input}", file=sys.stderr)
        sys.exit(1)

    summary = {"total": len(input_files), "succeeded": 0, "failed": 0, "results": []}

    with httpx.Client(timeout=30.0) as client:
        for path in input_files:
            name = os.path.splitext(os.path.basename(path))[0]
            with open(path) as f:
                spec = json.load(f)
            print(f"Running {name} ...")
            try:
                result = run_one(client, args.base_url, spec)
            except Exception as e:
                result = {"kind": spec.get("kind"), "input": spec, "exception": str(e)}

            out_path = os.path.join(args.output, f"{name}.result.json")
            with open(out_path, "w") as f:
                json.dump(result, f, indent=2, default=str)

            ok = result.get("job", {}).get("status") == "succeeded" or result.get("status_code") == 200
            summary["succeeded" if ok else "failed"] += 1
            summary["results"].append({"name": name, "ok": ok, "output_file": out_path})

    with open(os.path.join(args.output, "_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n{summary['succeeded']}/{summary['total']} succeeded. "
          f"Results in {args.output}/ (see _summary.json)")


if __name__ == "__main__":
    main()
