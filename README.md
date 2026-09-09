# Aurora HE-1 Digital Twin

Parametric preliminary engineering model for **Aurora HE-1**, a practical human-electric experimental aircraft.

> **PRELIMINARY / NOT FOR CONSTRUCTION.** This repository is an analysis and design-control environment. It is not a certified aircraft design and does not replace structural, aeroelastic, propeller, battery, ground, or flight testing.

## Phase 1 scope

The first build establishes:

- one authoritative JSON design baseline;
- deterministic trapezoidal-wing geometry;
- Reynolds-number station table;
- analytical drag / power / stall model;
- human-electric power split and battery endurance model;
- mass and longitudinal CG closure;
- propeller gearing / advance-ratio checks;
- a preliminary excess-power climb sanity check;
- aerodynamic-only parameter sweeps;
- automated regression and consistency gates in GitHub Actions;
- generated CSV/JSON/Markdown engineering outputs.

This is deliberately lower fidelity than XFOIL/VSPAERO/FEA. The purpose is to establish consistent inputs and catch conceptual errors before higher-fidelity solvers are integrated.

## Current reference candidate

See [`DESIGN_BASELINE.md`](DESIGN_BASELINE.md) and [`config/he1_baseline.json`](config/he1_baseline.json).

The 23 m configuration is a **candidate baseline**, not an approved optimum.

## Run locally

Requires Python 3.11+ and no third-party packages.

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python scripts/check_design.py
PYTHONPATH=src python scripts/generate_outputs.py
PYTHONPATH=src python scripts/run_trade_study.py
```

## Generated outputs

- `outputs/design_summary.json`
- `outputs/phase1_report.md`
- `outputs/power_curve.csv`
- `outputs/airfoil_stations.csv`
- `outputs/mass_budget.csv`
- `outputs/aero_trade_study.csv`

CI regenerates tracked baseline outputs and fails if they disagree with the model.

## Important current finding

The analytical model does **not** support the earlier conceptual 2-3 m/s climb estimate from a 500 W electrical boost. At the current reference gross mass and assumed efficiencies, the excess-power estimate is only a few tenths of a metre per second. This is intentionally preserved as a design finding and makes propulsion sizing a Phase 2 priority.

## Next simulation layers

1. Import candidate DAE airfoils and run XFOIL polar matrices at the actual HE-1 Reynolds range.
2. Build the parametric geometry in OpenVSP and run VSPAERO lift/stability sweeps.
3. Add a blade-element/momentum propeller solver and optimize diameter/chord/twist/RPM.
4. Couple structural beam/bracing mass and deflection to the aerodynamic trade study.
5. Add longitudinal and lateral-directional flight-dynamics models.
6. Replace assumed efficiencies with measured drivetrain/battery bench data.

See `docs/SIMULATION_ROADMAP.md`.
