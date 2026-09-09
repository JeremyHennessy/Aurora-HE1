from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aurora_he1.aero import aero_point, stall_speed
from aurora_he1.config import load_config
from aurora_he1.geometry import solve_trapezoidal_wing
from aurora_he1.model import evaluate


def main() -> int:
    cfg = load_config(ROOT / "config" / "he1_baseline.json")
    base = evaluate(cfg)
    env, ac = cfg["environment"], cfg["aero"]
    weight = base["gross_mass_kg"] * env["gravity_m_s2"]
    out = ROOT / "outputs" / "aero_trade_study.csv"
    out.parent.mkdir(exist_ok=True)
    rows = []
    for span_x2 in range(40, 51):
        span = span_x2 / 2.0
        for area in range(16, 21):
            wing = solve_trapezoidal_wing(span, float(area), cfg["geometry"]["wing"]["taper_ratio"])
            vs = stall_speed(weight, env["density_kg_m3"], wing.area_m2, ac["cl_max_clean"])
            for speed_x2 in range(17, 23):
                speed = speed_x2 / 2.0
                ap = aero_point(weight_n=weight, rho_kg_m3=env["density_kg_m3"], speed_m_s=speed, wing=wing, cd0=ac["cd0_profile_plus_parasite"], oswald_efficiency=ac["oswald_efficiency"])
                rows.append({"span_m": span, "area_m2": area, "aspect_ratio": wing.aspect_ratio, "speed_m_s": speed, "stall_speed_m_s": vs, "stall_margin_ratio": speed / vs, "drag_n": ap.drag_n, "ld": ap.lift_to_drag, "aero_power_w": ap.aerodynamic_power_w, "prop_shaft_w": ap.aerodynamic_power_w / ac["propulsive_efficiency"], "warning": "AERODYNAMIC-ONLY: fixed gross mass/CD0; no structural-mass or cost coupling"})
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys())); writer.writeheader(); writer.writerows(rows)
    print(f"wrote {len(rows)} aerodynamic trade points to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
