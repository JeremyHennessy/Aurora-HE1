# Phase 2 — viscous airfoil and propeller analysis

Status: **validated computational pipeline / candidate engineering result**. Not a construction or flight-clearance baseline.

This phase replaces two Phase 1 placeholders with higher-fidelity computational evidence:

1. DAE wing/propeller sections are retrieved from Mark Drela's MIT Human Powered Aircraft archive and analyzed with XFOIL 6.996.
2. DAE51 propeller polars feed a blade-element/momentum (BEM) solver at the HE-1 design condition.

## Source and solver provenance

Authoritative coordinate index: https://web.mit.edu/drela/Public/web/hpa/airfoils/

The downloaded DAE11/21/31/41/51 files are SHA-256 pinned in `config/airfoil_sources.json`; CI fails if the remote content changes.

The first implementation used Ubuntu's packaged XFOIL 6.99 and exposed repeatable SIGFPE failures during otherwise valid low-Re viscous solves. That executable is not used by the accepted Phase 2 pipeline.

The accepted workflow uses `webxfoil-wasm@0.1.1`, a headless build of XFOIL 6.996. CI verifies the wrapper's documented upstream XFOIL source SHA before analysis. Each `(airfoil, Reynolds, alpha)` case is solved independently so a failed point cannot contaminate subsequent solver state.

MIT identifies the original design Reynolds numbers as approximately DAE11 500k, DAE21 375k, DAE31 250k, DAE41 150k and DAE51 150k. HE-1 evaluates each wing section over its own estimated operating envelope, while DAE51 is evaluated from Re 75k to 400k for the propeller.

## Accepted polar coverage

The successful exact-head Phase 2 run generated **22 viscous polar cases**. Every case met the minimum operating-coverage gate of at least -2 to +7 degrees and at least 12 converged points.

Representative best observed section L/D values from the computational polars:

| Section | Reynolds range evaluated | Best observed section L/D range |
| --- | ---: | ---: |
| DAE11 | 500k–700k | ~139–159 |
| DAE21 | 350k–600k | ~118–147 |
| DAE31 | 250k–500k | ~104–140 |
| DAE41 | 200k–400k | ~76–97 |
| DAE51 | 75k–400k | ~53–113 |

These are two-dimensional XFOIL section results, not aircraft or propeller L/D values. The DAE51 result is particularly important: profile performance degrades materially at the propeller's low local Reynolds numbers, so high-Re propeller assumptions are not acceptable for HE-1.

## BEM candidate result

Phase 1 assumed propulsive efficiency of **0.88**. The current DAE51/XFOIL-driven seed BEM solution at the 2.85 m, 130 rpm, 9.5 m/s design condition gives:

- required aircraft cruise thrust: ~31.68 N;
- BEM seed thrust: ~31.88 N;
- BEM shaft power: ~335.15 W;
- calculated propulsive efficiency: **~0.9037**;
- torque: ~24.62 N·m;
- advance ratio: ~1.538;
- disk loading: ~5.00 N/m²;
- local blade Reynolds range: ~102k–168k;
- seed target section alpha: 6.5°;
- seed chord scale: 1.2.

The local BEM Reynolds range is inside the generated DAE51 polar envelope, so the result does not depend on Reynolds extrapolation outside the analyzed range.

Using the calculated BEM efficiency in the system model, without changing the Phase 1 baseline configuration, gives the following **candidate** values:

| Quantity | Phase 1 assumption | Phase 2 candidate |
| --- | ---: | ---: |
| Propulsive efficiency | 0.880 | **0.9037** |
| Prop-shaft cruise requirement | ~342 W | **~333 W** |
| Cruise battery input | ~276 W | **~265 W** |
| One-pack still-air range | ~46.4 km | **~48.4 km** |
| 500 W battery-input boost climb | ~28 ft/min | **~30.6 ft/min** |

The propulsion improvement is modest and physically plausible. Critically, it does **not** resolve the climb-power limitation identified in Phase 1.

## Baseline promotion rule

This PR intentionally does not edit `config/he1_baseline.json` to replace the 0.88 Phase 1 assumption. The ~0.9037 BEM result remains a candidate until higher-order propeller optimization and subsequent physical propulsion testing provide sufficient evidence for baseline promotion.

## What this phase does not establish

XFOIL/BEM do not validate:

- three-dimensional blade losses beyond the implemented BEM corrections;
- final minimum-induced-loss/Larrabee circulation distribution;
- blade aeroelastic deformation;
- propeller structural integrity or overspeed margin;
- built-surface roughness and manufacturing tolerances;
- hub and bearing losses;
- motor/controller thermal behavior;
- aircraft three-dimensional lift distribution or stability;
- flight safety or airworthiness.

The generated blade geometry is a **seed geometry** for subsequent circulation optimization and physical testing, not a construction drawing.
