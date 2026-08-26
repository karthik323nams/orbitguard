# OrbitGuard — Phase 4: OMM ingestion + local cache

Phase 4 replaces the legacy TLE-only ingestion path with CelesTrak **OMM JSON** for the active-group MVP, then caches normalized orbital records locally in SQLite.

CelesTrak's current documentation supports JSON GP output and states that GP updates occur every 2 hours. Its site also notes that new 6-digit catalog numbers cannot be represented in legacy TLE format, so the new ingestion path is intentionally OMM-based.

## Architecture

```text
CelesTrak GP JSON (OMM)
        ↓
OMM parser + sgp4.omm.initialize()
        ↓
Normalized orbital records
        ↓
SQLite cache (orbitguard.db)
        ↓
Propagation / conjunction scanner
        ↓
API
```

## Run

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Refresh the local cache

```text
GET /data/refresh?group=active&max_objects=500
```

Use the cache:

```text
GET /data/cache?group=active&limit=100
```

The scanner now consumes OMM JSON directly:

```text
GET /conjunctions/scan?group=active&max_objects=250
```

## Cache policy

CelesTrak asks users to download GP data only once per update; the current usage policy says GP updates are every 2 hours. The app therefore exposes a `cache_policy_hours=2` field and is designed so the scheduler can refresh no more than once per update window.

For an SIH demo, manual refresh is sufficient. A later production layer can add a scheduler/TTL guard.

## Database

SQLite is used for the MVP to keep setup simple. The schema stores:

- catalog number
- object name
- OMM epoch
- source group
- source format
- raw OMM JSON
- fetch timestamp

PostgreSQL can replace SQLite later without changing the API contracts.

## Important scientific limitation

The conjunction engine remains a **prototype screening system**. OMM/SGP4 propagation gives us a practical way to demonstrate tracking and close-approach detection, but this is not an operational conjunction-assessment service and its risk bands are not official collision probabilities.
