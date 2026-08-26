# Phase 3 Architecture

```text
                    CelesTrak
                       │
                       ▼
              ┌─────────────────┐
              │ Data Ingestion  │
              │ TLE group feed  │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ SGP4 Propagator │
              └────────┬────────┘
                       │
                 Position grid
                       │
                       ▼
              ┌─────────────────┐
              │ Spatial Hash     │
              │ Candidate filter │
              └────────┬────────┘
                       │
                 candidate pairs
                       │
                       ▼
              ┌─────────────────┐
              │ SGP4 + SciPy    │
              │ closest approach │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ Risk Classifier │
              └────────┬────────┘
                       │
                       ▼
              FastAPI JSON API
                       │
                       ▼
                React Dashboard
```
