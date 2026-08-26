# OrbitGuard Phase 7 — Conjunction-to-3D Visualization

Phase 7 connects the conjunction detection engine directly to the 3D SGP4 viewer.

## New flow

1. User selects a detected conjunction.
2. Frontend sends both catalog numbers to `/conjunctions/visualization`.
3. Backend recomputes the pair's closest approach and creates a short trajectory window centered on TCA.
4. Frontend renders both propagated trajectories in TEME coordinates.
5. The TCA positions are marked and joined by a miss-distance vector.
6. The event's miss distance and TCA are shown in the 3D overlay.

## New endpoint

`GET /conjunctions/visualization?catalog_a=<A>&catalog_b=<B>&duration_minutes=20&step_seconds=30`

The response contains:
- conjunction event metadata
- TCA
- miss distance
- TCA position for both objects
- two propagated trajectories
- coordinate-frame label (`TEME`)

## Scientific note

This remains a research/demo visualization. The positions are SGP4/TEME states and are not yet converted to an Earth-fixed ITRF/ECEF frame. The miss-distance risk band is a transparent prototype screen, not an operational collision probability.

## Validation

Python source was compile-checked successfully. Full runtime testing requires the dependencies in `backend/requirements.txt` and `frontend` packages from `package.json`.
