# API Agent-Readiness Scorer

Scores OpenAPI specs against the Hermes documentation smell rubric and generates curated MCP server + SKILL.md artifacts.

## Project Structure

```
api-scorer/
├── backend/          # Flask API server
│   ├── app.py
│   ├── requirements.txt
│   └── .env.example
└── frontend/         # React app
    ├── public/
    └── src/
        ├── App.jsx
        ├── samples.js
        └── components/
            ├── ScoreRing.jsx
            ├── SmellsGrid.jsx
            ├── EndpointList.jsx
            └── MCPOutput.jsx
```

## Setup

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

python app.py
# Runs on http://localhost:5000
```

### 2. Frontend

```bash
cd frontend
npm install
npm start
# Runs on http://localhost:3000
# Proxies /api/* to Flask at :5000
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/analyze` | Analyze an OpenAPI spec. Body: `{ "spec": "..." }` |
| POST | `/api/generate-mcp` | Generate MCP + SKILL.md. Body: `{ "spec": "...", "analysis": {...} }` |
| GET | `/api/health` | Health check |

## How it works

1. User pastes an OpenAPI spec (YAML or JSON)
2. Flask sends it to Claude with the Hermes rubric prompt
3. Claude returns a structured JSON score with:
   - Overall 0–100 agent-readiness score
   - Per-smell counts (Lazy, Bloated, Tangled, Fragmented, Response, Security, Input)
   - Per-endpoint scores with specific fixes
   - Prioritized recommendations
4. Optionally generates a FastMCP Python stub + SKILL.md for the top endpoints

## Smell Rubric (Hermes)

| Smell | Description |
|-------|-------------|
| LAZY | Vague summaries, undocumented params, generic responses |
| BLOATED | Verbose descriptions with low info density |
| TANGLED | Mixes unrelated concerns in one block |
| FRAGMENTED | Key info scattered without linkage |
| RESPONSE | Missing status codes or error schemas |
| SECURITY | No auth schemes, missing scopes |
| INPUT | Undescribed request body fields or constraints |
