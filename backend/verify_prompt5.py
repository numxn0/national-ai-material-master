import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import asyncio
import json
from main import app

async def make_request(method, path, body=None, headers=None):
    if headers is None:
        headers = []
    if body is None:
        body_bytes = b""
    elif isinstance(body, str):
        body_bytes = body.encode("utf-8")
    elif isinstance(body, dict):
        body_bytes = json.dumps(body).encode("utf-8")
        headers.append([b"content-type", b"application/json"])
    else:
        body_bytes = body

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [[b"host", b"testserver"]] + headers,
    }
    status_code = None
    response_body = []
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body_bytes, "more_body": False}
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        nonlocal status_code
        if message["type"] == "http.response.start":
            status_code = message["status"]
        elif message["type"] == "http.response.body":
            response_body.append(message.get("body", b""))

    await app(scope, receive, send)
    res_str = b"".join(response_body).decode("utf-8")
    return status_code, res_str

async def run_prompt5_checks():
    print("=== Verification 1: Health Check ===")
    status, body = await make_request("GET", "/health")
    assert status == 200, f"/health failed with {status}: {body}"
    print("  [PASS] /health returns HTTP 200")

    print("\n=== Verification 2: POST /api/materials/normalize-text ===")
    payload = {
        "raw_description": "S.S. PIPE 50NB SCH-40 OD 60.3MM ID 52MM THK 4MM DIA 50MM",
        "uom": "MTR",
        "category": "pipe"
    }
    status, body = await make_request("POST", "/api/materials/normalize-text", body=payload)
    assert status == 200, f"/normalize-text failed with {status}: {body}"
    res = json.loads(body)
    print("  [PASS] Raw description:", res["raw_description"])
    print("  [PASS] Cleaned description:", res["cleaned_description"])
    print("  [PASS] Standard description:", res["standard_description"])
    print("  [PASS] Normalized UOM:", res["normalized_uom"])
    print("  [PASS] Normalized Category:", res["normalized_category"])
    print("  [PASS] Tokens count:", len(res["normalized_tokens"]))
    assert res["normalized_uom"] == "M"
    assert res["normalized_category"] == "PIPES_AND_TUBES"
    assert "STAINLESS STEEL" in res["standard_description"]
    assert "NOMINAL BORE" in res["standard_description"]
    assert "SCHEDULE 40" in res["standard_description"]
    assert "OUTER DIAMETER" in res["standard_description"]
    assert "INNER DIAMETER" in res["standard_description"]
    assert "THICKNESS" in res["standard_description"]
    assert "DIAMETER" in res["standard_description"]

    print("\n=== Verification 3: Sample CSV Preview after Ingestion Refactor ===")
    status, body = await make_request("GET", "/api/materials/preview-sample")
    assert status == 200, f"/preview-sample failed with {status}: {body}"
    sample_res = json.loads(body)
    assert sample_res["success"] is True
    assert len(sample_res["valid_records"]) == 10
    print("  [PASS] /api/materials/preview-sample successfully processed 10 valid records.")
    for rec in sample_res["valid_records"][:3]:
        print(f"    Item {rec['source_material_code']}: UOM={rec['uom']}, Category={rec['category']}")

    print("\n=== Verification 4: Common Normalization Test Cases ===")
    test_cases = [
        ("SS PIPE 50 NB SCH 40 ASTM A312", "MTR", "pipe", "STAINLESS STEEL", "M", "PIPES_AND_TUBES"),
        ("S.S. PIPE 50NB SCH-40", "METER", "piping", "STAINLESS STEEL", "M", "PIPES_AND_TUBES"),
        ("BEARING 6205 ZZ", "NOS", "bearing", "BEARING 6205 ZZ", "EA", "BEARINGS"),
        ("PVC CABLE 3 CORE 2.5 SQMM", "MTR", "cable", "CABLE", "M", "ELECTRICAL_CABLES"),
        ("BALL VALVE 50MM SS304 PN16", "NOS", "valve", "BALL VALVE", "EA", "VALVES"),
        ("INDUCTION MOTOR 10HP 1440RPM", "NOS", "motor", "MOTOR", "EA", "MOTORS"),
    ]
    for desc, u, cat, exp_str, exp_u, exp_cat in test_cases:
        s, b = await make_request("POST", "/api/materials/normalize-text", body={
            "raw_description": desc,
            "uom": u,
            "category": cat
        })
        assert s == 200
        r = json.loads(b)
        assert exp_str in r["standard_description"], f"Missing {exp_str} in {r['standard_description']}"
        assert r["normalized_uom"] == exp_u, f"Expected {exp_u}, got {r['normalized_uom']}"
        assert r["normalized_category"] == exp_cat, f"Expected {exp_cat}, got {r['normalized_category']}"
        print(f"  [PASS] '{desc}' -> UOM: {r['normalized_uom']} | Cat: {r['normalized_category']}")

    print("\n=== ALL PROMPT 5 VERIFICATION CHECKS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    asyncio.run(run_prompt5_checks())
