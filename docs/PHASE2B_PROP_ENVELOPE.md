# Phase 2B — propeller family and operating-envelope trade

Status: **computational trade / candidate engineering evidence**. Not for construction or flight clearance.

## Why this increment exists

Phase 2 established that a DAE51/XFOIL-driven BEM seed at the current 2.85 m / 130 rpm / 9.5 m/s reference condition can produce the required cruise thrust with roughly 0.90 computed propulsive efficiency. That is useful but it is still only one operating point.

The simulation roadmap requires a broader 2.5–3.2 m propeller family, 8–11 m/s flight conditions, Reynolds-dependent section data, RPM sensitivity, and explicit separation of cruise from low-speed/static behavior. Phase 2B implements that trade while preserving `config/he1_baseline.json` unchanged.

## Installation constraint discovered before optimization

The present baseline has:

- propeller shaft center height: **1.75 m**
- minimum target ground clearance: **0.30 m**

Therefore the largest propeller that can meet that target without changing the airframe or landing-gear geometry is:

`Dmax = 2 × (1.75 - 0.30) = 2.90 m`

The 3.0 m and 3.2 m family members are still evaluated aerodynamically, but they are automatically marked installation-infeasible under the current geometry. They cannot be selected as the preferred design unless the installation geometry is changed in a later, explicit design decision.

## Trade grid

Design-family grid:

- diameter: 2.50, 2.70, 2.85, 2.90, 3.00, 3.20 m
- design RPM: 110, 120, 130, 140, 150 rpm
- design speed: 9.5 m/s
- required thrust: the unchanged Phase 1 analytical aircraft drag at the design condition
- trusted DAE51 Reynolds range: 75k–400k
- trusted angle-of-attack range for acceptance: -2 to +7 degrees
- shaft-power band used as a design gate: 250–800 W

For the selected seed geometry, off-design matching is then attempted at:

- flight speed: 8.0–11.0 m/s in 0.5 m/s increments
- RPM: 90–180 rpm in 10 rpm increments

At each flight speed the aircraft drag requirement is recomputed from the same unchanged analytical aircraft model, and the lowest-shaft-power RPM that meets thrust while remaining inside the trusted DAE51 computational envelope is selected.

## New diagnostic gates

The BEM result now reports the final blade-station Reynolds and section-angle-of-attack extrema. This prevents the family trade from silently accepting off-design points that depend on extrapolation beyond the trusted XFOIL region.

Candidate selection requires all of the following:

1. required design thrust is met;
2. present ground-clearance target is met;
3. final station Reynolds numbers remain within the trusted DAE51 range;
4. final station section angles remain within the trusted acceptance range;
5. design shaft power remains within the 250–800 W trade band;
6. computed propulsive efficiency is positive and no greater than 1.

## Static and takeoff boundary

The current BEM induction formulation is a forward-flight formulation and is singular at exactly zero axial speed. Phase 2B therefore **does not report static thrust**. The workflow records this explicitly rather than fabricating a static result.

A 5 m/s propeller-only diagnostic is retained as a low-speed check, but it is not treated as an aircraft level-flight requirement because it is below the present analytical stall speed.

A later propulsion increment must add either a dedicated static BEM formulation or a validated actuator-disk/static initialization before static thrust can become a trusted design result.

## Interpretation boundary

This phase narrows the propeller diameter/RPM operating space. It still does not establish:

- a final Larrabee/minimum-induced-loss circulation distribution;
- blade structural sizing, stiffness, overspeed margin, or aeroelastic stability;
- actual roughness/manufacturing losses;
- hub, bearing, chain/belt, or gearbox losses;
- motor/controller thermal endurance;
- commercial availability of any theoretical sprocket tooth count;
- airworthiness or flight safety.

`config/he1_baseline.json` remains unchanged. Any future baseline promotion requires separate evidence and an explicit design decision.
