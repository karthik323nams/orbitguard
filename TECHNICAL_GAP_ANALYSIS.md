# OrbitGuard — Technical Gap Analysis Before Final SIH Demo

## High priority

1. Run live end-to-end with CelesTrak OMM data on the team's machine.
2. Capture one complete real scan and preserve the raw input used for the demo.
3. Confirm that the same cached input reproduces the same event ordering.
4. Test with both active satellites and debris groups rather than only the active group.
5. Add explicit API/source/freshness labels to screenshots used in the PPT.

## Medium priority

1. Add ECI/TEME → ITRF/ECEF correction with Earth orientation data if time allows.
2. Improve conjunction candidate screening to reduce false negatives from coarse time steps.
3. Add covariance-aware inputs if a suitable public source is available.
4. Add object-type classification: active payload, debris, rocket body, unknown.

## Do not spend hackathon time on

- Full maneuver optimization
- Autonomous collision-avoidance commands
- A black-box ML model for "collision probability"
- A massive production cloud deployment
- Decorative 3D effects that do not improve the analysis workflow
