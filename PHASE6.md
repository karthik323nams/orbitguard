# OrbitGuard Phase 6 — Live 3D Orbital Visualization

This phase adds a Three.js / React Three Fiber visualization driven by the backend's real SGP4 propagation endpoint.

## What is real
- The backend fetches the selected object's current OMM/GP data from CelesTrak.
- SGP4 generates a sampled 3-hour trajectory.
- The frontend renders those propagated TEME positions as a 3D orbit trail.
- The marker animates through the actual propagated states.

## Coordinate-frame note
The endpoint explicitly labels the output frame as **TEME**. The visualization normalizes the position vectors by Earth's mean equatorial radius for rendering. It is not yet an Earth-fixed (ITRF/ECEF) ground-track view and should not be presented as one.

## Run
Backend:
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Next scientific visualization upgrade
Add TEME → ITRF/ECEF conversion using a library with Earth orientation support, then add ground tracks, multiple live objects, and conjunction markers from Phase 3 events.
