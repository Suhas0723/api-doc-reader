from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic
import json
import os
import base64
import urllib.request
import urllib.error
from html.parser import HTMLParser

import scorer as sc

app = Flask(__name__)
CORS(app)

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

# Claude is only asked for semantic quality - mechanical checks happen in Python.
# semanticScore: 0-20 per endpoint (are descriptions clear, accurate, non-bloated?)
SEMANTIC_PROMPT = """You are an API documentation quality reviewer. For each endpoint below, assess the SEMANTIC quality of its human-written text only (summaries, descriptions, response descriptions). You are NOT checking structural completeness - that is handled separately.

Return ONLY a valid JSON object (no markdown, no preamble):
{{
  "endpoints": [
    {{
      "method": "<method>",
      "path": "<path>",
      "semanticScore": <integer 0-20>,
      "smells": ["lazy"|"bloated"|"tangled"|"fragmented"],
      "analysis": "<1-2 sentence diagnosis of text quality>",
      "fixes": ["<concrete text improvement 1>", "<concrete text improvement 2>"]
    }}
  ],
  "summary": "<2 sentence overall assessment of documentation prose quality>",
  "recommendations": [
    {{
      "title": "<short action title>",
      "detail": "<why this matters and how to fix it>"
    }}
  ]
}}

Semantic score guide (0-20):
- 17-20: Descriptions are clear, specific, accurate, and useful to an agent
- 12-16: Mostly clear with minor vagueness or filler
- 7-11:  Vague, generic, or partially misleading descriptions
- 0-6:   Missing, copied boilerplate, or actively incorrect

Smell tags (semantic only - do not tag structural issues):
- lazy: summary/description is vague, trivially short, or says nothing useful
- bloated: verbose padding with little informational value
- tangled: mixes unrelated concerns in one description
- fragmented: description references info that is not present or linked

Endpoints to assess:
{endpoints}"""

PROSE_EXTRACT_PROMPT = """You are reading API documentation written as unstructured prose (from a PDF, web page, Confluence page, etc.). Extract a structured representation of the API from this text.

Return ONLY a valid JSON object with this structure (no markdown, no preamble):
{{
  "api_name": "<name of the API or service>",
  "base_url": "<base URL if mentioned, else null>",
  "auth_mechanism": "<description of auth, e.g. 'Bearer token', 'API key in header', 'OAuth2', or null if not mentioned>",
  "endpoints": [
    {{
      "method": "<GET|POST|PUT|DELETE|PATCH|UNKNOWN>",
      "path": "<path or descriptive name if path not explicit>",
      "description": "<what this endpoint does>",
      "parameters": [
        {{"name": "<param name>", "in": "<query|path|body|header>", "description": "<what it does>", "required": <true|false>}}
      ],
      "request_body": "<description of request body if any, else null>",
      "responses": [
        {{"status": "<200|400|etc or 'success'/'error'>", "description": "<what is returned>"}}
      ],
      "auth_required": <true|false|null>,
      "examples_present": <true|false>
    }}
  ],
  "missing_info": ["<list of things that seem to be missing or unclear in the docs>"]
}}

If you cannot find clear endpoint information, do your best with what is available. Include up to 10 endpoints.

Prose documentation to parse:
{text}"""

PROSE_SEMANTIC_PROMPT = """You are an API documentation quality reviewer assessing prose API documentation (not a formal OpenAPI spec). Evaluate the semantic quality of the extracted endpoint descriptions.

Return ONLY a valid JSON object (no markdown, no preamble):
{{
  "endpoints": [
    {{
      "method": "<method>",
      "path": "<path>",
      "semanticScore": <integer 0-20>,
      "smells": ["lazy"|"bloated"|"tangled"|"fragmented"],
      "analysis": "<1-2 sentence diagnosis>",
      "fixes": ["<concrete improvement 1>", "<concrete improvement 2>"]
    }}
  ],
  "summary": "<2 sentence assessment - note this was scored from prose docs, not a formal spec>",
  "recommendations": [
    {{
      "title": "<short action title>",
      "detail": "<why this matters and how to fix it>"
    }}
  ]
}}

Semantic score guide (0-20):
- 17-20: Clear, specific, accurate descriptions useful to an agent
- 12-16: Mostly clear with minor vagueness
- 7-11:  Vague, generic, or incomplete
- 0-6:   Missing, boilerplate, or actively misleading

Always include a recommendation to publish a formal OpenAPI spec.

Extracted endpoints:
{endpoints}

Missing info identified during extraction:
{missing_info}"""

MCP_PROMPT = """Given this API analysis, generate TWO artifacts. Return ONLY valid JSON with this structure (no markdown):
{{
  "mcp": "<MCP server stub as a string with escaped newlines>",
  "skill": "<SKILL.md content as a string with escaped newlines>"
}}

Generate a Python FastMCP server stub that:
1. Includes only the top-scoring endpoints (curated, not all)
2. Has rich docstrings explaining what each tool does for an AI agent
3. Includes type hints and Pydantic models for inputs
4. Has a clear module docstring explaining the API's purpose
5. Uses progressive disclosure patterns

Generate a SKILL.md that:
1. Follows the standard SKILL.md format with name, description, usage examples
2. Lists the curated tools with their purposes
3. Includes agent-specific guidance (when to use, rate limits, auth requirements)
4. Is concise and optimized for token efficiency

Top endpoints (by score):
{endpoints}

Original spec summary: {summary}

Source material (truncated):
{spec}"""


# ---------------------------------------------------------------------------
# HTML text extractor
# ---------------------------------------------------------------------------

class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "header"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "header"):
            self._skip = False
        if tag in ("p", "li", "h1", "h2", "h3", "h4", "tr", "div"):
            self._parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            stripped = data.strip()
            if stripped:
                self._parts.append(stripped + " ")

    def get_text(self):
        return " ".join("".join(self._parts).split())


def _scrape_url(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        html = raw.decode(charset, errors="replace")
    parser = _TextExtractor()
    parser.feed(html)
    text = parser.get_text()
    return text[:20000]


# ---------------------------------------------------------------------------
# Hybrid scoring helpers
# ---------------------------------------------------------------------------

def _call_claude(prompt: str, max_tokens: int = 2000) -> dict:
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = "".join(b.text for b in message.content if hasattr(b, "text"))
    clean = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(clean)


def _build_hybrid_result(spec_dict: dict, semantic: dict) -> dict:
    """
    Combine mechanical scores from scorer.py with Claude's semantic scores.
    Returns the full result dict ready for the frontend.
    """
    operations = sc.extract_operations(spec_dict)
    ops_for_semantic = operations[:20]

    global_info = sc.compute_global_penalties(spec_dict)

    semantic_map = {
        (e["method"].upper(), e["path"]): e
        for e in semantic.get("endpoints", [])
    }

    endpoints_out = []
    endpoint_totals = []

    for method, path, operation in ops_for_semantic:
        mech = sc.score_endpoint(operation, method, spec_dict)
        sem = semantic_map.get((method, path), {})

        semantic_score = max(0, min(20, sem.get("semanticScore", 10)))
        total = min(100, mech["mechanicalScore"] + semantic_score)
        endpoint_totals.append(total)

        all_smells = list(set(mech["smells"]) | set(sem.get("smells", [])))

        endpoints_out.append({
            "method": method,
            "path": path,
            "score": total,
            "smells": all_smells,
            "analysis": sem.get("analysis", ""),
            "fixes": sem.get("fixes", []),
            "scoreBreakdown": {
                "mechanical": mech["mechanicalScore"],
                "semantic": semantic_score,
                "deductions": mech["deductions"],
            },
        })

    overall = sc.compute_overall_score(endpoint_totals, global_info["totalPenalty"])
    smells_agg = sc.aggregate_smells(endpoints_out)
    total_smells = sum(smells_agg.values())

    return {
        "overallScore": overall,
        "summary": semantic.get("summary", ""),
        "totalSmells": total_smells,
        "smells": smells_agg,
        "endpoints": endpoints_out,
        "recommendations": semantic.get("recommendations", []),
        "scoreBreakdown": {
            "globalPenalties": global_info["adjustments"],
            "endpointAverage": round(sum(endpoint_totals) / len(endpoint_totals)) if endpoint_totals else 0,
        },
    }


def _prose_mechanical_penalties(extracted: dict) -> tuple[int, list[dict]]:
    """Deterministic penalties for prose docs based on extracted structure fields."""
    total = 0
    adjustments = []

    def penalize(reason: str, points: int, smell: str):
        nonlocal total
        total += points
        adjustments.append({"reason": reason, "penalty": points, "smell": smell})

    penalize("no_machine_readable_spec", 10, "fragmented")

    if not extracted.get("base_url"):
        penalize("no_base_url", 5, "lazy")

    if not extracted.get("auth_mechanism"):
        penalize("no_auth_mechanism", 8, "security")

    endpoints = extracted.get("endpoints", [])
    missing_examples = sum(1 for e in endpoints if not e.get("examples_present", False))
    if missing_examples:
        penalize("endpoints_missing_examples", min(missing_examples * 3, 15), "response")

    return total, adjustments


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    spec_text = data.get("spec", "").strip()
    if not spec_text:
        return jsonify({"error": "No spec provided"}), 400

    try:
        spec_dict = sc.parse_spec(spec_text)
    except Exception:
        return jsonify({"error": "Could not parse spec as JSON or YAML"}), 400

    operations = sc.extract_operations(spec_dict)
    if not operations:
        return jsonify({"error": "No endpoints found in spec"}), 400

    try:
        semantic_input = sc.build_semantic_input(operations[:20])
        semantic = _call_claude(
            SEMANTIC_PROMPT.format(endpoints=json.dumps(semantic_input, indent=2))
        )
        result = _build_hybrid_result(spec_dict, semantic)
        return jsonify(result)
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Failed to parse Claude response: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/analyze-prose", methods=["POST"])
def analyze_prose():
    """Two-step pipeline: extract structure from prose, then score it."""
    data = request.get_json()
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        extracted = _call_claude(
            PROSE_EXTRACT_PROMPT.format(text=text[:15000]),
            max_tokens=2000,
        )

        prose_penalty, prose_adjustments = _prose_mechanical_penalties(extracted)

        endpoints = extracted.get("endpoints", [])
        semantic_input = [
            {
                "method": e.get("method", "UNKNOWN"),
                "path": e.get("path", ""),
                "description": e.get("description", ""),
                "params": e.get("parameters", []),
                "responseDescriptions": {r["status"]: r["description"] for r in e.get("responses", [])},
            }
            for e in endpoints[:20]
        ]
        semantic = _call_claude(
            PROSE_SEMANTIC_PROMPT.format(
                endpoints=json.dumps(semantic_input, indent=2),
                missing_info=json.dumps(extracted.get("missing_info", [])),
            ),
            max_tokens=2000,
        )

        semantic_map = {
            (e["method"].upper(), e["path"]): e
            for e in semantic.get("endpoints", [])
        }

        endpoints_out = []
        endpoint_totals = []

        for ep in endpoints[:20]:
            method = ep.get("method", "UNKNOWN").upper()
            path = ep.get("path", "")
            sem = semantic_map.get((method, path), {})
            semantic_score = max(0, min(20, sem.get("semanticScore", 10)))

            prose_base = 40
            total = min(100, prose_base + semantic_score)
            endpoint_totals.append(total)

            endpoints_out.append({
                "method": method,
                "path": path,
                "score": total,
                "smells": sem.get("smells", []),
                "analysis": sem.get("analysis", ""),
                "fixes": sem.get("fixes", []),
            })

        avg = round(sum(endpoint_totals) / len(endpoint_totals)) if endpoint_totals else 50
        overall = max(0, min(100, avg - prose_penalty))
        smells_agg = sc.aggregate_smells(endpoints_out)

        result = {
            "overallScore": overall,
            "summary": semantic.get("summary", ""),
            "totalSmells": sum(smells_agg.values()),
            "smells": smells_agg,
            "endpoints": endpoints_out,
            "recommendations": semantic.get("recommendations", []),
            "scoreBreakdown": {
                "proseBaseline": 40,
                "prosePenalties": prose_adjustments,
                "totalProsePenalty": prose_penalty,
            },
            "_source": {
                "api_name": extracted.get("api_name"),
                "base_url": extracted.get("base_url"),
                "auth_mechanism": extracted.get("auth_mechanism"),
                "missing_info": extracted.get("missing_info", []),
            },
        }
        return jsonify(result)
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Failed to parse response: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ingest/url", methods=["POST"])
def ingest_url():
    data = request.get_json()
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    if not url.startswith(("http://", "https://")):
        return jsonify({"error": "URL must start with http:// or https://"}), 400

    try:
        text = _scrape_url(url)
        if not text or len(text) < 100:
            return jsonify({"error": "Could not extract meaningful text from that URL"}), 422
        return jsonify({"text": text, "char_count": len(text)})
    except urllib.error.HTTPError as e:
        return jsonify({"error": f"HTTP {e.code} fetching URL"}), 422
    except urllib.error.URLError as e:
        return jsonify({"error": f"Could not reach URL: {e.reason}"}), 422
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ingest/file", methods=["POST"])
def ingest_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    f = request.files["file"]
    filename = f.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    allowed = {"pdf", "txt", "md", "rst", "html", "htm"}
    if ext not in allowed:
        return jsonify({"error": f"Unsupported file type .{ext}. Allowed: {', '.join(sorted(allowed))}"}), 422

    raw_bytes = f.read(5 * 1024 * 1024)

    if ext == "pdf":
        b64 = base64.standard_b64encode(raw_bytes).decode("utf-8")
        try:
            msg = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {"type": "base64", "media_type": "application/pdf", "data": b64}
                        },
                        {
                            "type": "text",
                            "text": "Extract all text content from this PDF, preserving the structure as best you can. Return only the extracted text, no commentary."
                        }
                    ]
                }])
            text = "".join(b.text for b in msg.content if hasattr(b, "text"))
        except Exception as e:
            return jsonify({"error": f"PDF extraction failed: {str(e)}"}), 500
    else:
        try:
            text = raw_bytes.decode("utf-8", errors="replace")
            if ext in ("html", "htm"):
                parser = _TextExtractor()
                parser.feed(text)
                text = parser.get_text()
        except Exception as e:
            return jsonify({"error": f"Could not read file: {str(e)}"}), 500

    text = text.strip()
    if not text or len(text) < 50:
        return jsonify({"error": "Could not extract meaningful text from the file"}), 422

    return jsonify({"text": text[:20000], "char_count": len(text)})


@app.route("/api/generate-mcp", methods=["POST"])
def generate_mcp():
    data = request.get_json()
    spec = data.get("spec", "").strip()
    analysis = data.get("analysis", {})

    if not analysis:
        return jsonify({"error": "Missing analysis"}), 400

    top_endpoints = sorted(
        analysis.get("endpoints", []),
        key=lambda e: e.get("score", 0),
        reverse=True
    )[:5]

    try:
        result = _call_claude(
            MCP_PROMPT.format(
                endpoints=json.dumps(top_endpoints, indent=2),
                summary=analysis.get("summary", ""),
                spec=spec[:2000] if spec else "(prose documentation - no formal spec)"
            ),
            max_tokens=2000,
        )
        return jsonify(result)
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Failed to parse MCP output: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)