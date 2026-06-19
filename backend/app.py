from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic
import json
import os
import base64
import urllib.request
import urllib.error
from html.parser import HTMLParser

app = Flask(__name__)
CORS(app)

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

ANALYSIS_PROMPT = """You are an API documentation quality analyzer using the Hermes rubric. Analyze the given OpenAPI spec and return ONLY a valid JSON object (no markdown, no preamble).

The JSON must have this exact structure:
{{
  "overallScore": <integer 0-100>,
  "summary": "<2 sentence assessment>",
  "totalSmells": <integer>,
  "smells": {{
    "lazy": <count>,
    "bloated": <count>,
    "tangled": <count>,
    "fragmented": <count>,
    "response": <count>,
    "security": <count>,
    "input": <count>
  }},
  "endpoints": [
    {{
      "method": "<GET|POST|PUT|DELETE|PATCH>",
      "path": "<path string>",
      "score": <integer 0-100>,
      "smells": ["lazy"|"bloated"|"tangled"|"fragmented"|"response"|"security"|"input"],
      "analysis": "<1-2 sentence diagnosis>",
      "fixes": ["<concrete fix 1>", "<concrete fix 2>"]
    }}
  ],
  "recommendations": [
    {{
      "title": "<short action title>",
      "detail": "<why this matters and how to fix it>"
    }}
  ]
}}

Score definitions:
- LAZY: vague/short summaries, undocumented parameters, generic response messages
- BLOATED: verbose descriptions with little informational value, padded text
- TANGLED: mixes unrelated concerns in one description
- FRAGMENTED: essential info scattered without linkage
- RESPONSE: missing error codes, no error schemas, missing examples, no 4xx/5xx docs
- SECURITY: no auth schemes defined, missing scopes, over-permissioned endpoints
- INPUT: undescribed request body properties, missing constraints

Overall score: 100 minus penalty points. Each smell = -3 to -8 points depending on severity.
Provide all endpoints (max 10) and 3-5 prioritized recommendations.

OpenAPI spec to analyze:
{spec}"""

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

PROSE_ANALYSIS_PROMPT = """You are an API documentation quality analyzer using the Hermes rubric. You are analyzing documentation that was written as unstructured prose (not a clean OpenAPI spec), so apply additional scrutiny for discoverability and agent-readiness.

Given this structured extraction from prose API documentation, return ONLY a valid JSON object (no markdown, no preamble).

The JSON must have this exact structure:
{{
  "overallScore": <integer 0-100>,
  "summary": "<2 sentence assessment — mention that this was scored from prose docs, not a formal spec>",
  "totalSmells": <integer>,
  "smells": {{
    "lazy": <count>,
    "bloated": <count>,
    "tangled": <count>,
    "fragmented": <count>,
    "response": <count>,
    "security": <count>,
    "input": <count>
  }},
  "endpoints": [
    {{
      "method": "<GET|POST|PUT|DELETE|PATCH|UNKNOWN>",
      "path": "<path string>",
      "score": <integer 0-100>,
      "smells": ["lazy"|"bloated"|"tangled"|"fragmented"|"response"|"security"|"input"],
      "analysis": "<1-2 sentence diagnosis>",
      "fixes": ["<concrete fix 1>", "<concrete fix 2>"]
    }}
  ],
  "recommendations": [
    {{
      "title": "<short action title>",
      "detail": "<why this matters and how to fix it>"
    }}
  ]
}}

Score definitions:
- LAZY: vague descriptions, undocumented parameters, generic response info
- BLOATED: verbose text with little informational value
- TANGLED: mixes unrelated concerns
- FRAGMENTED: essential info scattered, no cross-linking
- RESPONSE: missing error codes, no error descriptions, no examples
- SECURITY: auth mechanism unclear or undocumented, missing scope info
- INPUT: undescribed request fields, missing constraints or types

Additional prose-doc penalties:
- No machine-readable spec exists at all: -10 points
- Endpoints not clearly enumerated (hard to discover): -8 points
- Auth mechanism not explained: -8 points
- No base URL stated: -5 points
- Each endpoint missing examples: -3 points each

Provide all endpoints (max 10) and 4-5 prioritized recommendations. Include a recommendation to publish a formal OpenAPI spec if one is absent.

Extracted API structure:
{extracted}

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
    return text[:20000]  # cap to avoid huge context


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    spec = data.get("spec", "").strip()
    if not spec:
        return jsonify({"error": "No spec provided"}), 400

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": ANALYSIS_PROMPT.format(spec=spec)}]
        )
        raw = "".join(b.text for b in message.content if hasattr(b, "text"))
        clean = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean)
        return jsonify(result)
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Failed to parse analysis: {str(e)}"}), 500
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
        # Step 1: extract structured API info from prose
        extract_msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": PROSE_EXTRACT_PROMPT.format(text=text[:15000])}]
        )
        raw_extract = "".join(b.text for b in extract_msg.content if hasattr(b, "text"))
        clean_extract = raw_extract.replace("```json", "").replace("```", "").strip()
        extracted = json.loads(clean_extract)

        # Step 2: score the extracted structure
        score_msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": PROSE_ANALYSIS_PROMPT.format(
                extracted=json.dumps(extracted, indent=2),
                missing_info=json.dumps(extracted.get("missing_info", []))
            )}]
        )
        raw_score = "".join(b.text for b in score_msg.content if hasattr(b, "text"))
        clean_score = raw_score.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean_score)

        # Attach the extracted structure so the frontend can display source info
        result["_source"] = {
            "api_name": extracted.get("api_name"),
            "base_url": extracted.get("base_url"),
            "auth_mechanism": extracted.get("auth_mechanism"),
            "missing_info": extracted.get("missing_info", [])
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

    raw_bytes = f.read(5 * 1024 * 1024)  # 5 MB cap

    if ext == "pdf":
        # Use Claude's native PDF vision support
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
                }]
            )
            text = "".join(b.text for b in msg.content if hasattr(b, "text"))
        except Exception as e:
            return jsonify({"error": f"PDF extraction failed: {str(e)}"}), 500
    else:
        # Plain text variants
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
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": MCP_PROMPT.format(
                endpoints=json.dumps(top_endpoints, indent=2),
                summary=analysis.get("summary", ""),
                spec=spec[:2000] if spec else "(prose documentation — no formal spec)"
            )}]
        )
        raw = "".join(b.text for b in message.content if hasattr(b, "text"))
        clean = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean)
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
