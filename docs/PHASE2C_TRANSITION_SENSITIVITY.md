# Phase 2C — DAE51 transition / surface-disturbance sensitivity

Status: **computational sensitivity analysis / not for construction or flight clearance**.

## Objective

Phase 2 and Phase 2B use clean XFOIL section data. Phase 2C asks a narrower question before those results are trusted further:

> How sensitive is the existing Phase 2 propeller seed to earlier boundary-layer transition and severe surface disturbance?

This phase does not change `config/he1_baseline.json` and does not redesign the blade.

## Why these are proxies rather than literal roughness predictions

XFOIL transition parameters can represent changed amplification/transition assumptions and can force transition at a chosen chord position. They do **not**, in this workflow, establish a calibrated relationship between a physical roughness height, bug contamination, rain, tape edge, manufacturing waviness, or surface finish and the resulting aerodynamic penalty.

Therefore the cases are deliberately named and interpreted as transition / contamination proxies:

- clean natural transition, Ncrit 9;
- moderately disturbed natural transition, Ncrit 6;
- strongly disturbed natural transition, Ncrit 3;
- transition forced at 10% chord on both surfaces;
- transition forced at 5% chord on both surfaces.

No case should be read as “this corresponds to X microns RMS roughness.” Physical coupon/section testing would be required for that claim.

## Airfoil matrix

The analysis is limited to **DAE51**, because the immediate objective is propeller sensitivity. The Reynolds grid is:

- 75,000
- 100,000
- 150,000
- 200,000
- 250,000

This brackets the verified Phase 2 reference blade station Reynolds range at the 9.5 m/s cruise point.

Each case is solved with isolated XFOIL alpha points from -2 to +8 degrees in 0.5-degree increments, with convergence and minimum alpha-coverage gates.

## Fixed-blade propagation

All surface-disturbance cases use the exact same Phase 2 seed geometry:

- diameter: 2.85 m
- two blades
- design speed: 9.5 m/s
- design RPM: 130 rpm
- target design alpha: 6.5 degrees
- chord scale: 1.2

The blade is **not reoptimized** after the polar is degraded. That is intentional: reoptimization would partially hide the sensitivity of the design we already have.

For each case, the analysis reports two things:

1. **Fixed 130 rpm behavior** — thrust, torque, shaft power, efficiency, Reynolds and section-alpha envelope.
2. **Thrust-recovery sweep** — the same blade is tested from 110 to 190 rpm. If the required Phase 1/2 cruise drag can be recovered inside the generated polar envelope, the lowest-shaft-power recovery point is selected.

The recovery point is then propagated through the unchanged human/electric drivetrain equations to estimate battery input, endurance and still-air range consequences.

## Acceptance boundary

Phase 2C may show that the current clean-surface propeller result is robust, moderately sensitive, or highly sensitive. It does not establish:

- a real manufactured blade surface-loss factor;
- contamination/rain/insect behavior;
- static thrust;
- propeller strength or overspeed margin;
- aeroelastic stability;
- drivetrain durability or thermal endurance;
- airworthiness or flight safety.

The purpose is to expose sensitivity before advancing to higher-fidelity whole-aircraft work, not to promote a new baseline value automatically.
