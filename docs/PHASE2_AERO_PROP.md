# Phase 2 — viscous airfoil and propeller analysis

This phase replaces two Phase 1 placeholders with higher-fidelity computational evidence:

1. DAE wing/propeller sections are retrieved from Mark Drela's MIT Human Powered Aircraft archive and analyzed in XFOIL.
2. DAE51 propeller polars feed a blade-element/momentum solver at the HE-1 design condition.

## Source provenance

Authoritative coordinate index: https://web.mit.edu/drela/Public/web/hpa/airfoils/

MIT identifies the original design Reynolds numbers as DAE11 500k, DAE21 375k, DAE31 250k, DAE41 150k and DAE51 150k. HE-1 intentionally evaluates a wider Reynolds envelope because its geometry and cruise speed differ from Daedalus.

## What this phase can establish

- section-polar trends at HE-1 Reynolds numbers;
- whether DAE51 is plausible for the 2.85 m / 130 rpm propeller regime;
- a first calculated propulsive-efficiency estimate rather than the Phase 1 fixed 0.88 assumption;
- initial propeller chord/twist stations that satisfy cruise thrust in BEM;
- revised cruise battery and climb estimates using the calculated propeller efficiency.

## What it does not establish

XFOIL/BEM do not validate three-dimensional blade losses, aeroelastic deformation, propeller structural integrity, surface roughness in the built aircraft, hub losses, motor cooling or flight safety. The BEM geometry is a seed for subsequent Larrabee/circulation optimization and physical test.
