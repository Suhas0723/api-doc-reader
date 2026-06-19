"""
Deterministic mechanical scoring for OpenAPI specs.

Endpoints are scored out of 80 (mechanical) + 20 (Claude semantic) = 100.
Global penalties reduce the overall score after averaging endpoint scores.
"""

import json
import yaml

# Per-endpoint penalty table: key -> (smell_category, points)
ENDPOINT_PENALTIES = {
    "no_summary":             ("lazy",     8),
    "short_summary":          ("lazy",     4),
    "no_description":         ("lazy",     4),
    "undescribed_params":     ("input",    4),  # applied proportionally, cap 12
    "untyped_params":         ("input",    2),  # applied proportionally, cap 6
    "no_request_body_schema": ("input",    6),  # POST/PUT/PATCH only
    "no_4xx_response":        ("response", 6),
    "no_5xx_response":        ("response", 3),
    "no_200_schema":          ("response", 5),
    "no_examples":            ("response", 4),
    "missing_security":       ("security", 5),  # when global schemes exist
}

GLOBAL_PENALTIES = {
    "no_security_schemes": ("security", 8),
    "no_servers":          ("lazy",     5),
}

MECHANICAL_MAX = 80  # Claude contributes the remaining 20


def parse_spec(spec_text: str) -> dict:
    spec_text = spec_text.strip()
    try:
        return json.loads(spec_text)
    except (json.JSONDecodeError, ValueError):
        pass
    return yaml.safe_load(spec_text)


def extract_operations(spec: dict) -> list[tuple]:
    """Return list of (method, path, operation_dict)."""
    http_methods = {"get", "post", "put", "delete", "patch", "head", "options"}
    ops = []
    for path, path_item in spec.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() in http_methods and isinstance(operation, dict):
                ops.append((method.upper(), path, operation))
    return ops


def _has_global_security(spec: dict) -> bool:
    return bool(
        spec.get("components", {}).get("securitySchemes")
        or spec.get("securityDefinitions")
    )


def _has_examples(operation: dict) -> bool:
    for param in operation.get("parameters", []):
        if "example" in param or "examples" in param:
            return True
        if "example" in param.get("schema", {}):
            return True
    rb = operation.get("requestBody", {})
    for media in rb.get("content", {}).values():
        if "example" in media or "examples" in media:
            return True
        if "example" in media.get("schema", {}):
            return True
    for resp in operation.get("responses", {}).values():
        if not isinstance(resp, dict):
            continue
        for media in resp.get("content", {}).values():
            if "example" in media or "examples" in media:
                return True
    return False


def score_endpoint(operation: dict, method: str, spec: dict) -> dict:
    """
    Returns:
      mechanicalScore  int  0-80
      smells           list of smell category strings
      deductions       list of {reason, penalty, smell}
    """
    score = MECHANICAL_MAX
    smells: set[str] = set()
    deductions = []

    def deduct(key: str, penalty: int | None = None):
        cat, default = ENDPOINT_PENALTIES[key]
        p = penalty if penalty is not None else default
        nonlocal score
        score -= p
        smells.add(cat)
        deductions.append({"reason": key, "penalty": p, "smell": cat})

    # Summary
    summary = (operation.get("summary") or "").strip()
    if not summary:
        deduct("no_summary")
    elif len(summary) < 10:
        deduct("short_summary")

    # Description
    if not (operation.get("description") or "").strip():
        deduct("no_description")

    # Parameters
    params = operation.get("parameters", [])
    undesc = sum(1 for p in params if not (p.get("description") or "").strip())
    untyped = sum(1 for p in params if not p.get("schema", {}).get("type"))
    if undesc:
        deduct("undescribed_params", min(undesc * 4, 12))
    if untyped:
        deduct("untyped_params", min(untyped * 2, 6))

    # Request body (write methods only)
    if method in ("POST", "PUT", "PATCH"):
        rb = operation.get("requestBody", {})
        has_schema = any(
            "schema" in media
            for media in rb.get("content", {}).values()
        )
        if not rb or not has_schema:
            deduct("no_request_body_schema")

    # Responses
    responses = operation.get("responses", {})
    if not any(str(c).startswith("4") for c in responses):
        deduct("no_4xx_response")
    if not any(str(c).startswith("5") for c in responses):
        deduct("no_5xx_response")

    resp_ok = responses.get("200") or responses.get("201")
    has_ok_schema = (
        isinstance(resp_ok, dict)
        and any("schema" in m for m in resp_ok.get("content", {}).values())
    )
    if not has_ok_schema:
        deduct("no_200_schema")

    # Examples
    if not _has_examples(operation):
        deduct("no_examples")

    # Security (only flag if global schemes exist but no security on endpoint)
    if _has_global_security(spec):
        endpoint_sec = operation.get("security")
        global_sec = spec.get("security")
        # endpoint_sec == [] means explicitly unauthenticated - intentional
        if endpoint_sec != [] and not global_sec and not endpoint_sec:
            deduct("missing_security")

    return {
        "mechanicalScore": max(0, score),
        "smells": list(smells),
        "deductions": deductions,
    }


def compute_global_penalties(spec: dict) -> dict:
    adjustments = []
    total = 0

    if not _has_global_security(spec):
        cat, penalty = GLOBAL_PENALTIES["no_security_schemes"]
        adjustments.append({"reason": "no_security_schemes", "penalty": penalty, "smell": cat})
        total += penalty

    if not spec.get("servers") and not spec.get("host"):
        cat, penalty = GLOBAL_PENALTIES["no_servers"]
        adjustments.append({"reason": "no_servers", "penalty": penalty, "smell": cat})
        total += penalty

    return {"totalPenalty": total, "adjustments": adjustments}


def build_semantic_input(operations: list[tuple]) -> list[dict]:
    """Build a compact representation to send to Claude for semantic scoring."""
    result = []
    for method, path, op in operations:
        params = op.get("parameters", [])
        responses = op.get("responses", {})
        result.append({
            "method": method,
            "path": path,
            "summary": (op.get("summary") or "").strip(),
            "description": (op.get("description") or "").strip(),
            "params": [
                {"name": p.get("name"), "description": (p.get("description") or "").strip()}
                for p in params
            ],
            "responseDescriptions": {
                str(code): (r.get("description") or "") if isinstance(r, dict) else ""
                for code, r in responses.items()
            },
        })
    return result


def compute_overall_score(
    endpoint_totals: list[int],
    global_penalty: int,
) -> int:
    if not endpoint_totals:
        return max(0, 100 - global_penalty)
    avg = sum(endpoint_totals) / len(endpoint_totals)
    return max(0, min(100, round(avg - global_penalty)))


def aggregate_smells(endpoint_results: list[dict]) -> dict:
    counts = {k: 0 for k in ("lazy", "bloated", "tangled", "fragmented", "response", "security", "input")}
    for ep in endpoint_results:
        for smell in ep.get("smells", []):
            if smell in counts:
                counts[smell] += 1
    return counts