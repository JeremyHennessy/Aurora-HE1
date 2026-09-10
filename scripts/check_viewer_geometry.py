#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path


def require(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(f"VIEWER GEOMETRY VALIDATION FAILED: {message}")


def close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(b)))


def main() -> None:
    baseline = json.loads(Path("config/he1_baseline.json").read_text())
    phase3b = json.loads(Path("config/phase3b_longitudinal_tail.json").read_text())
    geom = json.loads(Path("viewer/data/geometry_fidelity.json").read_text())
    profiles = json.loads(Path("viewer/data/wing_profiles.json").read_text())

    bg = baseline["geometry"]
    w = geom["wing"]
    bw = bg["wing"]

    for key in ("span_m", "area_m2", "taper_ratio", "dihedral_deg", "incidence_deg", "root_le_x_m"):
        require(close(w[key], bw[key]), f"wing {key} differs from baseline: {w[key]} vs {bw[key]}")
    require(close(geom["overall_length_m"], bg["overall_length_m"]), "overall length differs from baseline")
    require(close(geom["horizontal_tail"]["fixed_area_m2"], bg["tail"]["horizontal_area_m2"]), "horizontal-tail area differs from baseline")
    require(close(geom["horizontal_tail"]["fixed_aerodynamic_center_x_m"], bg["tail"]["tail_ac_x_m"]), "tail AC x differs from baseline")
    require(close(geom["vertical_tail"]["area_m2"], bg["tail"]["vertical_area_m2"]), "vertical-tail area differs from baseline")
    require(close(geom["propeller"]["baseline"]["diameter_m"], bg["propeller"]["diameter_m"]), "baseline prop diameter differs")
    require(close(geom["propeller"]["baseline"]["rpm"], bg["propeller"]["design_rpm"]), "baseline prop RPM differs")
    require(close(geom["propeller"]["shaft_center_height_m"], bg["propeller"]["shaft_center_height_m"]), "shaft height differs")
    require(close(geom["mass"]["reference_pilot_cg_x_m"], baseline["mass"]["reference_pilot_cg_x_m"]), "pilot CG x differs")

    root = 2.0 * w["area_m2"] / (w["span_m"] * (1.0 + w["taper_ratio"]))
    tip = root * w["taper_ratio"]
    mac = (2.0 / 3.0) * root * (1.0 + w["taper_ratio"] + w["taper_ratio"] ** 2) / (1.0 + w["taper_ratio"])
    ar = w["span_m"] ** 2 / w["area_m2"]
    require(close(w["root_chord_m"], root), "viewer root chord is not derived from baseline trapezoid")
    require(close(w["tip_chord_m"], tip), "viewer tip chord is not derived from baseline trapezoid")
    require(close(w["mean_aerodynamic_chord_m"], mac), "viewer MAC is not derived from baseline trapezoid")
    require(close(w["aspect_ratio"], ar), "viewer aspect ratio is inconsistent")

    bw_stations = bw["airfoil_stations"]
    gw_stations = w["stations"]
    require(len(bw_stations) == len(gw_stations) == 5, "expected five wing stations")
    for b, g in zip(bw_stations, gw_stations):
        require(close(b["eta"], g["eta"]), f"station eta drift at {g['eta']}")
        require(close(b["twist_deg"], g["twist_deg"]), f"station twist drift at eta {g['eta']}")

    expected = phase3b["horizontal_tail_family"]["candidates"]
    candidates = geom["horizontal_tail"]["candidates"]
    require([c["id"] for c in candidates] == [c["id"] for c in expected], "Phase 3B candidate IDs/order differ")
    area = float(bg["tail"]["horizontal_area_m2"])
    qmac_x = float(bg["tail"]["tail_ac_x_m"])
    for cfg, case in zip(expected, candidates):
        require(close(case["aspect_ratio"], cfg["aspect_ratio"]), f"{case['id']}: AR differs from Phase 3B config")
        require(close(case["taper_ratio"], cfg["taper_ratio"]), f"{case['id']}: taper differs from Phase 3B config")
        span = math.sqrt(area * float(cfg["aspect_ratio"]))
        root = 2.0 * area / (span * (1.0 + float(cfg["taper_ratio"])))
        tip = root * float(cfg["taper_ratio"])
        mac = (2.0 / 3.0) * root * (1.0 + float(cfg["taper_ratio"]) + float(cfg["taper_ratio"]) ** 2) / (1.0 + float(cfg["taper_ratio"]))
        root_le = qmac_x - 0.25 * mac
        require(close(case["area_m2"], area), f"{case['id']}: area differs from baseline")
        require(close(case["span_m"], span), f"{case['id']}: span derivation mismatch")
        require(close(case["root_chord_m"], root), f"{case['id']}: root chord derivation mismatch")
        require(close(case["tip_chord_m"], tip), f"{case['id']}: tip chord derivation mismatch")
        require(close(case["mean_aerodynamic_chord_m"], mac), f"{case['id']}: MAC derivation mismatch")
        require(close(case["root_le_x_m"], root_le), f"{case['id']}: root LE placement mismatch")
        require(close(case["quarter_mac_x_m"], qmac_x), f"{case['id']}: quarter-MAC x drift")
        sm = float(case["static_margin_fraction_mac"])
        require(math.isfinite(sm) and 0.02 <= sm <= 0.50, f"{case['id']}: static margin outside Phase 3B broad gate")
        np_x = float(case["neutral_point_x_m"])
        require(close(np_x, geom["mass"]["gross_cg_x_m"] + sm * w["mean_aerodynamic_chord_m"]), f"{case['id']}: neutral point conversion mismatch")

    review_lo, review_hi = geom["horizontal_tail"]["review_band_fraction_mac"]
    inside = [c["id"] for c in candidates if review_lo <= c["static_margin_fraction_mac"] <= review_hi]
    require(inside == geom["phase3b_results"]["cases_inside_review_band"], "review-band case list is inconsistent")

    cfg_airfoils = json.loads(Path("config/airfoil_sources.json").read_text())["airfoils"]
    expected_profiles = {"DAE11": "dae11", "DAE21": "dae21", "DAE31": "dae31", "DAE41": "dae41"}
    require(set(profiles["profiles"]) == set(expected_profiles), "wing profile set differs from DAE11/21/31/41")
    for name, cfg_name in expected_profiles.items():
        pts = profiles["profiles"][name]
        require(len(pts) >= 70, f"{name}: too few source-coordinate points")
        require(all(len(p) == 2 and all(math.isfinite(float(v)) for v in p) for p in pts), f"{name}: non-finite coordinate")
        xs = [float(p[0]) for p in pts]
        require(min(xs) <= 0.001 and max(xs) >= 0.999, f"{name}: coordinate domain does not cover chord")
        require(profiles["meta"]["sha256"][name] == cfg_airfoils[cfg_name]["expected_sha256"], f"{name}: source SHA metadata differs from repository pin")

    visual = set(geom["authority"]["visual_only"])
    require(any("pod" in x for x in visual), "pod visual-only boundary is missing")
    require(any("vertical-tail" in x for x in visual), "vertical-tail visual-only boundary is missing")
    require(geom["horizontal_tail"]["no_candidate_promoted"] is True, "viewer must not promote a Phase 3B tail candidate")

    print("VIEWER GEOMETRY VALIDATION PASSED")
    print(f"wing: {w['span_m']:.1f} m span / {w['area_m2']:.1f} m2 / {w['aspect_ratio']:.3f} AR")
    print(f"Phase 3B tails: {len(candidates)}; inside 8-20% review band: {len(inside)}")
    print(f"DAE profile points: {', '.join(f'{k}={len(v)}' for k, v in profiles['profiles'].items())}")


if __name__ == "__main__":
    main()
