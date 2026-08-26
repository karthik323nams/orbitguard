# OrbitGuard — Likely SIH Judge Questions

## Why SGP4?

SGP4 is the standard propagation model associated with TLE/GP-style mean elements and is appropriate for a prototype that works directly from publicly available GP data.

## Why not calculate probability of collision?

Because a credible operational Pc calculation requires uncertainty/covariance and encounter assumptions that are not present in the basic public GP record used by our MVP. We expose that limitation instead of inventing a number.

## Why not just use CelesTrak/SOCRATES?

Our project is not trying to replace an operational service. The innovation is the end-to-end prototype workflow: ingestion, local caching, multi-object screening, explainable prioritization, history, and interactive visualization in a developer-friendly architecture.

## Can it scale?

The current MVP uses spatial screening to avoid blindly evaluating every pair with the expensive closest-approach refinement. The next production step would add more aggressive parallelization, orbital-volume screening, covariance-aware assessment, and distributed storage.

## What happens when data changes?

Each refresh is cached, scans are persisted, and repeated pairs can be compared across observations. That creates a foundation for monitoring encounter evolution rather than a one-shot calculation.

## What is innovative here?

The strongest innovation claim is not a brand-new orbital-dynamics algorithm. It is the integration and explainability layer: turning open orbital data into a transparent, visual, historical conjunction-monitoring workflow suitable for smaller institutions and student teams.

## Is the 3D globe operationally precise?

No. The visualization is a screening/demo visualization. We explicitly document the coordinate-frame approximation and do not present it as precision orbit determination.
