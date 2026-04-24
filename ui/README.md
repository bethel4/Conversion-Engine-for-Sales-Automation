# Lead Catalyst Pro UI

This is an optional dashboard UI for running the **Act II enrichment pipeline** and viewing:
- `hiring_signal_brief` (merged signal schema)
- `competitor_gap_brief` (peers + gaps)

It calls the FastAPI backend in `agent/main.py`.

## Run

1) Start the API server (repo root):

```bash
uvicorn agent.main:app --reload --port 8000
```

2) Start the UI (new terminal):

```bash
cd ui
npm install
npm run dev
```

Open `http://localhost:3000`.

## Config

The UI talks to the backend via:
- `AGENT_API_URL` (default: `http://127.0.0.1:8000`)

Create `ui/.env.local`:

```bash
AGENT_API_URL=http://127.0.0.1:8000
```

## Render

If your backend is deployed on Render, point the UI at it:

```bash
AGENT_API_URL=https://conversion-engine-for-sales-automation.onrender.com
```

The dashboard provides:
- “Run enrichment” (brief generation)
- “Enrich → HubSpot” (writes enrichment + logs events)
- “Send email (Resend)” (sends email; keys remain server-side)
