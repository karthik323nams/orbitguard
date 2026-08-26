# Phase 14 — Live Validation Hardening

This phase hardens the Phase 13 validation path before SIH demonstration.

## Changes

- Raised the coarse-screen relative-speed safety bound from 15 km/s to 20 km/s.
- Parameterized the live validation script via CLI flags.
- Added duplicate-catalog and ingestion sanity checks.
- Added an explicit effective candidate-radius calculation to the validation report.
- Documented what evidence to record for the SIH report.

## Validation claim

The project now has a reproducible procedure for validating the live CelesTrak → OMM → SGP4 → screening → closest-approach → risk-ranking pipeline on the machine used for the demonstration.

The validation still does **not** establish operational collision probability or formal screening completeness.
