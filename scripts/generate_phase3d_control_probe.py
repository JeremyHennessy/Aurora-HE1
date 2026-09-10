#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path


def trapezoid(area: float, ar: float, taper: float) -> dict[str, float]:
    span = math.sqrt(area * ar)
    root = 2.0 * area / (span * (1.0 + taper))
    tip = root * taper
    mac = (2.0 / 3.0) * root * (1.0 + taper + taper * taper) / (1.0 + taper)
    return {"span_m": span, "root_chord_m": root, "tip_chord_m": tip, "mac_m": mac}


def main() -> None:
    cfg = json.loads(Path("config/phase3d_elevator_trim.json").read_text())
    raw = next(x for x in cfg["tail_candidates"] if x["id"] == cfg["probe"]["tail_candidate"])
    tail = trapezoid(float(raw["area_m2"]), float(raw["aspect_ratio"]), float(raw["taper_ratio"]))
    root_le = float(raw["tail_ac_x_m"]) - 0.25 * tail["mac_m"]
    eta_start = float(cfg["probe"]["eta_start"])
    eta_end = float(cfg["probe"]["eta_end"])
    chord_fraction = float(cfg["elevator"]["provisional_chord_fraction"])
    c_start = chord_fraction * tail["root_chord_m"]
    c_end = chord_fraction * tail["tip_chord_m"]
    test_def = float(cfg["probe"]["test_deflection_deg"])

    script = f'''void main()
{{
    VSPCheckSetup();
    VSPRenew();
    string tail_id = AddGeom("WING", "");
    SetGeomName(tail_id, "HE1ProbeTail");
    SetParmVal(tail_id, "RelativeTwistFlag", "WingGeom", 0.0);
    SetParmVal(tail_id, "RelativeDihedralFlag", "WingGeom", 0.0);
    SetDriverGroup(tail_id, 1, AREA_WSECT_DRIVER, ROOTC_WSECT_DRIVER, TIPC_WSECT_DRIVER);
    SetParmVal(tail_id, "Root_Chord", "XSec_1", {tail['root_chord_m']:.12f});
    SetParmVal(tail_id, "Tip_Chord", "XSec_1", {tail['tip_chord_m']:.12f});
    SetParmVal(tail_id, "Area", "XSec_1", {float(raw['area_m2'])/2.0:.12f});
    SetParmVal(tail_id, "Sweep", "XSec_1", 0.0);
    SetParmVal(tail_id, "Sweep_Location", "XSec_1", 0.0);
    SetParmVal(tail_id, "Dihedral", "XSec_1", 0.0);
    SetParmVal(tail_id, "Twist", "XSec_1", 0.0);
    SetParmVal(tail_id, "X_Rel_Location", "XForm", {root_le:.12f});
    SetParmVal(tail_id, "Tess_W", "Shape", 35);
    Update();

    string cs_id = AddSubSurf(tail_id, SS_CONTROL);
    if (cs_id.length() == 0 || cs_id == "NONE") {{ Print("PHASE3D_PROBE_ERROR|AddSubSurf failed"); return; }}
    SetSubSurfName(cs_id, "ElevatorProbe");
    array<string> pids = GetSubSurfParmIDs(cs_id);
    Print("PHASE3D_PROBE_SUBSURF_ID|" + cs_id);
    Print("PHASE3D_PROBE_PARM_COUNT|", false); Print(int(pids.size()));
    int found_eta_flag = 0;
    int found_eta_start = 0;
    int found_eta_end = 0;
    int found_len_start = 0;
    int found_len_end = 0;
    for (uint i = 0; i < uint(pids.size()); i++)
    {{
        string name = GetParmName(pids[i]);
        string group = GetParmDisplayGroupName(pids[i]);
        Print("PHASE3D_PROBE_PARM|" + name + "|" + group + "|", false); Print(GetParmVal(pids[i]));
        if (name == "EtaFlag") {{ SetParmValUpdate(pids[i], 1.0); found_eta_flag = 1; }}
        else if (name == "EtaStart") {{ SetParmValUpdate(pids[i], {eta_start:.12f}); found_eta_start = 1; }}
        else if (name == "EtaEnd") {{ SetParmValUpdate(pids[i], {eta_end:.12f}); found_eta_end = 1; }}
        else if (name == "Length_C_Start") {{ SetParmValUpdate(pids[i], {c_start:.12f}); found_len_start = 1; }}
        else if (name == "Length_C_End") {{ SetParmValUpdate(pids[i], {c_end:.12f}); found_len_end = 1; }}
    }}
    Print("PHASE3D_PROBE_FOUND|", false); Print(found_eta_flag, false); Print("|", false); Print(found_eta_start, false); Print("|", false); Print(found_eta_end, false); Print("|", false); Print(found_len_start, false); Print("|", false); Print(found_len_end);
    Update();

    AutoGroupVSPAEROControlSurfaces();
    Update();
    int ng = GetNumControlSurfaceGroups();
    Print("PHASE3D_PROBE_GROUP_COUNT|", false); Print(ng);
    string settings = FindContainer("VSPAEROSettings", 0);
    if (settings.length() == 0) {{ Print("PHASE3D_PROBE_ERROR|VSPAEROSettings missing"); return; }}
    string def_id = FindParm(settings, "DeflectionAngle", "ControlSurfaceGroup_0");
    string gain0_id = FindParm(settings, "Surf_" + cs_id + "_0_Gain", "ControlSurfaceGroup_0");
    string gain1_id = FindParm(settings, "Surf_" + cs_id + "_1_Gain", "ControlSurfaceGroup_0");
    Print("PHASE3D_PROBE_GROUP_IDS|" + def_id + "|" + gain0_id + "|" + gain1_id);
    if (def_id.length() == 0 || gain0_id.length() == 0 || gain1_id.length() == 0) {{ Print("PHASE3D_PROBE_ERROR|control group parm missing"); return; }}
    SetParmValUpdate(gain0_id, 1.0);
    SetParmValUpdate(gain1_id, -1.0);
    SetParmValUpdate(def_id, {test_def:.12f});
    Print("PHASE3D_PROBE_GROUP_VALUES|", false); Print(GetParmVal(def_id), false); Print("|", false); Print(GetParmVal(gain0_id), false); Print("|", false); Print(GetParmVal(gain1_id));
    WriteVSPFile("analysis/phase3d_probe/control_probe.vsp3", SET_ALL);
    Print("PHASE3D_PROBE_COMPLETE");
    while (GetNumTotalErrors() > 0)
    {{
        ErrorObj err = PopLastError();
        Print("PHASE3D_PROBE_API_ERROR|" + err.GetErrorString());
    }}
}}
'''
    out = Path("analysis/phase3d_probe")
    out.mkdir(parents=True, exist_ok=True)
    (out / "control_probe.vspscript").write_text(script)
    manifest = {
        "status": cfg["status"],
        "tail": {**raw, **tail, "root_le_x_m": root_le},
        "requested": {
            "eta_start": eta_start,
            "eta_end": eta_end,
            "elevator_chord_fraction": chord_fraction,
            "length_c_start_m": c_start,
            "length_c_end_m": c_end,
            "test_deflection_deg": test_def,
        },
        "boundary": cfg["boundary"],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest["requested"], indent=2))


if __name__ == "__main__":
    main()
