#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from aurora_he1.geometry import chord_at_eta, solve_trapezoidal_wing


def baseline_cg(base: dict) -> float:
    items = base["mass"]["items"]
    pilot_mass = float(base["mass"]["reference_pilot_and_personal_gear_kg"])
    pilot_x = float(base["mass"]["reference_pilot_cg_x_m"])
    gross_mass = sum(float(x["mass_kg"]) for x in items) + pilot_mass
    gross_moment = sum(float(x["mass_kg"]) * float(x["x_m"]) for x in items) + pilot_mass * pilot_x
    return gross_moment / gross_mass


def main_wing_data(base: dict) -> dict:
    cfg = base["geometry"]["wing"]
    wing = solve_trapezoidal_wing(cfg["span_m"], cfg["area_m2"], cfg["taper_ratio"])
    etas = [0.0, 0.25, 0.50, 0.75, 1.0]
    tracked = {float(s["eta"]): s for s in cfg["airfoil_stations"]}
    stations = []
    for eta in etas:
        stations.append({
            "eta": eta,
            "semi_span_y_m": eta * wing.span_m / 2.0,
            "chord_m": chord_at_eta(wing, eta),
            "twist_deg": float(tracked[eta]["twist_deg"]),
        })
    semisection_span = wing.span_m / 8.0
    areas = [
        semisection_span * (stations[i - 1]["chord_m"] + stations[i]["chord_m"]) / 2.0
        for i in range(1, len(stations))
    ]
    return {
        "span_m": wing.span_m,
        "semi_span_m": wing.span_m / 2.0,
        "area_m2": wing.area_m2,
        "aspect_ratio": wing.aspect_ratio,
        "root_chord_m": wing.root_chord_m,
        "tip_chord_m": wing.tip_chord_m,
        "mean_aerodynamic_chord_m": wing.mean_aerodynamic_chord_m,
        "taper_ratio": wing.taper_ratio,
        "root_le_x_m": float(cfg["root_le_x_m"]),
        "incidence_deg": float(cfg["incidence_deg"]),
        "dihedral_deg": float(cfg["dihedral_deg"]),
        "section_semispan_areas_m2": areas,
        "stations": stations,
    }


def make_script(cfg: dict, wing: dict, xcg: float) -> str:
    alphas = [float(x) for x in cfg["aero_load_shape"]["alpha_deg"]]
    chords = [s["chord_m"] for s in wing["stations"]]
    twists = [wing["stations"][i]["twist_deg"] for i in range(1, 5)]
    lines = [
        "void main()",
        "{",
        "    VSPCheckSetup();",
        "    VSPRenew();",
        '    string wing_id = AddGeom("WING", "");',
        '    SetGeomName(wing_id, "AURORA_HE1_Phase4A_MainWing");',
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
            f'    SetParmVal(wing_id, "Root_Chord", "XSec_{i}", {chords[i-1]:.12f});',
            f'    SetParmVal(wing_id, "Tip_Chord", "XSec_{i}", {chords[i]:.12f});',
            f'    SetParmVal(wing_id, "Area", "XSec_{i}", {wing["section_semispan_areas_m2"][i-1]:.12f});',
            f'    SetParmVal(wing_id, "Sweep", "XSec_{i}", 0.0);',
            f'    SetParmVal(wing_id, "Sweep_Location", "XSec_{i}", 0.0);',
            f'    SetParmVal(wing_id, "Dihedral", "XSec_{i}", {wing["dihedral_deg"]:.12f});',
            f'    SetParmVal(wing_id, "Twist", "XSec_{i}", {twists[i-1]:.12f});',
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
        '    WriteVSPFile("analysis/phase4a/WING_LOAD.vsp3", SET_ALL);',
        '    SetVSPAERORefWingID(wing_id);',
        '    string settings = FindContainer("VSPAEROSettings", 0);',
        '    if (settings.length() == 0) { Print("PHASE4A_ERROR|VSPAEROSettings container missing"); return; }',
        '    string xcg_id = FindParm(settings, "Xcg", "VSPAERO");',
        f'    SetParmValUpdate(xcg_id, {xcg:.12f});',
        '    Print("PHASE4A_VERSION|", false); Print(GetVSPVersion());',
        '    Print("PHASE4A_MAIN_GEOM|", false);',
        '    Print(GetParmVal(wing_id, "TotalSpan", "WingGeom"), false); Print("|", false);',
        '    Print(GetParmVal(wing_id, "TotalArea", "WingGeom"), false); Print("|", false);',
        '    Print(GetParmVal(wing_id, "Root_Chord", "XSec_1"), false); Print("|", false);',
        '    Print(GetParmVal(wing_id, "Tip_Chord", "XSec_4"));',
        '    string cg_name = "VSPAEROComputeGeometry";',
        '    SetAnalysisInputDefaults(cg_name);',
        '    array<int> cg_thick = GetIntAnalysisInput(cg_name, "GeomSet");',
        '    array<int> cg_thin = GetIntAnalysisInput(cg_name, "ThinGeomSet");',
        '    cg_thick[0] = SET_TYPE::SET_NONE;',
        '    cg_thin[0] = SET_TYPE::SET_ALL;',
        '    SetIntAnalysisInput(cg_name, "GeomSet", cg_thick);',
        '    SetIntAnalysisInput(cg_name, "ThinGeomSet", cg_thin);',
        '    string cg_res = ExecAnalysis(cg_name);',
        '    if (cg_res.length() == 0) { Print("PHASE4A_ERROR|VSPAEROComputeGeometry returned no result"); return; }',
        '    string analysis_name = "VSPAEROSweep";',
        '    SetAnalysisInputDefaults(analysis_name);',
        '    array<int> sweep_thick = GetIntAnalysisInput(analysis_name, "GeomSet");',
        '    array<int> sweep_thin = GetIntAnalysisInput(analysis_name, "ThinGeomSet");',
        '    sweep_thick[0] = SET_TYPE::SET_NONE;',
        '    sweep_thin[0] = SET_TYPE::SET_ALL;',
        '    SetIntAnalysisInput(analysis_name, "GeomSet", sweep_thick);',
        '    SetIntAnalysisInput(analysis_name, "ThinGeomSet", sweep_thin);',
        '    array<int> ref_flag(1, 0); SetIntAnalysisInput(analysis_name, "RefFlag", ref_flag);',
        f'    array<double> sref(1, {wing["area_m2"]:.12f}); SetDoubleAnalysisInput(analysis_name, "Sref", sref);',
        f'    array<double> bref(1, {wing["span_m"]:.12f}); SetDoubleAnalysisInput(analysis_name, "bref", bref);',
        f'    array<double> cref(1, {wing["mean_aerodynamic_chord_m"]:.12f}); SetDoubleAnalysisInput(analysis_name, "cref", cref);',
        f'    array<double> alpha_start(1, {alphas[0]:.12f}); SetDoubleAnalysisInput(analysis_name, "AlphaStart", alpha_start);',
        f'    array<double> alpha_end(1, {alphas[-1]:.12f}); SetDoubleAnalysisInput(analysis_name, "AlphaEnd", alpha_end);',
        f'    array<int> alpha_n(1, {len(alphas)}); SetIntAnalysisInput(analysis_name, "AlphaNpts", alpha_n);',
        f'    array<double> mach_start(1, {float(cfg["aero_load_shape"]["mach"]):.12f}); SetDoubleAnalysisInput(analysis_name, "MachStart", mach_start);',
        f'    array<double> mach_end(1, {float(cfg["aero_load_shape"]["mach"]):.12f}); SetDoubleAnalysisInput(analysis_name, "MachEnd", mach_end);',
        '    array<int> mach_n(1, 1); SetIntAnalysisInput(analysis_name, "MachNpts", mach_n);',
        '    string sweep_res = ExecAnalysis(analysis_name);',
        '    if (sweep_res.length() == 0) { Print("PHASE4A_ERROR|VSPAEROSweep returned no result"); return; }',
        '    Print("PHASE4A_LOD|analysis/phase4a/WING_LOAD.lod");',
        '    Print("PHASE4A_COMPLETE");',
        "    while (GetNumTotalErrors() > 0)",
        "    {",
        "        ErrorObj err = PopLastError();",
        '        Print("PHASE4A_API_ERROR|" + err.GetErrorString());',
        "    }",
        "}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    base = json.loads(Path("config/he1_baseline.json").read_text())
    cfg = json.loads(Path("config/phase4a_structural_loads.json").read_text())
    wing = main_wing_data(base)
    xcg = baseline_cg(base)
    manifest = {
        "status": cfg["status"],
        "source_phase3c_main_sha": cfg["source_phase3c_main_sha"],
        "source_baseline": "config/he1_baseline.json",
        "toolchain": cfg["toolchain"],
        "aero_load_shape": cfg["aero_load_shape"],
        "structural_concept": cfg["structural_concept"],
        "screening_only": cfg["screening_only"],
        "validation": cfg["validation"],
        "main_wing": wing,
        "reference_gross_cg_x_m": xcg,
        "boundary": cfg["boundary"],
    }
    out = Path("analysis/phase4a")
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out / "WING_LOAD.vspscript").write_text(make_script(cfg, wing, xcg))
    print(json.dumps({"span_m": wing["span_m"], "alphas_deg": cfg["aero_load_shape"]["alpha_deg"], "gross_cg_x_m": xcg}, indent=2))


if __name__ == "__main__":
    main()
