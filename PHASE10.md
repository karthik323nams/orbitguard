# OrbitGuard Phase 10 — Historical Conjunction Tracking & Alert Evolution

## Goal
Turn the one-shot conjunction scanner into a stateful monitoring loop. Each scan is preserved, and repeated observations of the same object pair can be compared over time.

## Backend
- `app/database/history.py` adds SQLite tables for `scan_runs` and `conjunction_observations`.
- `/conjunctions/scan` now writes a scan run and all detected conjunction observations.
- `/conjunctions/history?catalog_a=...&catalog_b=...` returns chronological observations plus a simple trend classification:
  - `NEW`: first stored observation for the pair
  - `WORSENING`: risk score rises by >= 5 or miss distance drops by >= 2 km versus the previous observation
  - `IMPROVING`: risk score falls by >= 5 or miss distance rises by >= 2 km
  - `STABLE`: smaller changes
- `/conjunctions/history/runs` returns recent scan-run metadata.

## Frontend
The conjunction-detail drawer now includes **Alert Evolution**:
- observation count
- trend badge
- compact risk-score history sparkline
- latest observations with timestamp, risk, miss distance, and band
- delta note from the previous scan

## Why this matters
A collision-avoidance monitoring system should not treat each scan as an isolated snapshot. Keeping historical observations lets analysts see whether a conjunction is becoming more or less concerning as new orbital data arrives.

## Scientific framing
This is still a prototype monitoring and prioritization layer. It does not claim operational probability of collision. The same limitations from Phase 9 remain: covariance/uncertainty and object-size information are not synthesized from public GP data in this MVP.

## How to demo
1. Run the backend and frontend.
2. Click **Refresh data** to execute a conjunction scan.
3. Open a detected event.
4. The drawer shows `NEW` on the first observation.
5. Run **Refresh data** again after the data changes/refreshes.
6. Open the same pair to show the stored time series and `STABLE`, `IMPROVING`, or `WORSENING` trend.
