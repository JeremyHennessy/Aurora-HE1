#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path

from aurora_he1.geometry import chord_at_eta, solve_trapezoidal_wing


def trapezoid(area: float, ar: float, taper: float) -> dict[str, float]:
    span = math.sqrt(area * ar)
    root = 2.0 * area / (span * (1.0 + taper))
    tip = root * taper
    mac = (2.0 / 3.0) * root * (1.0 + taper + taper * taper) / (1.0 + taper)
    return {"area_m2": area, "aspect_ratio": ar, "taper_ratio": taper, "span_m": span, "root_chord_m": root, "tip_chord_m": tip, "mean_aerodynamic_chord_m": mac}


def main_wing_data(base: dict) -> dict:
    cfg = base["geometry"]["wing"]
    wing = solve_trapezoidal_wing(cfg["span_m"], cfg["area_m2"], cfg["taper_ratio"])
    etas = [0.0, 0.25, 0.50, 0.75, 1.0]
    tracked = {float(s["eta"]): s for s in cfg["airfoil_stations"]}
    stations = []
    for eta in etas:
        stations.append({"eta": eta, "chord_m": chord_at_eta(wing, eta), "twist_deg": float(tracked[eta]["twist_deg"])})
    section_span = wing.span_m / 8.0
    areas = [section_span * (stations[i - 1]["chord_m"] + stations[i]["chord_m"]) / 2.0 for i in range(1, len(stations))]
    return {
        "span_m": wing.span_m,
        "area_m2": wing.area_m2,
        "aspect_ratio": wing.aspect_ratio,
        "root_chord_m": wing.root_chord_m,
        "tip_chord_m": wing.tip_chord_m,
        "mean_aerodynamic_chord_m": wing.mean_aerodynamic_chord_m,
        "root_le_x_m": float(cfg["root_le_x_m"]),
        "incidence_deg": float(cfg["incidence_deg"]),
        "dihedral_deg": float(cfg["dihedral_deg"]),
        "stations": stations,
        "section_semispan_areas_m2": areas,
    }


def def_token(x: float) -> str:
    if abs(x) < 1e-9:
        return "Z00"
    return ("P" if x > 0 else "M") + f"{abs(int(round(x))):02d}"


def case_id(tail_id: str, span_fraction: float, deflection: float, cg_fraction: float) -> str:
    return f"{tail_id}_S{int(round(span_fraction*100)):02d}_D{def_token(deflection)}_CG{int(round(cg_fraction*100)):02d}"


def make_cases(cfg: dict) -> list[dict]:
    tails = {x["id"]: x for x in cfg["tail_candidates"]}
    cases: dict[str, dict] = {}

    def add(tail_id: str, span: float, de: float, cg: float, role: str):
        cid = case_id(tail_id, span, de, cg)
        entry = cases.setdefault(cid, {"id": cid, "tail_id": tail_id, "elevator_span_fraction": span, "deflection_deg": de, "cg_fraction_mac": cg, "roles": []})
        if role not in entry["roles"]:
            entry["roles"].append(role)

    # Architecture comparison: full deflection family at the middle elevator span.
    for tid in tails:
        for de in cfg["elevator"]["deflection_deg"]:
            add(tid, 0.85, float(de), 0.23, "architecture")

    # Elevator-span sensitivity on the MID tail. 85% cases above are reused.
    for span in cfg["elevator"]["span_fraction_candidates"]:
        for de in (-10.0, 0.0, 10.0):
            add("MID", float(span), de, 0.23, "span_sensitivity")

    # Direct moment-reference validation with identical neutral elevator geometry.
    for cg in (0.18, 0.28):
        add("MID", 0.85, 0.0, cg, "cg_validation")

    return list(cases.values())


def build_tail(raw: dict) -> dict:
    tail = trapezoid(float(raw["area_m2"]), float(raw["aspect_ratio"]), float(raw["taper_ratio"]))
    tail["quarter_mac_x_m"] = float(raw["tail_ac_x_m"])
    tail["root_le_x_m"] = tail["quarter_mac_x_m"] - 0.25 * tail["mean_aerodynamic_chord_m"]
    return tail


def script_for_case(cfg: dict, wing: dict, tail: dict, case: dict) -> str:
    cid = case["id"]
    span_fraction = float(case["elevator_span_fraction"])
    eta_gap = (1.0 - span_fraction) / 2.0
    eta_start, eta_end = eta_gap, 1.0 - eta_gap
    chord_fraction = float(cfg["elevator"]["provisional_chord_fraction"])
    de = float(case["deflection_deg"])
    cg_fraction = float(case["cg_fraction_mac"])
    xcg = wing["root_le_x_m"] + cg_fraction * wing["mean_aerodynamic_chord_m"]
    chords = [s["chord_m"] for s in wing["stations"]]
    twists = [wing["stations"][i]["twist_deg"] for i in range(1, 5)]
    a0, a1 = -4.0, 14.0
    na = 10

    L = [
        "void main()", "{", "    VSPCheckSetup();", "    VSPRenew();",
        '    string wing_id = AddGeom("WING", "");',
        '    SetGeomName(wing_id, "HE1MainWing");',
        '    SetParmVal(wing_id, "RelativeTwistFlag", "WingGeom", 0.0);',
        '    SetParmVal(wing_id, "RelativeDihedralFlag", "WingGeom", 0.0);',
        '    InsertXSec(wing_id, 1, XS_FOUR_SERIES);',
        '    InsertXSec(wing_id, 2, XS_FOUR_SERIES);',
        '    InsertXSec(wing_id, 3, XS_FOUR_SERIES);', "    Update();",
    ]
    for i in range(1, 5):
        L += [
            f"    SetDriverGroup(wing_id, {i}, AREA_WSECT_DRIVER, ROOTC_WSECT_DRIVER, TIPC_WSECT_DRIVER);",
            f'    SetParmVal(wing_id, "Root_Chord", "XSec_{i}", {chords[i-1]:.12f});',
            f'    SetParmVal(wing_id, "Tip_Chord", "XSec_{i}", {chords[i]:.12f});',
            f'    SetParmVal(wing_id, "Area", "XSec_{i}", {wing["section_semispan_areas_m2"][i-1]:.12f});',
            f'    SetParmVal(wing_id, "Sweep", "XSec_{i}", 0.0);',
            f'    SetParmVal(wing_id, "Sweep_Location", "XSec_{i}", 0.0);',
            f'    SetParmVal(wing_id, "Dihedral", "XSec_{i}", {wing["dihedral_deg"]:.12f});',
            f'    SetParmVal(wing_id, "Twist", "XSec_{i}", {twists[i-1]:.12f});',
            f'    SetParmVal(wing_id, "Twist_Location", "XSec_{i}", 0.25);',
            f'    SetParmVal(wing_id, "SectTess_U", "XSec_{i}", 16);', "    Update();",
        ]
    L += [
        f'    SetParmVal(wing_id, "X_Rel_Location", "XForm", {wing["root_le_x_m"]:.12f});',
        f'    SetParmVal(wing_id, "Y_Rel_Rotation", "XForm", {wing["incidence_deg"]:.12f});',
        '    SetParmVal(wing_id, "Tess_W", "Shape", 45);',
        '    string wing_xsurf = GetXSecSurf(wing_id, 0);',
        '    for (int j = 0; j < GetNumXSec(wing_xsurf); j++) { ChangeXSecShape(wing_xsurf, j, XS_FOUR_SERIES); string xid = GetXSec(wing_xsurf, j); SetParmVal(GetXSecParm(xid, "Camber"), 0.0); SetParmVal(GetXSecParm(xid, "ThickChord"), 0.01); }',
        '    Update();',
        '    string tail_id = AddGeom("WING", "");',
        f'    SetGeomName(tail_id, "HE1Tail{case["tail_id"]}");',
        '    SetParmVal(tail_id, "RelativeTwistFlag", "WingGeom", 0.0);',
        '    SetParmVal(tail_id, "RelativeDihedralFlag", "WingGeom", 0.0);',
        '    SetDriverGroup(tail_id, 1, AREA_WSECT_DRIVER, ROOTC_WSECT_DRIVER, TIPC_WSECT_DRIVER);',
        f'    SetParmVal(tail_id, "Root_Chord", "XSec_1", {tail["root_chord_m"]:.12f});',
        f'    SetParmVal(tail_id, "Tip_Chord", "XSec_1", {tail["tip_chord_m"]:.12f});',
        f'    SetParmVal(tail_id, "Area", "XSec_1", {tail["area_m2"]/2.0:.12f});',
        '    SetParmVal(tail_id, "Sweep", "XSec_1", 0.0);',
        '    SetParmVal(tail_id, "Sweep_Location", "XSec_1", 0.0);',
        '    SetParmVal(tail_id, "Dihedral", "XSec_1", 0.0);',
        '    SetParmVal(tail_id, "Twist", "XSec_1", 0.0);',
        f'    SetParmVal(tail_id, "X_Rel_Location", "XForm", {tail["root_le_x_m"]:.12f});',
        '    SetParmVal(tail_id, "Tess_W", "Shape", 35);',
        '    string tail_xsurf = GetXSecSurf(tail_id, 0);',
        '    for (int j = 0; j < GetNumXSec(tail_xsurf); j++) { ChangeXSecShape(tail_xsurf, j, XS_FOUR_SERIES); string xid = GetXSec(tail_xsurf, j); SetParmVal(GetXSecParm(xid, "Camber"), 0.0); SetParmVal(GetXSecParm(xid, "ThickChord"), 0.01); }',
        '    Update();',
        '    string cs_id = AddSubSurf(tail_id, SS_CONTROL);',
        f'    SetSubSurfName(cs_id, "Elevator{cid}");',
        '    array<string> pids = GetSubSurfParmIDs(cs_id);',
        '    int found_eta_flag=0; int found_eta_start=0; int found_eta_end=0; int found_absrel=0; int found_const=0; int found_lcs=0; int found_lce=0;',
        '    for (uint i=0; i<uint(pids.size()); i++) { string n=GetParmName(pids[i]); if(n=="EtaFlag"){SetParmValUpdate(pids[i],1.0);found_eta_flag=1;} else if(n=="EtaStart"){SetParmValUpdate(pids[i],'+f'{eta_start:.12f}'+');found_eta_start=1;} else if(n=="EtaEnd"){SetParmValUpdate(pids[i],'+f'{eta_end:.12f}'+');found_eta_end=1;} else if(n=="Abs_Rel_Flag"){SetParmValUpdate(pids[i],1.0);found_absrel=1;} else if(n=="SE_Const_Flag"){SetParmValUpdate(pids[i],1.0);found_const=1;} else if(n=="Length_C_Start"){SetParmValUpdate(pids[i],'+f'{chord_fraction:.12f}'+');found_lcs=1;} else if(n=="Length_C_End"){SetParmValUpdate(pids[i],'+f'{chord_fraction:.12f}'+');found_lce=1;} }',
        f'    Print("PHASE3D_CONTROL_FOUND|{cid}|", false); Print(found_eta_flag,false); Print("|",false); Print(found_eta_start,false); Print("|",false); Print(found_eta_end,false); Print("|",false); Print(found_absrel,false); Print("|",false); Print(found_const,false); Print("|",false); Print(found_lcs,false); Print("|",false); Print(found_lce);',
        '    Update(); AutoGroupVSPAEROControlSurfaces(); Update();',
        '    string settings = FindContainer("VSPAEROSettings", 0);',
        '    string def_id = FindParm(settings, "DeflectionAngle", "ControlSurfaceGroup_0");',
        '    string gain0_id = FindParm(settings, "Surf_" + cs_id + "_0_Gain", "ControlSurfaceGroup_0");',
        '    string gain1_id = FindParm(settings, "Surf_" + cs_id + "_1_Gain", "ControlSurfaceGroup_0");',
        f'    if (def_id.length()==0 || gain0_id.length()==0 || gain1_id.length()==0) {{ Print("PHASE3D_ERROR|{cid}|control group parm missing"); return; }}',
        '    SetParmValUpdate(gain0_id, 1.0); SetParmValUpdate(gain1_id, -1.0);',
        f'    SetParmValUpdate(def_id, {de:.12f});',
        f'    Print("PHASE3D_CASE|{cid}|{case["tail_id"]}|{span_fraction:.6f}|{chord_fraction:.6f}|{de:.6f}|{cg_fraction:.6f}|{xcg:.12f}");',
        f'    WriteVSPFile("analysis/phase3d/{cid}.vsp3", SET_ALL);',
        '    SetVSPAERORefWingID(wing_id);',
        '    string xcg_id = FindParm(settings, "Xcg", "VSPAERO");',
        f'    SetParmValUpdate(xcg_id, {xcg:.12f});',
        '    string cg_name="VSPAEROComputeGeometry"; SetAnalysisInputDefaults(cg_name);',
        '    array<int> cgt=GetIntAnalysisInput(cg_name,"GeomSet"); array<int> cgn=GetIntAnalysisInput(cg_name,"ThinGeomSet"); cgt[0]=SET_TYPE::SET_NONE; cgn[0]=SET_TYPE::SET_ALL; SetIntAnalysisInput(cg_name,"GeomSet",cgt); SetIntAnalysisInput(cg_name,"ThinGeomSet",cgn);',
        f'    if (ExecAnalysis(cg_name).length()==0) {{ Print("PHASE3D_ERROR|{cid}|compute geometry failed"); return; }}',
        '    string an="VSPAEROSweep"; SetAnalysisInputDefaults(an);',
        '    array<int> st=GetIntAnalysisInput(an,"GeomSet"); array<int> sn=GetIntAnalysisInput(an,"ThinGeomSet"); st[0]=SET_TYPE::SET_NONE; sn[0]=SET_TYPE::SET_ALL; SetIntAnalysisInput(an,"GeomSet",st); SetIntAnalysisInput(an,"ThinGeomSet",sn);',
        '    array<int> rf(1,0); SetIntAnalysisInput(an,"RefFlag",rf);',
        f'    array<double> sr(1,{wing["area_m2"]:.12f}); SetDoubleAnalysisInput(an,"Sref",sr);',
        f'    array<double> br(1,{wing["span_m"]:.12f}); SetDoubleAnalysisInput(an,"bref",br);',
        f'    array<double> cr(1,{wing["mean_aerodynamic_chord_m"]:.12f}); SetDoubleAnalysisInput(an,"cref",cr);',
        f'    array<double> asv(1,{a0:.12f}); array<double> aev(1,{a1:.12f}); array<int> anv(1,{na}); SetDoubleAnalysisInput(an,"AlphaStart",asv); SetDoubleAnalysisInput(an,"AlphaEnd",aev); SetIntAnalysisInput(an,"AlphaNpts",anv);',
        '    array<double> ms(1,0.03); array<double> me(1,0.03); array<int> mn(1,1); SetDoubleAnalysisInput(an,"MachStart",ms); SetDoubleAnalysisInput(an,"MachEnd",me); SetIntAnalysisInput(an,"MachNpts",mn);',
        f'    if (ExecAnalysis(an).length()==0) {{ Print("PHASE3D_ERROR|{cid}|sweep failed"); return; }}',
        f'    Print("PHASE3D_COMPLETE|{cid}");',
        '    while(GetNumTotalErrors()>0){ ErrorObj err=PopLastError(); Print("PHASE3D_API_ERROR|"+err.GetErrorString()); }',
        '}',
    ]
    return "\n".join(L) + "\n"


def main() -> None:
    base = json.loads(Path("config/he1_baseline.json").read_text())
    cfg = json.loads(Path("config/phase3d_elevator_trim.json").read_text())
    wing = main_wing_data(base)
    tail_defs = {x["id"]: build_tail(x) for x in cfg["tail_candidates"]}
    cases = make_cases(cfg)
    out = Path("analysis/phase3d")
    out.mkdir(parents=True, exist_ok=True)
    for c in cases:
        c["tail"] = tail_defs[c["tail_id"]]
        c["xcg_m"] = wing["root_le_x_m"] + float(c["cg_fraction_mac"]) * wing["mean_aerodynamic_chord_m"]
        (out / f"{c['id']}.vspscript").write_text(script_for_case(cfg, wing, c["tail"], c))
    manifest = {
        "status": cfg["status"], "source_main_sha": cfg["source_main_sha"], "toolchain": cfg["toolchain"],
        "main_wing": wing, "tail_candidates": cfg["tail_candidates"], "elevator": cfg["elevator"], "trim_screen": cfg["trim_screen"],
        "alpha_sweep_deg": [-4.0, 14.0], "alpha_points": 10, "cases": cases, "boundary": cfg["boundary"]
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"case_count": len(cases), "cases": [c["id"] for c in cases]}, indent=2))


if __name__ == "__main__":
    main()
