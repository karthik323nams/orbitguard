# OrbitGuard — SIH Validation & Positioning Pack

## 1. What the MVP demonstrably does

- Ingests public GP/OMM orbital element data.
- Uses SGP4 propagation to generate future object states.
- Screens multiple catalogued objects for close approaches.
- Refines the closest-approach time for candidate pairs.
- Computes miss distance and relative velocity at TCA.
- Produces an explainable prototype prioritization score.
- Stores repeated observations of the same object pair.
- Shows worsening/stable/improving/new trends.
- Visualizes one or more propagated trajectories in 3D.

## 2. What it does NOT claim

OrbitGuard does **not** claim to produce an operational probability of collision (Pc), maneuver recommendation, or mission-safety decision. Operational collision-risk assessment requires additional information such as covariance/uncertainty, object size/hard-body radius, and encounter geometry.

## 3. Why the data layer is future-proof

CelesTrak's GP documentation supports JSON/CSV/OMM formats and states that legacy TLE cannot represent catalog numbers above 99999. CelesTrak reported that the 5-digit catalog space was exhausted on 2026-07-11, making the OMM/JSON path important for a modern implementation.

## 4. Validation strategy

### A. Data provenance

Every live run should record:
- source = CelesTrak
- source group/query
- format = OMM/JSON
- fetch timestamp
- object epoch

### B. Numerical sanity checks

For each propagated object:
- reject non-finite position/velocity values
- reject duplicate catalog IDs within a scan
- enforce UTC timestamps
- verify that the scan horizon and time step are positive

### C. Conjunction sanity checks

For every event:
- object A != object B
- miss distance >= 0
- relative speed >= 0
- TCA lies within the scan window
- event is reproducible from the same cached orbital input

### D. Demo validation cases

1. **No-event case:** large screening distance threshold reduced enough that no candidates survive.
2. **Close-event case:** a stored/mock pair creates a visible TCA and risk explanation.
3. **Historical case:** repeat the same scan against a persistent database and confirm that a pair changes from NEW to a trend state.
4. **Stale-data case:** use older epochs and confirm the freshness component changes visibly.

## 5. Judge-safe terminology

Use:
- "conjunction candidate"
- "closest approach"
- "miss distance"
- "prototype risk index"
- "screening / prioritization"
- "public GP/OMM data"

Avoid:
- "guaranteed collision prediction"
- "true collision probability"
- "operational safety decision"
- "maneuver recommendation"
