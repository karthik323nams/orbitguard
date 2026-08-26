# OrbitGuard Live Validation

## Purpose

This runbook validates the real end-to-end pipeline against a current CelesTrak GP JSON feed. It is intentionally a **prototype validation**, not an operational conjunction-assessment certification.

## Run

```bash
cd backend
python scripts/live_validate.py --group active --max-objects 100 --duration-minutes 30 --step-seconds 15
```

The script prints a JSON report containing:

- records loaded and unique catalog numbers
- count of 6-digit-or-larger catalog numbers
- duplicate-ID check
- screening configuration and effective candidate radius
- detected conjunctions ranked by miss distance
- basic ingestion sanity checks

## Why the screen uses a 20 km/s bound

For a coarse sample interval, two objects can move toward one another between samples. The candidate-radius safety buffer is:

`screening_distance + max_relative_speed_bound × sample_interval`

The prototype uses 20 km/s as a conservative screening bound so the coarse stage is less likely to discard a pair solely because the encounter happened between samples. This is a screening heuristic, not a formal proof of completeness.

## What to record for the SIH report

Run the command immediately before your demo and save the JSON output. Record:

1. CelesTrak data timestamp / retrieval time.
2. Number of objects loaded.
3. Number of unique catalog numbers.
4. Number of 6-digit-or-larger catalog IDs, if present.
5. Number of candidate/detected conjunctions.
6. Minimum miss distance and corresponding TCA.
7. Runtime on your laptop.

## Important limitation

Do not present the prototype risk score as probability of collision. A real collision-risk assessment needs state uncertainty/covariance, encounter geometry and physical object size / hard-body radius. OrbitGuard's score is an explainable prioritization index for close approaches.
