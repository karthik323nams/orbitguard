# OrbitGuard Dashboard — Phase 5

React + TypeScript + Vite dashboard for the OrbitGuard backend.

## Run

From `frontend/`:

```bash
npm install
npm run dev
```

Backend expected at `http://127.0.0.1:8000` by default. Override with:

```bash
VITE_API_URL=http://127.0.0.1:8000 npm run dev
```

## Demo behavior

The dashboard starts with a realistic demo state so it remains presentation-ready even when the backend is offline. Click **Refresh data** to query the Phase 4 backend. If the backend responds, live OMM cache/conjunction results replace the demo values.
