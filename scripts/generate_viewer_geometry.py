#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

BASELINE = Path("config/he1_baseline.json")
PHASE3B = Path("config/phase3b_longitudinal_tail.json")
PHASE3B_RESULTS = Path("viewer/data/phase3b_results.json")
SNAPSHOT = Path("viewer/data/verified_snapshot.json")
OUTPUT = Path("viewer/data/geometry_fidelity.json")


def load(path: Path):
    return json.loads(path.read_text())


def wing_derived(wing: dict) -> tuple[float, float, float, float]:
    span = float(wing["span_m"])
    area = float(wing["area_m2"])
    taper = float(wing["taper_ratio"])
    root = 2.0 * area / (span * (1.0 + taper))
    tip = root * taper
    mac = (2.0 / 3.0) * root * (1.0 + taper + taper * taper) / (1.0 + taper)
    ar = span * span / area
    return root, tip, mac, ar


def station_visual(station: dict) -> dict:
    label = str(station["airfoil"])
    token = label.split()[0]
    parts = token.split("/")
    provisional = "provisional" in label.lower()
    blend = len(parts) == 2
    if blend:
        authority = "provisional 50/50 visualization of unresolved blend"
    elif provisional:
        authority = "provisional profile assignment"
    else:
        authority = "tracked profile"
    return {
        "eta": float(station["eta"]),
        "profile_a": parts[0],
        "profile_b": parts[1] if blend else None,
        "blend_fraction": 0.5 if blend else 0.0,
        "twist_deg": float(station["twist_deg"]),
        "authority": authority,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if tracked output differs from regenerated output")
    args = parser.parse_args()

    baseline = load(BASELINE)
    p3b = load(PHASE3B)
    evidence = load(PHASE3B_RESULTS)
    snapshot = load(SNAPSHOT)

    geom = baseline["geometry"]
    wing = geom["wing"]
    tail = geom["tail"]
    prop = geom["propeller"]
    mass = baseline["mass"]
    root, tip, mac, ar = wing_derived(wing)

    empty_mass = sum(float(x["mass_kg"]) for x in mass["items"])
    pilot_mass = float(mass["reference_pilot_and_personal_gear_kg"])
    pilot_x = float(mass["reference_pilot_cg_x_m"])
    gross_mass = empty_mass + pilot_mass
    gross_moment = sum(float(x["mass_kg"]) * float(x["x_m"]) for x in mass["items"]) + pilot_mass * pilot_x
    gross_cg = gross_moment / gross_mass

    evidence_by_id = {x["id"]: x for x in evidence["cases"]}
    review_lo, review_hi = p3b["design_review"]["provisional_static_margin_review_band_fraction_mac"]
    candidates = []
    area = float(tail["horizontal_area_m2"])
    qmac_x = float(tail["tail_ac_x_m"])
    family = p3b["horizontal_tail_family"]
    for cfg in family["candidates"]:
        cid = cfg["id"]
        ev = evidence_by_id[cid]
        cand_ar = float(cfg["aspect_ratio"])
        taper = float(cfg["taper_ratio"])
        span = math.sqrt(area * cand_ar)
        cr = 2.0 * area / (span * (1.0 + taper))
        ct = cr * taper
        cmac = (2.0 / 3.0) * cr * (1.0 + taper + taper * taper) / (1.0 + taper)
        root_le = qmac_x - 0.25 * cmac
        sm = float(ev["static_margin_fraction_mac"])
        candidates.append({
            "id": cid,
            "area_m2": area,
            "aspect_ratio": cand_ar,
            "taper_ratio": taper,
            "span_m": span,
            "root_chord_m": cr,
            "tip_chord_m": ct,
            "mean_aerodynamic_chord_m": cmac,
            "root_le_x_m": root_le,
            "quarter_mac_x_m": qmac_x,
            "incidence_deg": float(family["incidence_deg"]),
            "dihedral_deg": float(family["dihedral_deg"]),
            "leading_edge_sweep_deg": float(family["leading_edge_sweep_deg"]),
            "vertical_position_m": float(family["vertical_position_m"]),
            "static_margin_fraction_mac": sm,
            "neutral_point_x_m": float(ev["neutral_point_x_m"]),
            "inside_review_band": review_lo <= sm <= review_hi,
        })

    phase2b = snapshot["phase2b"]
    ref = phase2b["baseline_reference"]
    selected = phase2b["selected_design"]
    prop_hub_x = next(float(x["x_m"]) for x in mass["items"] if x["name"] == "propeller_and_hub")

    out = {
        "meta": {
            "project": "Aurora HE-1 3D fidelity model",
            "status": "ENGINEERING VISUALIZATION / NOT FOR CONSTRUCTION OR FLIGHT CLEARANCE",
            "source_phase3a_main": p3b["source_phase3a_main_sha"],
            "source_phase3b_head": evidence["meta"]["phase3b_head"],
            "source_phase3b_merge": evidence["meta"]["phase3b_merge"],
            "phase3b_validation_run": evidence["meta"]["validation_run"],
            "coordinate_frame": "X aft from propeller/nose datum, Y spanwise, Z up relative to aerodynamic reference; ground clearance is a separate local propeller datum",
        },
        "authority": {
            "authoritative_or_tracked": [
                "overall length 10.8 m",
                "main wing span, area, taper, root leading-edge x, incidence and dihedral",
                "main wing station twist values",
                "baseline horizontal and vertical tail areas",
                "tail aerodynamic-center x = 8.85 m",
                "baseline mass stations and gross CG",
                "propeller diameters/RPM values and shaft-center ground-height constraint",
            ],
            "computationally_resolved": [
                "Phase 3A OpenVSP/VSPAERO main-wing geometry convention",
                "five Phase 3B horizontal-tail planforms holding area and quarter-MAC x fixed",
                "Phase 3B VLM static margins and neutral-point locations",
            ],
            "visual_only": [
                "50/50 interpolation at unresolved DAE blend stations",
                "pod/fairing outer envelope",
                "boom radius",
                "pilot body geometry",
                "vertical-tail square area proxy",
                "propeller longitudinal plane uses propeller/hub mass station as display surrogate",
                "landing gear is not geometrically resolved",
            ],
        },
        "overall_length_m": float(geom["overall_length_m"]),
        "wing": {
            "span_m": float(wing["span_m"]),
            "area_m2": float(wing["area_m2"]),
            "taper_ratio": float(wing["taper_ratio"]),
            "dihedral_deg": float(wing["dihedral_deg"]),
            "incidence_deg": float(wing["incidence_deg"]),
            "root_le_x_m": float(wing["root_le_x_m"]),
            "root_chord_m": root,
            "tip_chord_m": tip,
            "mean_aerodynamic_chord_m": mac,
            "aspect_ratio": ar,
            "stations": [station_visual(x) for x in wing["airfoil_stations"]],
        },
        "horizontal_tail": {
            "fixed_area_m2": area,
            "fixed_aerodynamic_center_x_m": qmac_x,
            "review_band_fraction_mac": [float(review_lo), float(review_hi)],
            "default_display_case": "HT35T70",
            "no_candidate_promoted": True,
            "candidates": candidates,
        },
        "vertical_tail": {
            "area_m2": float(tail["vertical_area_m2"]),
            "planform_status": "unresolved",
            "visual_proxy": {
                "shape": "square",
                "side_m": math.sqrt(float(tail["vertical_area_m2"])),
                "area_m2": float(tail["vertical_area_m2"]),
                "authority": "area exact; aspect ratio and location/shape visual only",
            },
        },
        "propeller": {
            "baseline": {
                "diameter_m": float(ref["diameter_m"]),
                "rpm": float(ref["design_rpm"]),
                "ground_clearance_m": float(ref["ground_clearance_m"]),
            },
            "phase2b_numerical_candidate": {
                "diameter_m": float(selected["diameter_m"]),
                "rpm": float(selected["design_rpm"]),
                "ground_clearance_m": float(selected["ground_clearance_m"]),
                "promoted": False,
            },
            "shaft_center_height_m": float(prop["shaft_center_height_m"]),
            "minimum_target_ground_clearance_m": float(prop["minimum_target_ground_clearance_m"]),
            "display_plane_x_m": prop_hub_x,
            "display_plane_basis": "propeller_and_hub mass station only; exact shaft x is not yet tracked",
        },
        "mass": {
            "empty_mass_kg": empty_mass,
            "reference_pilot_and_personal_gear_kg": pilot_mass,
            "gross_mass_kg": gross_mass,
            "gross_cg_x_m": gross_cg,
            "reference_pilot_cg_x_m": pilot_x,
            "items": mass["items"],
        },
        "visual_envelopes": {
            "pod": {"center_x_m": 2.45, "length_m": 2.4, "width_m": 0.65, "height_m": 0.8, "authority": "visual envelope only; no aerodynamic or structural use"},
            "boom": {"start_x_m": 3.35, "end_x_m": min(c["root_le_x_m"] for c in candidates), "radius_m": 0.035, "authority": "visual radius only; longitudinal extent follows pod-to-tail connection"},
            "pilot": {"cg_x_m": pilot_x, "authority": "reference pilot CG x exact; body dimensions visual only"},
        },
        "phase3b_results": {
            "case_count": len(candidates),
            "static_margin_range_fraction_mac": [min(c["static_margin_fraction_mac"] for c in candidates), max(c["static_margin_fraction_mac"] for c in candidates)],
            "cases_inside_review_band": [c["id"] for c in candidates if c["inside_review_band"]],
            "interpretation": "All tested fixed-area/fixed-arm tail planforms are much more statically stable than the provisional 8-20% MAC screening band. Planform change alone does not reach the target.",
        },
    }

    rendered = json.dumps(out, indent=2, sort_keys=False) + "\n"
    if args.check:
        current = OUTPUT.read_text() if OUTPUT.exists() else ""
        if current != rendered:
            raise SystemExit("VIEWER GEOMETRY GENERATION CHECK FAILED: tracked geometry_fidelity.json is stale; run scripts/generate_viewer_geometry.py")
        print("VIEWER GEOMETRY GENERATION CHECK PASSED")
    else:
        OUTPUT.write_text(rendered)
        print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
