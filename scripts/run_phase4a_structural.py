#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

G = 9.80665


def chord_at_y(wing: dict, y_m: float) -> float:
    semi = float(wing["semi_span_m"])
    eta = max(0.0, min(1.0, y_m / semi))
    return float(wing["root_chord_m"]) + (float(wing["tip_chord_m"]) - float(wing["root_chord_m"])) * eta


def internal_at_cut(sections: list[dict], total_halfwing_load_n: float, cut_y_m: float, brace_vertical_n: float, brace_y_m: float) -> dict:
    shear = 0.0
    moment = 0.0
    for s in sections:
        y = float(s["y_m"])
        if y + 1e-12 < cut_y_m:
            continue
        force = total_halfwing_load_n * float(s["normalized_vertical_load_fraction"])
        shear += force
        moment += force * (y - cut_y_m)
    if brace_y_m + 1e-12 >= cut_y_m:
        shear += brace_vertical_n
        moment += brace_vertical_n * (brace_y_m - cut_y_m)
    return {"shear_n": shear, "bending_moment_nm": moment}


def cap_screening(moment_nm: float, chord_m: float, depth_frac: float, stresses_mpa: list[float]) -> dict:
    depth = depth_frac * chord_m
    force = abs(moment_nm) / max(depth, 1e-9)
    areas = {f"{int(s)}_mpa": force / (s * 1e6) * 1e6 for s in stresses_mpa}
    return {
        "effective_spar_depth_m": depth,
        "idealized_cap_axial_force_n": force,
        "required_single_cap_area_mm2_by_effective_stress": areas,
    }


def load_case(name: str, factor_g: float, gross_mass_kg: float, sections: list[dict], wing: dict, concept: dict, stresses: list[float], braced: bool) -> dict:
    halfwing = factor_g * gross_mass_kg * G / 2.0
    brace_station = float(concept["brace_station_semispan_y_m"])
    brace_share = float(concept["illustrative_positive_brace_halfwing_vertical_share"])
    brace_active = braced and factor_g > 0.0
    brace_vertical = -brace_share * halfwing if brace_active else 0.0
    brace_angle = math.radians(float(concept["illustrative_brace_angle_deg"]))
    brace_tension = abs(brace_vertical) / max(math.sin(brace_angle), 1e-9) if brace_active else 0.0
    brace_horizontal = brace_tension * math.cos(brace_angle) if brace_active else 0.0

    station_y = [0.0] + [float(x) for x in concept["panel_joint_semispan_y_m"]] + [float(wing["semi_span_m"])]
    stations = []
    for y in station_y:
        demand = internal_at_cut(sections, halfwing, y, brace_vertical, brace_station)
        chord = chord_at_y(wing, y)
        stations.append({
            "y_m": y,
            "chord_m": chord,
            **demand,
            **cap_screening(demand["bending_moment_nm"], chord, float(concept["spar_effective_depth_fraction_chord"]), stresses),
        })

    root = stations[0]
    ultimate = float(concept["ultimate_factor_on_limit"])
    return {
        "id": name,
        "load_factor_g": factor_g,
        "halfwing_aerodynamic_resultant_n": halfwing,
        "brace_model_active": brace_active,
        "brace": {
            "station_y_m": brace_station,
            "vertical_reaction_on_wing_n": brace_vertical,
            "illustrative_angle_deg": float(concept["illustrative_brace_angle_deg"]),
            "axial_tension_limit_n": brace_tension,
            "horizontal_component_limit_n": brace_horizontal,
            "axial_tension_ultimate_n": brace_tension * ultimate,
            "horizontal_component_ultimate_n": brace_horizontal * ultimate,
        },
        "root": {
            "shear_n": root["shear_n"],
            "bending_moment_nm": root["bending_moment_nm"],
            "ultimate_abs_bending_moment_nm": abs(root["bending_moment_nm"]) * ultimate,
            "idealized_cap_axial_force_n": root["idealized_cap_axial_force_n"],
        },
        "stations": stations,
    }


def main() -> None:
    root = Path("analysis/phase4a")
    manifest = json.loads((root / "manifest.json").read_text())
    span = json.loads((root / "spanload.json").read_text())
    base = json.loads(Path("config/he1_baseline.json").read_text())
    concept = manifest["structural_concept"]
    stresses = [float(x) for x in manifest["screening_only"]["effective_cap_stress_mpa"]]
    wing = span["main_wing"]
    gross_mass = sum(float(x["mass_kg"]) for x in base["mass"]["items"]) + float(base["mass"]["reference_pilot_and_personal_gear_kg"])

    by_alpha = {float(c["alpha_deg"]): c for c in span["cases"]}
    selected_alpha = float(manifest["aero_load_shape"]["selected_conservative_alpha_deg"])
    selected = by_alpha[selected_alpha]
    sections = selected["sections"]

    cases = [
        load_case("POS_1G_CANTILEVER", 1.0, gross_mass, sections, wing, concept, stresses, False),
        load_case("POS_2P5G_CANTILEVER", float(concept["positive_limit_load_factor_g"]), gross_mass, sections, wing, concept, stresses, False),
        load_case("POS_2P5G_BRACED_ILLUSTRATIVE", float(concept["positive_limit_load_factor_g"]), gross_mass, sections, wing, concept, stresses, True),
        load_case("NEG_1G_CANTILEVER", float(concept["negative_limit_load_factor_g"]), gross_mass, sections, wing, concept, stresses, False),
    ]

    shape_sensitivity = []
    for alpha, case in sorted(by_alpha.items()):
        shape_sensitivity.append({
            "alpha_deg": alpha,
            "halfwing_load_centroid_y_m": float(case["halfwing_load_centroid_y_m"]),
            "positive_2p5g_cantilever_root_moment_nm": float(concept["positive_limit_load_factor_g"]) * gross_mass * G / 2.0 * float(case["halfwing_load_centroid_y_m"]),
        })

    pdr_limit = next(c for c in cases if c["id"] == "POS_2P5G_BRACED_ILLUSTRATIVE")
    cantilever_limit = next(c for c in cases if c["id"] == "POS_2P5G_CANTILEVER")
    out = {
        "status": manifest["status"],
        "source_phase3c_main_sha": manifest["source_phase3c_main_sha"],
        "reference_gross_mass_kg": gross_mass,
        "wing": wing,
        "selected_spanload_alpha_deg": selected_alpha,
        "selected_halfwing_load_centroid_y_m": selected["halfwing_load_centroid_y_m"],
        "shape_sensitivity": shape_sensitivity,
        "structural_concept": concept,
        "screening_only": manifest["screening_only"],
        "load_cases": cases,
        "headline": {
            "positive_2p5g_cantilever_root_moment_nm": cantilever_limit["root"]["bending_moment_nm"],
            "positive_2p5g_braced_root_moment_nm": pdr_limit["root"]["bending_moment_nm"],
            "positive_2p5g_brace_tension_limit_n": pdr_limit["brace"]["axial_tension_limit_n"],
            "positive_2p5g_brace_tension_ultimate_n": pdr_limit["brace"]["axial_tension_ultimate_n"],
            "brace_root_moment_reduction_fraction": 1.0 - abs(pdr_limit["root"]["bending_moment_nm"]) / abs(cantilever_limit["root"]["bending_moment_nm"]),
        },
        "boundary": manifest["boundary"],
    }
    (root / "structural_results.json").write_text(json.dumps(out, indent=2) + "\n")

    with (root / "joint_loads.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "y_m", "shear_n", "bending_moment_nm", "effective_spar_depth_m", "idealized_cap_axial_force_n"])
        for c in cases:
            for s in c["stations"]:
                w.writerow([c["id"], s["y_m"], s["shear_n"], s["bending_moment_nm"], s["effective_spar_depth_m"], s["idealized_cap_axial_force_n"]])

    print(json.dumps(out["headline"], indent=2))


if __name__ == "__main__":
    main()
