# Aurora HE-1 Phase 1 generated baseline

Status: **PRELIMINARY / NOT FOR CONSTRUCTION**

All values below are model outputs from `config/he1_baseline.json`; they are not flight-test results.

## Geometry

- Span: 23.000 m
- Area: 18.000 m²
- Aspect ratio: 29.389
- Root chord: 1.0576 m
- Tip chord: 0.5076 m
- MAC: 0.8148 m

## Reference mass / CG

- Empty mass: 37.50 kg
- Reference gross mass: 110.00 kg
- Gross CG: 2.886 m from nose datum = 22.8% MAC

## Aerodynamics / propulsion

- Clean stall estimate: 7.82 m/s (28.2 km/h)
- Design cruise: 9.50 m/s (34.2 km/h)
- Cruise CL: 1.084
- Cruise drag: 31.68 N
- Cruise L/D: 34.05
- Aerodynamic power: 300.9 W
- Required prop shaft power: 342.0 W
- Battery input at 130 W human input: 275.9 W
- 1-pack supported endurance estimate: 1.36 h
- 1-pack still-air supported range estimate: 46.4 km

## Boost finding

At the current 500 W battery-input boost assumption and 130 W pilot input, the simple excess-power estimate at design cruise is only **0.144 m/s (28 ft/min)**.

## Unverified assumptions

- CD0 = 0.0180
- Oswald efficiency = 0.92
- clean CLmax = 1.60
- propulsive efficiency = 0.88
- motor/controller efficiency = 0.82
- final drive efficiency = 0.96

These must be replaced progressively with XFOIL/VSPAERO, structural, bench, and physical-test evidence.
