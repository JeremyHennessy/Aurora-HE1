#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from aurora_he1.geometry import chord_at_eta, solve_trapezoidal_wing


def main() -> None:
    base = json.loads(Path("config/he1_baseline.json").read_text())
    cfg = json.loads(Path("config/phase3a_openvsp.json").read_text())
    wing_cfg = base["geometry"]["wing"]
    wing = solve_trapezoidal_wing(wing_cfg["span_m"], wing_cfg["area_m2"], wing_cfg["taper_ratio"])
    eta = [float(x) for x in cfg["wing_station_eta"]]
    if eta != [0.0, 0.25, 0.5, 0.75, 1.0]:
        raise SystemExit("Phase 3A currently requires the five tracked quarter-span stations")
    tracked = {float(s["eta"]): s for s in wing_cfg["airfoil_stations"]}
    stations = []
    for x in eta:
        s = tracked[x]
        stations.append({
            "eta": x,
            "semi_span_y_m": x * wing.span_m / 2.0,
            "chord_m": chord_at_eta(wing, x),
            "twist_deg": float(s["twist_deg"]),
            "airfoil_label": s["airfoil"],
        })
    segment_span = wing.span_m / 2.0 / (len(eta) - 1)
    section_areas = [segment_span * (stations[i - 1]["chord_m"] + stations[i]["chord_m"]) / 2.0 for i in range(1, len(stations))]
    if abs(2.0 * sum(section_areas) - wing.area_m2) > 1e-10:
        raise SystemExit("derived OpenVSP section areas do not close to baseline wing area")

    manifest = {
        "status": cfg["status"],
        "source_baseline": "config/he1_baseline.json",
        "toolchain": cfg["toolchain"],
        "scope": cfg["scope"],
        "analysis": cfg["analysis"],
        "wing": {
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
            "vspaero_surface_model": "thin symmetric four-series sections; planform/dihedral/incidence/twist authoritative, viscous airfoil drag excluded",
        },
        "boundary": cfg["boundary"],
    }
    out = Path("analysis/phase3a")
    out.mkdir(parents=True, exist_ok=True)
    (out / "geometry_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    twists = [stations[i]["twist_deg"] for i in range(1, len(stations))]
    chords = [s["chord_m"] for s in stations]
    a = cfg["analysis"]
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
            f'    SetParmVal(wing_id, "Root_Chord", "XSec_{i}", {chords[i-1]:.12f});',
            f'    SetParmVal(wing_id, "Tip_Chord", "XSec_{i}", {chords[i]:.12f});',
            f'    SetParmVal(wing_id, "Area", "XSec_{i}", {section_areas[i-1]:.12f});',
            f'    SetParmVal(wing_id, "Sweep", "XSec_{i}", 0.0);',
            f'    SetParmVal(wing_id, "Sweep_Location", "XSec_{i}", 0.0);',
            f'    SetParmVal(wing_id, "Dihedral", "XSec_{i}", {float(wing_cfg["dihedral_deg"]):.12f});',
            f'    SetParmVal(wing_id, "Twist", "XSec_{i}", {twists[i-1]:.12f});',
            f'    SetParmVal(wing_id, "Twist_Location", "XSec_{i}", 0.25);',
            f'    SetParmVal(wing_id, "SectTess_U", "XSec_{i}", 16);',
            "    Update();",
        ]
    lines += [
        f'    SetParmVal(wing_id, "X_Rel_Location", "XForm", {float(wing_cfg["root_le_x_m"]):.12f});',
        f'    SetParmVal(wing_id, "Y_Rel_Rotation", "XForm", {float(wing_cfg["incidence_deg"]):.12f});',
        '    SetParmVal(wing_id, "Tess_W", "Shape", 45);',
        "    Update();",
        "    string xsurf = GetXSecSurf(wing_id, 0);",
        "    for (int j = 0; j < GetNumXSec(xsurf); j++)",
        "    {",
        "        ChangeXSecShape(xsurf, j, XS_FOUR_SERIES);",
        "        string xid = GetXSec(xsurf, j);",
        '        SetParmVal(GetXSecParm(xid, "Camber"), 0.0);',
        '        SetParmVal(GetXSecParm(xid, "ThickChord"), 0.01);',
        "    }",
        "    Update();",
        '    WriteVSPFile("analysis/phase3a/AURORA_HE1_phase3a.vsp3", SET_ALL);',
        '    Print("PHASE3A_VERSION|", false); Print(GetVSPVersion());',
        '    Print("PHASE3A_GEOM|", false);',
        '    Print(GetParmVal(wing_id, "TotalSpan", "WingGeom"), false); Print("|", false);',
        '    Print(GetParmVal(wing_id, "TotalArea", "WingGeom"), false); Print("|", false);',
        '    Print(GetParmVal(wing_id, "Root_Chord", "XSec_1"), false); Print("|", false);',
        '    Print(GetParmVal(wing_id, "Tip_Chord", "XSec_4"));',
        '    Print("PHASE3A_SECTION_SPANS|", false);',
        '    Print(GetParmVal(wing_id, "Span", "XSec_1"), false); Print("|", false);',
        '    Print(GetParmVal(wing_id, "Span", "XSec_2"), false); Print("|", false);',
        '    Print(GetParmVal(wing_id, "Span", "XSec_3"), false); Print("|", false);',
        '    Print(GetParmVal(wing_id, "Span", "XSec_4"));',
        '    string cg_name = "VSPAEROComputeGeometry";',
        '    SetAnalysisInputDefaults(cg_name);',
        '    array<int> cg_thick = GetIntAnalysisInput(cg_name, "GeomSet");',
        '    array<int> cg_thin = GetIntAnalysisInput(cg_name, "ThinGeomSet");',
        '    if (cg_thick.size() == 0 || cg_thin.size() == 0) { Print("PHASE3A_ERROR|compute-geometry set inputs missing"); return; }',
        '    cg_thick[0] = SET_TYPE::SET_NONE;',
        '    cg_thin[0] = SET_TYPE::SET_ALL;',
        '    SetIntAnalysisInput(cg_name, "GeomSet", cg_thick);',
        '    SetIntAnalysisInput(cg_name, "ThinGeomSet", cg_thin);',
        '    string cg_res = ExecAnalysis(cg_name);',
        '    if (cg_res.length() == 0) { Print("PHASE3A_ERROR|VSPAEROComputeGeometry returned no result"); return; }',
        '    string analysis_name = "VSPAEROSweep";',
        '    SetAnalysisInputDefaults(analysis_name);',
        '    array<int> sweep_thick = GetIntAnalysisInput(analysis_name, "GeomSet");',
        '    array<int> sweep_thin = GetIntAnalysisInput(analysis_name, "ThinGeomSet");',
        '    if (sweep_thick.size() == 0 || sweep_thin.size() == 0) { Print("PHASE3A_ERROR|sweep set inputs missing"); return; }',
        '    sweep_thick[0] = SET_TYPE::SET_NONE;',
        '    sweep_thin[0] = SET_TYPE::SET_ALL;',
        '    SetIntAnalysisInput(analysis_name, "GeomSet", sweep_thick);',
        '    SetIntAnalysisInput(analysis_name, "ThinGeomSet", sweep_thin);',
        '    array<int> ref_flag(1, 1); SetIntAnalysisInput(analysis_name, "RefFlag", ref_flag);',
        '    array<string> wing_ids(1, wing_id); SetStringAnalysisInput(analysis_name, "WingID", wing_ids);',
        f'    array<double> alpha_start(1, {float(a["alpha_start_deg"]):.12f}); SetDoubleAnalysisInput(analysis_name, "AlphaStart", alpha_start);',
        f'    array<double> alpha_end(1, {float(a["alpha_end_deg"]):.12f}); SetDoubleAnalysisInput(analysis_name, "AlphaEnd", alpha_end);',
        f'    array<int> alpha_n(1, {n_alpha}); SetIntAnalysisInput(analysis_name, "AlphaNpts", alpha_n);',
        f'    array<double> mach_start(1, {float(a["mach"]):.12f}); SetDoubleAnalysisInput(analysis_name, "MachStart", mach_start);',
        f'    array<double> mach_end(1, {float(a["mach"]):.12f}); SetDoubleAnalysisInput(analysis_name, "MachEnd", mach_end);',
        '    array<int> mach_n(1, 1); SetIntAnalysisInput(analysis_name, "MachNpts", mach_n);',
        "    Update();",
        '    string sweep_res = ExecAnalysis(analysis_name);',
        '    if (sweep_res.length() == 0) { Print("PHASE3A_ERROR|VSPAEROSweep returned no result"); return; }',
        f'    Print("PHASE3A_COUNT|{n_alpha}");',
        f'    for (int k = 0; k < {n_alpha}; k++)',
        "    {",
        '        string hist = FindResultsID("VSPAERO_History", k);',
        '        if (hist.length() == 0) { Print("PHASE3A_ERROR|missing VSPAERO_History result"); return; }',
        '        array<double> al = GetDoubleResults(hist, "Alpha", 0);',
        '        array<double> cl = GetDoubleResults(hist, "CL", 0);',
        '        array<double> cdi = GetDoubleResults(hist, "CDi", 0);',
        '        if (al.size() == 0 || cl.size() == 0 || cdi.size() == 0) { Print("PHASE3A_ERROR|history coefficient result missing"); return; }',
        '        Print("PHASE3A_POINT|", false);',
        '        Print(al[al.size()-1], false); Print("|", false);',
        '        Print(cl[cl.size()-1], false); Print("|", false);',
        '        Print(cdi[cdi.size()-1]);',
        "    }",
        "    while (GetNumTotalErrors() > 0)",
        "    {",
        "        ErrorObj err = PopLastError();",
        '        Print("PHASE3A_API_ERROR|" + err.GetErrorString());',
        "    }",
        "}",
    ]
    (out / "aurora_phase3a.vspscript").write_text("\n".join(lines) + "\n")
    print(json.dumps({"span_m": wing.span_m, "area_m2": wing.area_m2, "segments": 4, "segment_area_m2": section_areas, "script": str(out / "aurora_phase3a.vspscript")}, indent=2))


if __name__ == "__main__":
    main()
