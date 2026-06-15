# AI Code Review

A full-stack AI-powered code review application built with FastAPI, React, and the Anthropic Claude API.

Upload any codebase (or ZIP file) and receive a detailed analysis covering bugs, security vulnerabilities, performance issues, and best practice recommendations — with specific fixes for every finding.

## Architecture

```
Browser (React/Vite :5173)
        ↓ POST /api/v1/upload
FastAPI (:8000)
        ↓ asyncio background task
  ├── FileProcessor    — ZIP extraction, file reading
  ├── StaticAnalyzer   — ESLint · Stylelint · Bandit
  └── AIAnalyzer       — Claude API (claude-opus-4-7)
        ↓
  Results + source stored in-memory → polled by frontend
        ↓ GET /api/v1/export
  ExportService → .xlsx or .md download
        ↓ POST /api/v1/chat/{session_id}
  ChatService → grounded Q&A over the reviewed code + issues
```

## Quick Start

### 1. Get an Anthropic API Key

Sign up at https://console.anthropic.com/ and create an API key.

### 2. Backend Setup

```bash
cd ai-code-review/backend

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Open .env and set: ANTHROPIC_API_KEY=sk-ant-...

# Start the server
uvicorn app.main:app --reload --port 8000
```

The API will be running at http://localhost:8000  
Interactive docs: http://localhost:8000/docs

> **Tip:** On Windows, if `uvicorn` isn't on your PATH, run it as a module:
> `python -m uvicorn app.main:app --reload --port 8000` (and `python -m pip install ...`).

#### Recommended: use a virtual environment

The two commands above work, but they install packages into your global
Python. A virtual environment isolates this project's dependencies so they
can't conflict with other projects, and you can remove everything by simply
deleting the `.venv` folder. It takes a few seconds:

```bash
# Create the virtual environment
python -m venv .venv

# Activate it
# macOS/Linux:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (CMD):
.venv\Scripts\activate.bat
```

Run this **before** `pip install`, then continue with the steps above. While
the venv is active, `pip` and `uvicorn` are always on your PATH.

### 3. Frontend Setup

Open a new terminal:

```bash
cd ai-code-review/frontend

npm install
npm run dev
```

The app will be running at http://localhost:5173

### 4. Usage

1. Open http://localhost:5173 in your browser
2. Drag & drop code files or a ZIP archive onto the upload area
3. Click **Analyze Code**
4. Watch real-time progress as files are processed
5. Browse issues in the sortable, filterable results table
6. Export findings as **Excel** or **Markdown**
7. **Ask the AI assistant** about your code via the floating chat button in the bottom-right corner — it has read every uploaded file and the full review. Use a suggested question or type your own ("Are there security vulnerabilities?", "How do I fix the issue in X?", "Which file is riskiest?").

## AI Chat Assistant

After a review completes, a floating chat button appears in the bottom-right corner (so it's reachable without scrolling past the issues). Opening it reveals a popover that lets you interrogate the codebase in natural language. It is grounded: the backend rebuilds context from the **actual uploaded source** plus the **issues found**, so answers cite real files and fixes rather than guessing.

- **Endpoint:** `POST /api/v1/chat/{session_id}` with `{ "message": "...", "history": [...] }`
- **Scenario-aware prompts:** the panel suggests starter questions derived from the review (e.g. the count of high-severity issues, the file with the most findings).
- **Multi-provider:** uses the same `LLM_PROVIDER` configuration as the analyzer (Anthropic / Ollama / OpenAI-compatible / Gemini).
- Short conversation memory is kept per session; the source is cached so it survives instant cache-hit re-uploads.

## Supported File Types

| Language | Extensions |
|----------|-----------|
| JavaScript | `.js` `.jsx` |
| TypeScript | `.ts` `.tsx` |
| CSS | `.css` `.scss` `.sass` |
| HTML | `.html` |
| JSON | `.json` |
| Python | `.py` |
| Java | `.java` |
| Archives | `.zip` |

## Static Analysis (Optional)

For enhanced analysis, install these tools:

**JavaScript/TypeScript (ESLint):**
```bash
npm install -g eslint
```

**CSS (Stylelint):**
```bash
npm install -g stylelint stylelint-config-standard
```

**Python (Bandit):**
```bash
pip install bandit
```

These tools run automatically when available. The app works without them (AI-only analysis).

## Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `ANTHROPIC_API_KEY` | **Required.** Your Anthropic API key | — |
| `ALLOWED_ORIGINS` | CORS allowed origins | `http://localhost:5173,http://localhost:3000` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |

## Issue Severity Levels

| Level | Description |
|-------|-------------|
| 🔴 High | Security vulnerabilities, crashes, data loss risks |
| 🟡 Medium | Logic bugs, performance issues, bad practices |
| 🟢 Low | Style issues, minor improvements, documentation |

## Limits

- Max upload size: **100 MB**
- Max files per upload: **50**
- Files exceeding 150,000 characters are truncated with a warning
- Excluded directories: `node_modules`, `.git`, `dist`, `build`, `.next`
