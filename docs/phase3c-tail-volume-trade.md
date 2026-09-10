# Phase 3C — longitudinal stability validation and tail-volume trade

Status: **computational engineering trade / not for construction or flight clearance**.

## Purpose

Phase 3B showed a large longitudinal static margin for every tested horizontal-tail planform while holding the baseline 1.77 m² tail area and 8.85 m aerodynamic-center station fixed. Before changing the aircraft around that result, Phase 3C performs independent internal sanity checks on the VSPAERO moment reference and mesh sensitivity, then varies horizontal-tail volume through area and tail arm.

No Phase 3C case changes `config/he1_baseline.json` and no case is promoted automatically.

## Sanity anchors

Five cases establish whether the Phase 3B result is suitable for sizing work:

1. **WING_ONLY** — the Phase 3A main wing at the baseline gross CG with no horizontal tail. This exposes the main-wing-only neutral point and static-margin contribution.
2. **REF_BASE** — exact Phase 3B `HT35T70` geometry: 1.77 m², AR 3.5, taper 0.70, tail AC x = 8.85 m. It must reproduce the accepted Phase 3B static margin and neutral point.
3. **REF_CG_FWD** — exact REF_BASE geometry with the VSPAERO moment reference moved forward by 0.10 wing MAC.
4. **REF_CG_AFT** — exact REF_BASE geometry with the moment reference moved aft by 0.10 wing MAC.
5. **REF_FINE** — exact REF_BASE geometry and CG with higher VSPAERO surface tessellation.

For an unchanged aerodynamic geometry, changing only Xcg should change static margin by the opposite CG shift while leaving the reconstructed neutral point essentially unchanged. This is an explicit sign/reference-convention test, not an assumed property.

The fine-mesh case must also remain close to REF_BASE. If either test fails, the tail-volume trade is not accepted even if its numerical cases complete.

## Tail-volume grid

The trade retains one representative Phase 3B planform so that area and arm are the variables rather than another simultaneous planform sweep:

- aspect ratio = 3.5;
- taper ratio = 0.70;
- zero leading-edge sweep;
- zero dihedral;
- zero tail incidence;
- z = 0 m reference position;
- symmetric thin VLM section.

Horizontal-tail area:

- 0.40 m²
- 0.60 m²
- 0.80 m²
- 1.00 m²
- 1.20 m²

Tail aerodynamic-center x:

- 7.00 m
- 8.00 m
- 8.85 m

This creates 15 grid cases spanning much lower horizontal-tail volume than the current baseline-area/arm combination. The exact 1.77 m² / 8.85 m Phase 3B geometry remains present separately as the validation reference.

## VSPAERO convention

All cases preserve the Phase 3A/3B main-wing geometry and analysis convention:

- OpenVSP 3.51.3;
- VSPAERO vortex-lattice thin-surface analysis;
- Sref = 18.0 m²;
- bref = 23.0 m;
- cref = baseline main-wing MAC;
- alpha sweep = -2° to +6°, five points;
- Mach = 0.03;
- native `.polar` output as coefficient evidence.

Static margin is reconstructed from the fitted pitching-moment slope:

`static margin = -dCm/dCL`

and neutral-point location is reported as:

`x_NP = x_CG + static_margin * MAC`.

## Acceptance boundary

CI rejects Phase 3C for solver/data/model defects such as:

- main-wing or generated tail geometry drift;
- missing or non-finite native VSPAERO coefficients;
- failure to reproduce the accepted Phase 3B reference;
- neutral-point movement beyond tolerance when only Xcg changes;
- static-margin shift inconsistent with the imposed Xcg movement;
- excessive reference-case mesh sensitivity;
- grossly implausible grid output.

The provisional 8–20% MAC review band is **not** a pass/fail gate. A valid analysis is allowed to show zero, one, or many cases in that region.

## What Phase 3C still does not establish

Phase 3C does not establish:

- a final horizontal-tail design;
- trim at cruise, climb or low speed;
- elevator size, deflection, authority or hinge moment;
- vertical-tail/rudder sizing;
- lateral-directional stability;
- fuselage aerodynamic interference;
- propeller slipstream effects;
- viscous whole-aircraft drag;
- structural or aeroelastic adequacy;
- flutter clearance;
- airworthiness or flight-test clearance.

If the validation anchors are sound and the grid locates a useful stability region, the next longitudinal-aerodynamic step is an explicit elevator/trim study on a small set of candidate tail-volume configurations. Structural mass and deformation work should proceed in parallel before any tail is promoted to a new baseline.
