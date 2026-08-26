# OrbitGuard Phase 9 — Explainable Risk Engine

## What changed
The prototype no longer assigns severity from miss distance alone. Each conjunction receives an explainable prioritization index built from:

- 55% predicted miss distance
- 20% time-to-closest-approach (TCA) imminence
- 15% relative speed
- 10% orbital-data freshness

The API returns the overall score, band, component scores, reasons, and an explicit uncertainty-status field.

## Scientific boundary
This is a **prototype prioritization index**, not an operational probability of collision (Pc). Operational collision-risk assessment requires uncertainty/covariance information and object-size/hard-body-radius information. Public GP/OMM data used by this MVP does not justify fabricating those inputs.

## API output
`/conjunctions/pair`, `/conjunctions/scan`, and `/conjunctions/visualization` now include:

- `risk_score`
- `risk_breakdown.miss_distance_score`
- `risk_breakdown.imminence_score`
- `risk_breakdown.relative_speed_score`
- `risk_breakdown.freshness_score`
- `risk_breakdown.time_to_tca_minutes`
- `risk_breakdown.reasons`
- `risk_breakdown.uncertainty_status`

## Demo language
Use: **"Explainable prototype risk index for prioritizing close approaches."**
Do not use: **"collision probability"**, **"probability of impact"**, or **"operational collision warning"**.
