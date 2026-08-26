# OrbitGuard — 3-Minute SIH Demo Script

## 0:00–0:20 — Problem

"Low Earth orbit is becoming increasingly congested. A useful space-situational-awareness workflow has to turn orbital data into understandable close-approach information. Our challenge is to make that pipeline accessible and explainable at prototype scale."

## 0:20–0:45 — Live data

Open the Overview dashboard.

Show:
- tracked-object count
- data source / freshness
- 3D Earth view

Say:
"OrbitGuard ingests public GP/OMM orbital data and propagates object states using SGP4."

## 0:45–1:25 — Detect a conjunction

Open Conjunctions.

Select a high-priority event.

Show:
- object pair
- TCA
- miss distance
- relative velocity
- risk band

Say:
"We don't stop at displaying raw orbital elements. We screen object pairs, refine the closest approach, and rank the encounter with an explainable prototype index."

## 1:25–2:00 — 3D encounter

Open the selected event.

Show both trajectories and the TCA marker.

Say:
"The same event is now spatially explainable. You can see both predicted paths and the point of closest approach rather than relying only on a table."

## 2:00–2:30 — Why was it prioritized?

Open risk details.

Show the score components:
- miss distance
- imminence
- relative speed
- data freshness

Say:
"This is deliberately a prioritization index, not a fabricated collision probability. Operational Pc requires uncertainty/covariance and additional inputs."

## 2:30–2:50 — History

Open Analytics / Alert Evolution.

Show:
- repeated observations
- trend
- historical risk

Say:
"When new orbital data arrives, the same pair can be tracked over time. That lets us show whether the encounter is worsening, stable, improving, or newly detected."

## 2:50–3:00 — Close

"So OrbitGuard connects public orbital data, propagation, conjunction screening, explainable prioritization, historical tracking, and 3D visualization in one workflow — built as an extensible prototype for space situational awareness."
