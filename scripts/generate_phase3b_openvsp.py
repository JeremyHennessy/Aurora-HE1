#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path

from aurora_he1.geometry import chord_at_eta, solve_trapezoidal_wing


def trapezoid_from_area_ar_taper(area_m2: float, aspect_ratio: float, taper_ratio: float) -> dict[str, float]:
    span = math.sqrt(area_m2 * aspect_ratio)
    root = 2.0 * area_m2 / (span * (1.0 + taper_ratio))
    tip = taper_ratio * root
    mac = (2.0 / 3.0) * root * (1.0 + taper_ratio + taper_ratio**2) / (1.0 + taper_ratio)
    return {
        "area_m2": area_m2,
        "aspect_ratio": aspect_ratio,
        "taper_ratio": taper_ratio,
        "span_m": span,
        "root_chord_m": root,
        "tip_chord_m": tip,
        "mean_aerodynamic_chord_m": mac,
    }


def baseline_cg(base: dict) -> tuple[float, float, float]:
    items = base["mass"]["items"]
    empty_mass = sum(float(item["mass_kg"]) for item in items)
    empty_moment = sum(float(item["mass_kg"]) * float(item["x_m"]) for item in items)
    pilot_mass = float(base["mass"]["reference_pilot_and_personal_gear_kg"])
    pilot_x = float(base["mass"]["reference_pilot_cg_x_m"])
    gross_mass = empty_mass + pilot_mass
    gross_cg = (empty_moment + pilot_mass * pilot_x) / gross_mass
    return empty_mass, gross_mass, gross_cg


def main_wing_data(base: dict) -> dict:
    wing_cfg = base["geometry"]["wing"]
    wing = solve_trapezoidal_wing(wing_cfg["span_m"], wing_cfg["area_m2"], wing_cfg["taper_ratio"])
    eta = [0.0, 0.25, 0.50, 0.75, 1.0]
    tracked = {float(s["eta"]): s for s in wing_cfg["airfoil_stations"]}
    stations = []
    for x in eta:
        stations.append(
            {
                "eta": x,
                "semi_span_y_m": x * wing.span_m / 2.0,
                "chord_m": chord_at_eta(wing, x),
                "twist_deg": float(tracked[x]["twist_deg"]),
                "airfoil_label": tracked[x]["airfoil"],
            }
        )
    segment_span = wing.span_m / 8.0
    section_areas = [
        segment_span * (stations[i - 1]["chord_m"] + stations[i]["chord_m"]) / 2.0
        for i in range(1, len(stations))
    ]
    if abs(2.0 * sum(section_areas) - wing.area_m2) > 1e-10:
        raise SystemExit("main-wing section areas do not close to baseline area")
    return {
        "span_m": wing.span_m,
        "area_m2": wing.area_m2,
        "aspect_ratio": wing.aspect_ratio,
        "root_chord_m": wing.root_chord_m,
        "tip_chord_m": wing.tip_chord_m,
        "mean_aerodynamic_chord_m": wing.mean_aerodynamic_chord_m,
        "taper_ratio": wing.taper_ratio,
        "root_le_x_m": float(wing_cfg["root_le_x_m"]),
        "incidence_deg": float(wing_cfg["incidence_deg"]),
        "dihedral_deg": float(wing_cfg["dihedral_deg"]),
        "segment_semispan_m": segment_span,
        "section_semispan_areas_m2": section_areas,
        "stations": stations,
    }


def script_for_case(base: dict, cfg: dict, wing: dict, case: dict, gross_cg_x_m: float) -> str:
    a = cfg["analysis"]
    ht_cfg = cfg["horizontal_tail_family"]
    tail = case["tail"]
    wing_chords = [s["chord_m"] for s in wing["stations"]]
    wing_twists = [wing["stations"][i]["twist_deg"] for i in range(1, 5)]
    case_id = case["id"]
    n_alpha = int(a["alpha_points"])

    lines = [
        "void main()",
        "{",
        "    VSPCheckSetup();",
        "    VSPRenew();",
        '    string wing_id = AddGeom("WING", "");',
        '    SetGeomName(wing_id, "AURORA_HE1_MainWing");',
        '    SetParmVal(wing_id, "RelativeTwistFlag", "WingGeom", 0.0);',
        '    SetParmVal(wing_id, "RelativeDihedralFlag", "WingGeom", 0.0);',
        '    InsertXSec(wing_id, 1, XS_FOUR_SERIES);',
        '    InsertXSec(wing_id, 2, XS_FOUR_SERIES);',
        '    InsertXSec(wing_id, 3, XS_FOUR_SERIES);',
        "    Update();",
    ]
    for i in range(1, 5):
        lines += [
            f"    SetDriverGroup(wing_id, {i}, AREA_WSECT_DRIVER, ROOTC_WSECT_DRIVER, TIPC_WSECT_DRIVER);",
            f'    SetParmVal(wing_id, "Root_Chord", "XSec_{i}", {wing_chords[i - 1]:.12f});',
            f'    SetParmVal(wing_id, "Tip_Chord", "XSec_{i}", {wing_chords[i]:.12f});',
            f'    SetParmVal(wing_id, "Area", "XSec_{i}", {wing["section_semispan_areas_m2"][i - 1]:.12f});',
            f'    SetParmVal(wing_id, "Sweep", "XSec_{i}", 0.0);',
            f'    SetParmVal(wing_id, "Sweep_Location", "XSec_{i}", 0.0);',
            f'    SetParmVal(wing_id, "Dihedral", "XSec_{i}", {wing["dihedral_deg"]:.12f});',
            f'    SetParmVal(wing_id, "Twist", "XSec_{i}", {wing_twists[i - 1]:.12f});',
            f'    SetParmVal(wing_id, "Twist_Location", "XSec_{i}", 0.25);',
            f'    SetParmVal(wing_id, "SectTess_U", "XSec_{i}", 16);',
            "    Update();",
        ]
    lines += [
        f'    SetParmVal(wing_id, "X_Rel_Location", "XForm", {wing["root_le_x_m"]:.12f});',
        f'    SetParmVal(wing_id, "Y_Rel_Rotation", "XForm", {wing["incidence_deg"]:.12f});',
        '    SetParmVal(wing_id, "Tess_W", "Shape", 45);',
        "    string wing_xsurf = GetXSecSurf(wing_id, 0);",
        "    for (int j = 0; j < GetNumXSec(wing_xsurf); j++)",
        "    {",
        "        ChangeXSecShape(wing_xsurf, j, XS_FOUR_SERIES);",
        "        string xid = GetXSec(wing_xsurf, j);",
        '        SetParmVal(GetXSecParm(xid, "Camber"), 0.0);',
        '        SetParmVal(GetXSecParm(xid, "ThickChord"), 0.01);',
        "    }",
        "    Update();",
        '    string tail_id = AddGeom("WING", "");',
        f'    SetGeomName(tail_id, "AURORA_HE1_HorizontalTail_{case_id}");',
        '    SetParmVal(tail_id, "RelativeTwistFlag", "WingGeom", 0.0);',
        '    SetParmVal(tail_id, "RelativeDihedralFlag", "WingGeom", 0.0);',
        '    SetDriverGroup(tail_id, 1, AREA_WSECT_DRIVER, ROOTC_WSECT_DRIVER, TIPC_WSECT_DRIVER);',
        f'    SetParmVal(tail_id, "Root_Chord", "XSec_1", {tail["root_chord_m"]:.12f});',
        f'    SetParmVal(tail_id, "Tip_Chord", "XSec_1", {tail["tip_chord_m"]:.12f});',
        f'    SetParmVal(tail_id, "Area", "XSec_1", {tail["area_m2"] / 2.0:.12f});',
        f'    SetParmVal(tail_id, "Sweep", "XSec_1", {float(ht_cfg["leading_edge_sweep_deg"]):.12f});',
        '    SetParmVal(tail_id, "Sweep_Location", "XSec_1", 0.0);',
        f'    SetParmVal(tail_id, "Dihedral", "XSec_1", {float(ht_cfg["dihedral_deg"]):.12f});',
        '    SetParmVal(tail_id, "Twist", "XSec_1", 0.0);',
        '    SetParmVal(tail_id, "Twist_Location", "XSec_1", 0.25);',
        '    SetParmVal(tail_id, "SectTess_U", "XSec_1", 18);',
        f'    SetParmVal(tail_id, "X_Rel_Location", "XForm", {tail["root_le_x_m"]:.12f});',
        f'    SetParmVal(tail_id, "Z_Rel_Location", "XForm", {float(ht_cfg["vertical_position_m"]):.12f});',
        f'    SetParmVal(tail_id, "Y_Rel_Rotation", "XForm", {float(ht_cfg["incidence_deg"]):.12f});',
        '    SetParmVal(tail_id, "Tess_W", "Shape", 35);',
        "    string tail_xsurf = GetXSecSurf(tail_id, 0);",
        "    for (int j = 0; j < GetNumXSec(tail_xsurf); j++)",
        "    {",
        "        ChangeXSecShape(tail_xsurf, j, XS_FOUR_SERIES);",
        "        string xid = GetXSec(tail_xsurf, j);",
        '        SetParmVal(GetXSecParm(xid, "Camber"), 0.0);',
        '        SetParmVal(GetXSecParm(xid, "ThickChord"), 0.01);',
        "    }",
        "    Update();",
        f'    WriteVSPFile("analysis/phase3b/{case_id}.vsp3", SET_ALL);',
        '    SetVSPAERORefWingID(wing_id);',
        '    string settings = FindContainer("VSPAEROSettings", 0);',
        '    if (settings.length() == 0) { Print("PHASE3B_ERROR|VSPAEROSettings container missing"); return; }',
        '    string xcg_id = FindParm(settings, "Xcg", "VSPAERO");',
        f'    SetParmValUpdate(xcg_id, {gross_cg_x_m:.12f});',
        f'    Print("PHASE3B_VERSION|{case_id}|", false); Print(GetVSPVersion());',
        f'    Print("PHASE3B_MAIN_GEOM|{case_id}|", false);',
        '    Print(GetParmVal(wing_id, "TotalSpan", "WingGeom"), false); Print("|", false);',
        '    Print(GetParmVal(wing_id, "TotalArea", "WingGeom"), false); Print("|", false);',
        '    Print(GetParmVal(wing_id, "Root_Chord", "XSec_1"), false); Print("|", false);',
        '    Print(GetParmVal(wing_id, "Tip_Chord", "XSec_4"));',
        f'    Print("PHASE3B_TAIL_GEOM|{case_id}|", false);',
        '    Print(GetParmVal(tail_id, "TotalSpan", "WingGeom"), false); Print("|", false);',
        '    Print(GetParmVal(tail_id, "TotalArea", "WingGeom"), false); Print("|", false);',
        '    Print(GetParmVal(tail_id, "Root_Chord", "XSec_1"), false); Print("|", false);',
        '    Print(GetParmVal(tail_id, "Tip_Chord", "XSec_1"));',
        f'    Print("PHASE3B_CG|{case_id}|{gross_cg_x_m:.12f}");',
        '    string cg_name = "VSPAEROComputeGeometry";',
        '    SetAnalysisInputDefaults(cg_name);',
        '    array<int> cg_thick = GetIntAnalysisInput(cg_name, "GeomSet");',
        '    array<int> cg_thin = GetIntAnalysisInput(cg_name, "ThinGeomSet");',
        '    if (cg_thick.size() == 0 || cg_thin.size() == 0) { Print("PHASE3B_ERROR|compute-geometry set inputs missing"); return; }',
        '    cg_thick[0] = SET_TYPE::SET_NONE;',
        '    cg_thin[0] = SET_TYPE::SET_ALL;',
        '    SetIntAnalysisInput(cg_name, "GeomSet", cg_thick);',
        '    SetIntAnalysisInput(cg_name, "ThinGeomSet", cg_thin);',
        '    string cg_res = ExecAnalysis(cg_name);',
        '    if (cg_res.length() == 0) { Print("PHASE3B_ERROR|VSPAEROComputeGeometry returned no result"); return; }',
        '    string analysis_name = "VSPAEROSweep";',
        '    SetAnalysisInputDefaults(analysis_name);',
        '    array<int> sweep_thick = GetIntAnalysisInput(analysis_name, "GeomSet");',
        '    array<int> sweep_thin = GetIntAnalysisInput(analysis_name, "ThinGeomSet");',
        '    if (sweep_thick.size() == 0 || sweep_thin.size() == 0) { Print("PHASE3B_ERROR|sweep set inputs missing"); return; }',
        '    sweep_thick[0] = SET_TYPE::SET_NONE;',
        '    sweep_thin[0] = SET_TYPE::SET_ALL;',
        '    SetIntAnalysisInput(analysis_name, "GeomSet", sweep_thick);',
        '    SetIntAnalysisInput(analysis_name, "ThinGeomSet", sweep_thin);',
        '    array<int> ref_flag(1, 0); SetIntAnalysisInput(analysis_name, "RefFlag", ref_flag);',
        f'    array<double> sref(1, {wing["area_m2"]:.12f}); SetDoubleAnalysisInput(analysis_name, "Sref", sref);',
        f'    array<double> bref(1, {wing["span_m"]:.12f}); SetDoubleAnalysisInput(analysis_name, "bref", bref);',
        f'    array<double> cref(1, {wing["mean_aerodynamic_chord_m"]:.12f}); SetDoubleAnalysisInput(analysis_name, "cref", cref);',
        f'    array<double> alpha_start(1, {float(a["alpha_start_deg"]):.12f}); SetDoubleAnalysisInput(analysis_name, "AlphaStart", alpha_start);',
        f'    array<double> alpha_end(1, {float(a["alpha_end_deg"]):.12f}); SetDoubleAnalysisInput(analysis_name, "AlphaEnd", alpha_end);',
        f'    array<int> alpha_n(1, {n_alpha}); SetIntAnalysisInput(analysis_name, "AlphaNpts", alpha_n);',
        f'    array<double> mach_start(1, {float(a["mach"]):.12f}); SetDoubleAnalysisInput(analysis_name, "MachStart", mach_start);',
        f'    array<double> mach_end(1, {float(a["mach"]):.12f}); SetDoubleAnalysisInput(analysis_name, "MachEnd", mach_end);',
        '    array<int> mach_n(1, 1); SetIntAnalysisInput(analysis_name, "MachNpts", mach_n);',
        '    string sweep_res = ExecAnalysis(analysis_name);',
        '    if (sweep_res.length() == 0) { Print("PHASE3B_ERROR|VSPAEROSweep returned no result"); return; }',
        f'    Print("PHASE3B_POLAR|{case_id}|analysis/phase3b/{case_id}.polar");',
        f'    Print("PHASE3B_COMPLETE|{case_id}");',
        "    while (GetNumTotalErrors() > 0)",
        "    {",
        "        ErrorObj err = PopLastError();",
        '        Print("PHASE3B_API_ERROR|" + err.GetErrorString());',
        "    }",
        "}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    base = json.loads(Path("config/he1_baseline.json").read_text())
    cfg = json.loads(Path("config/phase3b_longitudinal_tail.json").read_text())
    wing = main_wing_data(base)
    empty_mass, gross_mass, gross_cg = baseline_cg(base)
    tail_cfg = base["geometry"]["tail"]
    ht_area = float(tail_cfg["horizontal_area_m2"])
    tail_ac_x = float(tail_cfg["tail_ac_x_m"])
    tail_arm = tail_ac_x - gross_cg
    tail_volume = ht_area * tail_arm / (wing["area_m2"] * wing["mean_aerodynamic_chord_m"])

    cases = []
    for raw in cfg["horizontal_tail_family"]["candidates"]:
        tail = trapezoid_from_area_ar_taper(ht_area, float(raw["aspect_ratio"]), float(raw["taper_ratio"]))
        tail["root_le_x_m"] = tail_ac_x - 0.25 * tail["mean_aerodynamic_chord_m"]
        tail["quarter_mac_x_m"] = tail_ac_x
        tail["tail_arm_from_reference_cg_m"] = tail_arm
        tail["horizontal_tail_volume_coefficient"] = tail_volume
        cases.append({"id": raw["id"], "tail": tail})

    manifest = {
        "status": cfg["status"],
        "source_phase3a_main_sha": cfg["source_phase3a_main_sha"],
        "source_baseline": "config/he1_baseline.json",
        "toolchain": cfg["toolchain"],
        "scope": cfg["scope"],
        "reference_mass": {
            "empty_mass_kg": empty_mass,
            "gross_mass_kg": gross_mass,
            "gross_cg_x_m": gross_cg,
        },
        "main_wing": wing,
        "horizontal_tail_fixed": {
            "area_m2": ht_area,
            "aerodynamic_center_x_m": tail_ac_x,
            "tail_arm_from_reference_cg_m": tail_arm,
            "horizontal_tail_volume_coefficient": tail_volume,
        },
        "analysis": cfg["analysis"],
        "design_review": cfg["design_review"],
        "cases": cases,
        "boundary": cfg["boundary"],
    }

    out = Path("analysis/phase3b")
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for case in cases:
        (out / f"{case['id']}.vspscript").write_text(script_for_case(base, cfg, wing, case, gross_cg))

    print(
        json.dumps(
            {
                "cases": [case["id"] for case in cases],
                "gross_cg_x_m": gross_cg,
                "wing_mac_m": wing["mean_aerodynamic_chord_m"],
                "horizontal_tail_volume_coefficient": tail_volume,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
