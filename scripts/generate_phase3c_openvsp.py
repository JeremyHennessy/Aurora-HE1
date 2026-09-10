#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path

from generate_phase3b_openvsp import baseline_cg, main_wing_data, trapezoid_from_area_ar_taper


def tail_design(area_m2: float, ac_x_m: float, planform: dict, gross_cg_x_m: float, wing: dict) -> dict[str, float]:
    tail = trapezoid_from_area_ar_taper(area_m2, float(planform["aspect_ratio"]), float(planform["taper_ratio"]))
    tail["root_le_x_m"] = ac_x_m - 0.25 * tail["mean_aerodynamic_chord_m"]
    tail["quarter_mac_x_m"] = ac_x_m
    tail["tail_arm_from_reference_cg_m"] = ac_x_m - gross_cg_x_m
    tail["horizontal_tail_volume_coefficient"] = area_m2 * (ac_x_m - gross_cg_x_m) / (wing["area_m2"] * wing["mean_aerodynamic_chord_m"])
    return tail


def default_mesh() -> dict[str, int]:
    return {
        "wing_section_tess_u": 16,
        "wing_tess_w": 45,
        "tail_section_tess_u": 18,
        "tail_tess_w": 35,
    }


def build_cases(base: dict, cfg: dict, wing: dict, gross_cg_x_m: float) -> list[dict]:
    planform = cfg["reference_tail_planform"]
    ref = cfg["sanity_cases"]["phase3b_reference"]
    mac = float(wing["mean_aerodynamic_chord_m"])
    normal = default_mesh()
    cases: list[dict] = []

    cases.append({
        "id": "WING_ONLY",
        "category": "sanity_wing_only",
        "include_tail": False,
        "reference_cg_x_m": gross_cg_x_m,
        "mesh": normal,
        "tail": None,
    })

    reference_tail = tail_design(float(ref["tail_area_m2"]), float(ref["tail_ac_x_m"]), planform, gross_cg_x_m, wing)
    cases.append({
        "id": "REF_BASE",
        "category": "sanity_phase3b_reference",
        "include_tail": True,
        "reference_cg_x_m": gross_cg_x_m,
        "mesh": normal,
        "tail": reference_tail,
    })

    offsets = list(cfg["sanity_cases"]["cg_offset_fraction_mac"])
    for name, offset in (("REF_CG_FWD", min(offsets)), ("REF_CG_AFT", max(offsets))):
        xcg = gross_cg_x_m + float(offset) * mac
        cases.append({
            "id": name,
            "category": "sanity_cg_reference",
            "include_tail": True,
            "reference_cg_x_m": xcg,
            "cg_offset_fraction_mac": float(offset),
            "mesh": normal,
            "tail": tail_design(float(ref["tail_area_m2"]), float(ref["tail_ac_x_m"]), planform, xcg, wing),
        })

    fine = {k: int(v) for k, v in cfg["sanity_cases"]["fine_mesh"].items()}
    cases.append({
        "id": "REF_FINE",
        "category": "sanity_mesh_reference",
        "include_tail": True,
        "reference_cg_x_m": gross_cg_x_m,
        "mesh": fine,
        "tail": reference_tail,
    })

    for area in cfg["trade_grid"]["tail_area_m2"]:
        for ac_x in cfg["trade_grid"]["tail_ac_x_m"]:
            area_f = float(area)
            ac_f = float(ac_x)
            cid = f"GRID_A{int(round(area_f * 100)):03d}_X{int(round(ac_f * 100)):03d}"
            cases.append({
                "id": cid,
                "category": "tail_volume_grid",
                "include_tail": True,
                "reference_cg_x_m": gross_cg_x_m,
                "mesh": normal,
                "tail": tail_design(area_f, ac_f, planform, gross_cg_x_m, wing),
            })
    return cases


def script_for_case(cfg: dict, wing: dict, case: dict) -> str:
    a = cfg["analysis"]
    planform = cfg["reference_tail_planform"]
    case_id = case["id"]
    mesh = case["mesh"]
    wing_chords = [s["chord_m"] for s in wing["stations"]]
    wing_twists = [wing["stations"][i]["twist_deg"] for i in range(1, 5)]
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
            f'    SetParmVal(wing_id, "SectTess_U", "XSec_{i}", {int(mesh["wing_section_tess_u"])});',
            "    Update();",
        ]
    lines += [
        f'    SetParmVal(wing_id, "X_Rel_Location", "XForm", {wing["root_le_x_m"]:.12f});',
        f'    SetParmVal(wing_id, "Y_Rel_Rotation", "XForm", {wing["incidence_deg"]:.12f});',
        f'    SetParmVal(wing_id, "Tess_W", "Shape", {int(mesh["wing_tess_w"])});',
        "    string wing_xsurf = GetXSecSurf(wing_id, 0);",
        "    for (int j = 0; j < GetNumXSec(wing_xsurf); j++)",
        "    {",
        "        ChangeXSecShape(wing_xsurf, j, XS_FOUR_SERIES);",
        "        string xid = GetXSec(wing_xsurf, j);",
        '        SetParmVal(GetXSecParm(xid, "Camber"), 0.0);',
        '        SetParmVal(GetXSecParm(xid, "ThickChord"), 0.01);',
        "    }",
        "    Update();",
    ]

    if case["include_tail"]:
        tail = case["tail"]
        lines += [
            '    string tail_id = AddGeom("WING", "");',
            f'    SetGeomName(tail_id, "AURORA_HE1_HorizontalTail_{case_id}");',
            '    SetParmVal(tail_id, "RelativeTwistFlag", "WingGeom", 0.0);',
            '    SetParmVal(tail_id, "RelativeDihedralFlag", "WingGeom", 0.0);',
            '    SetDriverGroup(tail_id, 1, AREA_WSECT_DRIVER, ROOTC_WSECT_DRIVER, TIPC_WSECT_DRIVER);',
            f'    SetParmVal(tail_id, "Root_Chord", "XSec_1", {tail["root_chord_m"]:.12f});',
            f'    SetParmVal(tail_id, "Tip_Chord", "XSec_1", {tail["tip_chord_m"]:.12f});',
            f'    SetParmVal(tail_id, "Area", "XSec_1", {tail["area_m2"] / 2.0:.12f});',
            f'    SetParmVal(tail_id, "Sweep", "XSec_1", {float(planform["leading_edge_sweep_deg"]):.12f});',
            '    SetParmVal(tail_id, "Sweep_Location", "XSec_1", 0.0);',
            f'    SetParmVal(tail_id, "Dihedral", "XSec_1", {float(planform["dihedral_deg"]):.12f});',
            '    SetParmVal(tail_id, "Twist", "XSec_1", 0.0);',
            '    SetParmVal(tail_id, "Twist_Location", "XSec_1", 0.25);',
            f'    SetParmVal(tail_id, "SectTess_U", "XSec_1", {int(mesh["tail_section_tess_u"])});',
            f'    SetParmVal(tail_id, "X_Rel_Location", "XForm", {tail["root_le_x_m"]:.12f});',
            f'    SetParmVal(tail_id, "Z_Rel_Location", "XForm", {float(planform["vertical_position_m"]):.12f});',
            f'    SetParmVal(tail_id, "Y_Rel_Rotation", "XForm", {float(planform["incidence_deg"]):.12f});',
            f'    SetParmVal(tail_id, "Tess_W", "Shape", {int(mesh["tail_tess_w"])});',
            "    string tail_xsurf = GetXSecSurf(tail_id, 0);",
            "    for (int j = 0; j < GetNumXSec(tail_xsurf); j++)",
            "    {",
            "        ChangeXSecShape(tail_xsurf, j, XS_FOUR_SERIES);",
            "        string xid = GetXSec(tail_xsurf, j);",
            '        SetParmVal(GetXSecParm(xid, "Camber"), 0.0);',
            '        SetParmVal(GetXSecParm(xid, "ThickChord"), 0.01);',
            "    }",
            "    Update();",
        ]

    lines += [
        f'    WriteVSPFile("analysis/phase3c/{case_id}.vsp3", SET_ALL);',
        '    SetVSPAERORefWingID(wing_id);',
        '    string settings = FindContainer("VSPAEROSettings", 0);',
        '    if (settings.length() == 0) { Print("PHASE3C_ERROR|VSPAEROSettings container missing"); return; }',
        '    string xcg_id = FindParm(settings, "Xcg", "VSPAERO");',
        f'    SetParmValUpdate(xcg_id, {float(case["reference_cg_x_m"]):.12f});',
        f'    Print("PHASE3C_VERSION|{case_id}|", false); Print(GetVSPVersion());',
        f'    Print("PHASE3C_MAIN_GEOM|{case_id}|", false);',
        '    Print(GetParmVal(wing_id, "TotalSpan", "WingGeom"), false); Print("|", false);',
        '    Print(GetParmVal(wing_id, "TotalArea", "WingGeom"), false); Print("|", false);',
        '    Print(GetParmVal(wing_id, "Root_Chord", "XSec_1"), false); Print("|", false);',
        '    Print(GetParmVal(wing_id, "Tip_Chord", "XSec_4"));',
    ]
    if case["include_tail"]:
        lines += [
            f'    Print("PHASE3C_TAIL_GEOM|{case_id}|", false);',
            '    Print(GetParmVal(tail_id, "TotalSpan", "WingGeom"), false); Print("|", false);',
            '    Print(GetParmVal(tail_id, "TotalArea", "WingGeom"), false); Print("|", false);',
            '    Print(GetParmVal(tail_id, "Root_Chord", "XSec_1"), false); Print("|", false);',
            '    Print(GetParmVal(tail_id, "Tip_Chord", "XSec_1"));',
        ]
    else:
        lines.append(f'    Print("PHASE3C_NO_TAIL|{case_id}");')
    lines += [
        f'    Print("PHASE3C_CG|{case_id}|{float(case["reference_cg_x_m"]):.12f}");',
        '    string cg_name = "VSPAEROComputeGeometry";',
        '    SetAnalysisInputDefaults(cg_name);',
        '    array<int> cg_thick = GetIntAnalysisInput(cg_name, "GeomSet");',
        '    array<int> cg_thin = GetIntAnalysisInput(cg_name, "ThinGeomSet");',
        '    if (cg_thick.size() == 0 || cg_thin.size() == 0) { Print("PHASE3C_ERROR|compute-geometry set inputs missing"); return; }',
        '    cg_thick[0] = SET_TYPE::SET_NONE;',
        '    cg_thin[0] = SET_TYPE::SET_ALL;',
        '    SetIntAnalysisInput(cg_name, "GeomSet", cg_thick);',
        '    SetIntAnalysisInput(cg_name, "ThinGeomSet", cg_thin);',
        '    string cg_res = ExecAnalysis(cg_name);',
        '    if (cg_res.length() == 0) { Print("PHASE3C_ERROR|VSPAEROComputeGeometry returned no result"); return; }',
        '    string analysis_name = "VSPAEROSweep";',
        '    SetAnalysisInputDefaults(analysis_name);',
        '    array<int> sweep_thick = GetIntAnalysisInput(analysis_name, "GeomSet");',
        '    array<int> sweep_thin = GetIntAnalysisInput(analysis_name, "ThinGeomSet");',
        '    if (sweep_thick.size() == 0 || sweep_thin.size() == 0) { Print("PHASE3C_ERROR|sweep set inputs missing"); return; }',
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
        f'    array<int> alpha_n(1, {int(a["alpha_points"])}); SetIntAnalysisInput(analysis_name, "AlphaNpts", alpha_n);',
        f'    array<double> mach_start(1, {float(a["mach"]):.12f}); SetDoubleAnalysisInput(analysis_name, "MachStart", mach_start);',
        f'    array<double> mach_end(1, {float(a["mach"]):.12f}); SetDoubleAnalysisInput(analysis_name, "MachEnd", mach_end);',
        '    array<int> mach_n(1, 1); SetIntAnalysisInput(analysis_name, "MachNpts", mach_n);',
        '    string sweep_res = ExecAnalysis(analysis_name);',
        '    if (sweep_res.length() == 0) { Print("PHASE3C_ERROR|VSPAEROSweep returned no result"); return; }',
        f'    Print("PHASE3C_POLAR|{case_id}|analysis/phase3c/{case_id}.polar");',
        f'    Print("PHASE3C_COMPLETE|{case_id}");',
        "    while (GetNumTotalErrors() > 0)",
        "    {",
        "        ErrorObj err = PopLastError();",
        '        Print("PHASE3C_API_ERROR|" + err.GetErrorString());',
        "    }",
        "}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    base = json.loads(Path("config/he1_baseline.json").read_text())
    cfg = json.loads(Path("config/phase3c_tail_volume_trade.json").read_text())
    wing = main_wing_data(base)
    empty_mass, gross_mass, gross_cg = baseline_cg(base)
    cases = build_cases(base, cfg, wing, gross_cg)

    manifest = {
        "status": cfg["status"],
        "source_main_sha": cfg["source_main_sha"],
        "source_phase3b_head": cfg["source_phase3b_head"],
        "source_phase3b_validation_run": cfg["source_phase3b_validation_run"],
        "source_baseline": "config/he1_baseline.json",
        "toolchain": cfg["toolchain"],
        "reference_mass": {"empty_mass_kg": empty_mass, "gross_mass_kg": gross_mass, "gross_cg_x_m": gross_cg},
        "main_wing": wing,
        "reference_tail_planform": cfg["reference_tail_planform"],
        "analysis": cfg["analysis"],
        "design_review": cfg["design_review"],
        "validation": cfg["validation"],
        "cases": cases,
        "boundary": cfg["boundary"],
    }
    out = Path("analysis/phase3c")
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for case in cases:
        (out / f"{case['id']}.vspscript").write_text(script_for_case(cfg, wing, case))

    print(json.dumps({
        "case_count": len(cases),
        "sanity_case_count": sum(c["category"].startswith("sanity_") for c in cases),
        "grid_case_count": sum(c["category"] == "tail_volume_grid" for c in cases),
        "gross_cg_x_m": gross_cg,
        "wing_mac_m": wing["mean_aerodynamic_chord_m"],
        "grid_volume_range": [
            min(c["tail"]["horizontal_tail_volume_coefficient"] for c in cases if c["category"] == "tail_volume_grid"),
            max(c["tail"]["horizontal_tail_volume_coefficient"] for c in cases if c["category"] == "tail_volume_grid"),
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
