# AI Code Review — Backend

FastAPI backend that processes uploaded code files and runs AI + static analysis.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/upload` | Upload files (multipart/form-data, field: `files`) |
| GET | `/api/v1/status/{session_id}` | Poll analysis progress |
| GET | `/api/v1/results/{session_id}` | Fetch completed results |
| GET | `/api/v1/export/{session_id}/{format}` | Download results (`excel` or `markdown`) |
| DELETE | `/api/v1/session/{session_id}` | Clean up session |
| GET | `/health` | Health check |

## Setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000
```

> **Tip:** On Windows, if `uvicorn` isn't on your PATH, run it as a module:
> `python -m uvicorn app.main:app --reload --port 8000`.

**Recommended:** use a virtual environment so dependencies stay isolated from
your global Python (delete `.venv` to remove everything). Run this *before*
`pip install`:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key |
| `ALLOWED_ORIGINS` | No | CORS origins (default: localhost:5173,3000) |
| `LOG_LEVEL` | No | Logging level (default: INFO) |
