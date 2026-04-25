# Lead Catalyst Pro UI

This is an optional dashboard UI for working live prospect records and viewing:
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

The backend prospect list comes from `data/prospects.json` by default.

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
- `Run Enrichment` (brief generation + CRM enrichment)
- `Send Outreach` (provider-backed send through Resend or MailerSend)
- `Process Reply` (manual fallback that uses the same backend reply-processing path as inbound email)
- `Send Booking Link` (sends the real `CALCOM_BOOKING_LINK`)
- `Sync Booking` (records a booking against the prospect and updates HubSpot)
- `Refresh CRM` (re-syncs qualification and enrichment fields)
