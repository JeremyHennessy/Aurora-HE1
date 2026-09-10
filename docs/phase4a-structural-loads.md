# Phase 4A — preliminary structural loads and bracing demand

**Status: PRELIMINARY / NOT FOR CONSTRUCTION OR FLIGHT CLEARANCE**

Phase 4A turns the current verified VSPAERO wing load shape into structural **demand**. It does not claim that any spar, brace, fitting, panel joint or laminate is adequate.

## Source hierarchy

The geometry and aerodynamic load shape come from the current digital baseline and the Phase 3C/OpenVSP toolchain. A prior PDR blueprint is used only for structural-concept inputs that do not conflict with the current digital baseline:

- primary spar at 32% chord;
- rear member at 70% chord;
- panel joints at semispan y = 1.50, 5.25 and 8.75 m;
- lower brace station at y = 5.25 m;
- preliminary +2.5g positive and -1.0g negative load cases;
- illustrative 60% half-wing vertical brace share;
- illustrative brace angle 14.9 degrees;
- 1.5 ultimate/limit multiplier used by the old PDR brace example.

The PDR's older global geometry, CG, dihedral, pod packaging and force results are **not** imported as authoritative data. Phase 4A recomputes the force and moment demand from the current model.

## Aerodynamic load shape

A dedicated OpenVSP 3.51.3 / VSPAERO thin-surface wing-only run evaluates 4 and 6 degrees angle of attack. For each positive-semispan vortex strip, Phase 4A forms a vertical-load weight from:

`Cz * dArea * (V/Vref)^2`

The weights are normalized to exactly one half-wing resultant. This makes the spanwise distribution independent of VSPAERO's arbitrary batch reference speed. The normalized shape is then scaled to the selected load factor and the current 110 kg reference gross mass.

The 4-degree and 6-degree cases are a **shape sensitivity check**, not a maneuver-envelope solution. The higher root-moment shape is used for structural demand.

## Beam demand

For a cut at semispan station `y`, the script integrates all outboard normalized loads to recover:

- vertical shear;
- bending moment;
- idealized cap axial force `|M| / h`, using the PDR-derived screening depth `h = 0.125 chord`.

Demand is reported at:

- root y = 0;
- panel joint y = 1.50 m;
- brace/panel joint y = 5.25 m;
- outer panel joint y = 8.75 m;
- tip y = 11.50 m.

The cap-area table divides cap force by 200, 300 and 500 MPa solely as a sensitivity calculation. Those values are not material allowables and do not include compression buckling, laminate knockdowns, joints, bondlines, fatigue, damage tolerance or crippling.

## Illustrative brace load path

For the old PDR positive-limit comparison only, the brace is imposed as a downward point reaction at y = 5.25 m equal to 60% of the positive half-wing resultant. Its axial tension is reconstructed from the provisional 14.9-degree brace angle.

That model intentionally reproduces the old PDR's ~3.1 kN limit / ~4.7 kN ultimate brace-demand scale, but does **not** solve brace load share from elastic compatibility. Under the PDR negative-load concept the lower tension brace is unloaded and the spar carries the negative wing load.

## Validation gates

CI rejects Phase 4A if:

- the OpenVSP main-wing geometry drifts from the current baseline;
- the 4/6-degree normalized span-loads do not close to unity;
- the two load shapes change root-moment leverage by more than 3%;
- +2.5g cantilever root moment leaves a broad 5–8 kN·m plausibility window;
- the illustrative brace no longer reduces root bending;
- the reconstructed PDR brace tension differs from 3.1 kN by more than 5%;
- the negative case incorrectly loads the lower tension brace;
- any demand or sensitivity value is non-finite.

## Deferred to Phase 4B+

Phase 4A does not establish:

- carbon grade or laminate schedule;
- spar cap/web thickness;
- local panel buckling;
- brace material or diameter;
- brace fitting geometry;
- carry-through or panel-joint pin sizing;
- torsion-box stiffness;
- aeroelastic twist/divergence;
- flutter margin;
- gust envelope;
- landing/ground loads;
- control-surface hinge loads;
- wing self-mass inertial relief;
- fatigue or damage tolerance.

The next structural stage should use the Phase 4A demand distributions to trade spar/brace stiffness and mass, then couple predicted deflection/twist back into the aerodynamic model.
