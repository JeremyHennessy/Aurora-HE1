from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aurora_he1.aero import aero_point
from aurora_he1.config import load_config
from aurora_he1.geometry import solve_trapezoidal_wing
from aurora_he1.model import evaluate
from aurora_he1.propulsion import cruise_power_split


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "config" / "he1_baseline.json"))
    parser.add_argument("--out", default=str(ROOT / "outputs"))
    args = parser.parse_args()
    cfg = load_config(args.config)
    result = evaluate(cfg)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "design_summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    with (out / "airfoil_stations.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["eta", "semi_span_y_m", "chord_m", "airfoil", "twist_deg", "reynolds"])
        writer.writeheader(); writer.writerows(result["airfoil_stations"])
    with (out / "mass_budget.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "mass_kg", "x_m"])
        writer.writeheader(); writer.writerows(cfg["mass"]["items"])
    env, ac, pc = cfg["environment"], cfg["aero"], cfg["propulsion"]
    wing = solve_trapezoidal_wing(cfg["geometry"]["wing"]["span_m"], cfg["geometry"]["wing"]["area_m2"], cfg["geometry"]["wing"]["taper_ratio"])
    weight_n = result["gross_mass_kg"] * env["gravity_m_s2"]
    with (out / "power_curve.csv").open("w", newline="", encoding="utf-8") as f:
        fields = ["speed_m_s", "speed_km_h", "cl", "drag_n", "ld", "aero_power_w", "prop_shaft_w", "battery_input_w", "flyable_clean"]
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader()
        for i in range(75, 131, 2):
            speed = i / 10.0
            ap = aero_point(weight_n=weight_n, rho_kg_m3=env["density_kg_m3"], speed_m_s=speed, wing=wing, cd0=ac["cd0_profile_plus_parasite"], oswald_efficiency=ac["oswald_efficiency"])
            split = cruise_power_split(aerodynamic_power_w=ap.aerodynamic_power_w, propulsive_efficiency=ac["propulsive_efficiency"], human_input_w=pc["human_cruise_input_w"], final_drive_efficiency=pc["final_drive_efficiency"], motor_controller_efficiency=pc["motor_controller_efficiency"])
            writer.writerow({"speed_m_s": f"{speed:.2f}", "speed_km_h": f"{speed*3.6:.2f}", "cl": f"{ap.cl:.5f}", "drag_n": f"{ap.drag_n:.3f}", "ld": f"{ap.lift_to_drag:.3f}", "aero_power_w": f"{ap.aerodynamic_power_w:.2f}", "prop_shaft_w": f"{split.prop_shaft_required_w:.2f}", "battery_input_w": f"{split.battery_input_w:.2f}", "flyable_clean": ap.cl <= ac["cl_max_clean"]})
    report = f"""# Aurora HE-1 Phase 1 generated baseline\n\nStatus: **{cfg['meta']['status']}**\n\nAll values below are model outputs from `config/he1_baseline.json`; they are not flight-test results.\n\n## Geometry\n\n- Span: {wing.span_m:.3f} m\n- Area: {wing.area_m2:.3f} m²\n- Aspect ratio: {wing.aspect_ratio:.3f}\n- Root chord: {wing.root_chord_m:.4f} m\n- Tip chord: {wing.tip_chord_m:.4f} m\n- MAC: {wing.mean_aerodynamic_chord_m:.4f} m\n\n## Reference mass / CG\n\n- Empty mass: {result['empty_mass_kg']:.2f} kg\n- Reference gross mass: {result['gross_mass_kg']:.2f} kg\n- Gross CG: {result['gross_cg_x_m']:.3f} m from nose datum = {result['gross_cg_fraction_mac']*100:.1f}% MAC\n\n## Aerodynamics / propulsion\n\n- Clean stall estimate: {result['stall_speed_m_s']:.2f} m/s ({result['stall_speed_km_h']:.1f} km/h)\n- Design cruise: {result['cruise']['speed_m_s']:.2f} m/s ({result['cruise']['speed_m_s']*3.6:.1f} km/h)\n- Cruise CL: {result['cruise']['cl']:.3f}\n- Cruise drag: {result['cruise']['drag_n']:.2f} N\n- Cruise L/D: {result['cruise']['lift_to_drag']:.2f}\n- Aerodynamic power: {result['cruise']['aerodynamic_power_w']:.1f} W\n- Required prop shaft power: {result['power_split']['prop_shaft_required_w']:.1f} W\n- Battery input at {pc['human_cruise_input_w']:.0f} W human input: {result['power_split']['battery_input_w']:.1f} W\n- 1-pack supported endurance estimate: {result['battery_endurance_h']:.2f} h\n- 1-pack still-air supported range estimate: {result['still_air_supported_range_km']:.1f} km\n\n## Boost finding\n\nAt the current 500 W battery-input boost assumption and {pc['human_cruise_input_w']:.0f} W pilot input, the simple excess-power estimate at design cruise is only **{result['boost_climb_rate_estimate_m_s']:.3f} m/s ({result['boost_climb_rate_estimate_ft_min']:.0f} ft/min)**.\n\n## Unverified assumptions\n\n- CD0 = {ac['cd0_profile_plus_parasite']:.4f}\n- Oswald efficiency = {ac['oswald_efficiency']:.2f}\n- clean CLmax = {ac['cl_max_clean']:.2f}\n- propulsive efficiency = {ac['propulsive_efficiency']:.2f}\n- motor/controller efficiency = {pc['motor_controller_efficiency']:.2f}\n- final drive efficiency = {pc['final_drive_efficiency']:.2f}\n\nThese must be replaced progressively with XFOIL/VSPAERO, structural, bench, and physical-test evidence.\n"""
    (out / "phase1_report.md").write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
