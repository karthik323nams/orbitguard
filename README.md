# OrbitGuard — Phase 14

Phase 14 hardens the SIH live-validation workflow and the discrete-time conjunction screen.

Core pipeline:

CelesTrak GP JSON → OMM parsing → SGP4 propagation → spatial screening → closest-approach refinement → explainable risk index → dashboard/history.

Run the live validation from `backend/`:

```bash
python scripts/live_validate.py --group active --max-objects 100 --duration-minutes 30 --step-seconds 15
```

See `LIVE_VALIDATION.md` for the interpretation and SIH reporting guidance.
