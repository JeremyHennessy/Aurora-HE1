# Phase 3A — OpenVSP / VSPAERO main-wing validation

Status: **computational engineering analysis / not for construction or flight clearance**.

## Objective

Phase 3A moves the AURORA HE-1 from the analytical finite-wing model into an independently generated OpenVSP/VSPAERO representation, while refusing to fabricate geometry that is not yet specified.

The first accepted Phase 3 model is therefore **main-wing only**.

It answers:

- Does a VSP geometry generated from `config/he1_baseline.json` reproduce the tracked span, area and chords?
- Does VSPAERO produce a physically plausible lift curve for the tracked planform, dihedral, incidence and twist distribution?
- Is the three-dimensional induced drag consistent with the analytical finite-wing model within a deliberately broad validation tolerance?

It does **not** yet answer whole-aircraft static stability or control authority.

## Why the tail is not modeled yet

The current baseline tracks:

- horizontal-tail area;
- vertical-tail area;
- tail aerodynamic-center x-location.

It does not yet define authoritative:

- horizontal-tail span/aspect ratio;
- root/tip chords or taper;
- sweep;
- dihedral;
- incidence;
- vertical-tail planform;
- elevator/rudder geometry;
- control hinge locations.

Creating one arbitrary tail planform would produce precise-looking neutral-point and control-derivative results that are actually dominated by an untracked assumption. Phase 3A therefore excludes it.

## Geometry generation

The VSP model is generated on every run from the baseline rather than storing a hand-edited master model.

The tracked trapezoid is divided at eta = 0, 0.25, 0.50, 0.75 and 1.00. Chord is derived from the same trapezoidal-wing equations used by the analytical model. The four VSP wing sections preserve:

- 23.0 m total span;
- 18.0 m² planform area;
- 0.48 taper ratio;
- 3.5° dihedral;
- 1.5° incidence;
- the tracked twist at each quarter-span station;
- zero leading-edge sweep implied by the currently aligned leading-edge baseline.

VSPAERO is run in vortex-lattice mode with symmetric thin section geometry. This is intentional. Phase 2 owns viscous DAE airfoil drag and low-Re section behavior; Phase 3A is isolating 3-D lift distribution and induced drag rather than mixing a second viscous model into the comparison.

## Toolchain

OpenVSP is pinned to **3.51.3** using the official Ubuntu 24.04 package. CI records the reported OpenVSP version and rejects an unexpected version.

The generated `.vsp3`, generated `.vspscript`, solver log and parsed VSPAERO results are retained as workflow artifacts.

## Phase 3A acceptance gates

The run is rejected if:

- OpenVSP's reported span, area, root chord or tip chord differs from the baseline by more than 0.2%;
- the alpha sweep does not return the requested number of points;
- induced drag is negative or non-finite;
- CL is not monotonic through the core -2° to +6° range;
- the lift-curve slope is non-positive;
- VSPAERO induced drag at the comparison point differs by more than 30% from the analytical finite-wing estimate using e=0.92;
- implied span efficiency is physically implausible.

The 30% induced-drag tolerance is intentionally broad for the first independent model. Passing it is a consistency check, not model validation against flight data.

## Next after Phase 3A

Phase 3B should define a **provisional-but-explicit tail geometry family** before calculating neutral point or static margin. That work should sweep plausible horizontal/vertical-tail aspect ratios and planforms subject to the already tracked area and aerodynamic-center constraints, then select a candidate only after stability, control authority, structure and transport implications are evaluated.

Only after a tail candidate is explicitly promoted should VSPAERO control surfaces be added for elevator, rudder and aileron derivative sweeps.
