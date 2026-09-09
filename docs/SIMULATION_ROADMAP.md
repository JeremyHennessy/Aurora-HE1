# Simulation roadmap

## Phase 1 — deterministic analytical baseline

Implemented in this branch. Objective: eliminate inconsistent geometry/specification values and create regression gates.

## Phase 2 — viscous airfoil and propeller fidelity

### Airfoil matrix

- acquire authoritative DAE11/21/31/41 coordinate files;
- XFOIL sweeps over approximately Re 300k-750k;
- alpha sweeps through pre-stall and post-linear regions where solver convergence permits;
- transition / Ncrit sensitivity;
- forced-transition and roughness cases;
- export CL/CD/CM polar database;
- select/blend spanwise sections based on actual local Re and lift loading.

### Propeller BEM

- implement blade-element/momentum solver;
- optimize two-blade 2.5-3.2 m family;
- design conditions 8-11 m/s and 250-800 W shaft power;
- include Reynolds-dependent section polars;
- report chord, twist, thrust, torque, efficiency, advance ratio and sensitivity to RPM;
- flag static/takeoff conditions separately from cruise.

## Phase 3 — OpenVSP / VSPAERO

- generate master aircraft geometry from the same config values;
- no manually duplicated blueprint dimensions;
- compute lift distribution and induced drag;
- estimate neutral point, static margin and control derivatives;
- sweep alpha, beta, elevator, rudder and aileron;
- compare VSPAERO induced drag with analytical baseline and investigate deviations.

## Phase 4 — structural / aeroelastic model

- distributed aerodynamic load mapped to wing beam;
- shear and bending moment envelopes;
- carbon-cap / shear-web preliminary sizing;
- external brace load path and preload;
- bending and torsional deflection;
- iterate aerodynamic loading on deformed geometry;
- panel joints represented explicitly as stiffness/mass elements;
- no final laminate schedule until material coupon data exists.

## Phase 5 — dynamics / mission simulation

- longitudinal linear model;
- lateral-directional linear model;
- control authority and trim envelope;
- gust cases;
- 6-DOF nonlinear integration after derivative quality is adequate;
- mission energy: takeoff, climb, cruise, turns, descent and reserve;
- pilot-power profile and battery state of charge.

## Validation boundary

Simulation can narrow the design and identify contradictions. It cannot establish actual laminate strength, actual joint strength, flutter clearance, real surface drag, real propeller efficiency, motor thermal endurance, battery fault tolerance, or airworthiness. Those require appropriately designed physical testing and regulatory oversight.
