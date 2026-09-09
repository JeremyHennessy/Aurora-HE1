# Aurora HE-1 design baseline

**Status: PRELIMINARY / NOT FOR CONSTRUCTION**

The repository, not a rendered blueprint, is the authoritative source for Aurora HE-1 numerical design data.

## Phase 1 reference candidate

The initial candidate is intentionally not an approved optimum:

- 23.0 m span
- 18.0 m² wing area
- taper ratio 0.48
- 2.85 m two-blade propeller
- 9.5 m/s design cruise
- 37.5 kg modelled empty mass including one battery
- 110.0 kg reference gross mass using a 72.5 kg reference pilot/personal-gear assumption
- 48 V / 468 Wh standard battery
- torque-sensing mid-drive architecture

The reference pilot mass is a design assumption only. It is not a statement about any intended pilot.

## Evidence hierarchy

1. Measured physical-test data
2. Validated high-fidelity simulation
3. Published component data
4. Preliminary analytical model
5. Design target

Every model output should be traceable to one of these levels. Phase 1 is primarily levels 3-5.

## Current high-impact uncertainties

- low-Re airfoil polars with real surface roughness
- whole-aircraft parasite drag / CD0
- propeller BEM design and efficiency at J ~1.54
- motor/controller efficiency at sustained aircraft loads
- structural wing and brace mass
- wing torsional stiffness and aeroelastic deformation
- panel joint mass and stiffness
- validated neutral point and control derivatives
- landing/takeoff performance
- pilot mission power and ergonomic envelope

No item in this repository should be interpreted as establishing airworthiness.
