# AI Code Review — Frontend

React + Vite frontend for the AI Code Review application.

## Setup

```bash
cd frontend
npm install
npm run dev
```

Runs on http://localhost:5173. Proxies `/api` to the backend at `http://localhost:8000`.

## Components

| Component | Description |
|-----------|-------------|
| `FileUpload` | Drag-and-drop file input with validation |
| `ProgressBar` | Real-time analysis status display |
| `ResultsTable` | Sortable, filterable issue table with expandable rows |
| `ExportButtons` | Excel and Markdown export download triggers |

## Build for Production

```bash
npm run build
# Output in dist/
```
