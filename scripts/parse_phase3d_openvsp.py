#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path


def linear_fit(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("linear fit requires paired samples")
    xm, ym = sum(xs)/len(xs), sum(ys)/len(ys)
    den = sum((x-xm)**2 for x in xs)
    if den <= 0:
        raise ValueError("zero x variance")
    slope = sum((x-xm)*(y-ym) for x,y in zip(xs,ys))/den
    intercept = ym - slope*xm
    ss_tot = sum((y-ym)**2 for y in ys)
    ss_res = sum((y-(slope*x+intercept))**2 for x,y in zip(xs,ys))
    r2 = 1.0 - ss_res/ss_tot if ss_tot > 1e-20 else 1.0
    return slope, intercept, r2


def parse_log(path: Path, cid: str) -> dict:
    lines=[x.strip() for x in path.read_text(errors="replace").splitlines()]
    errors=[x for x in lines if x.startswith("PHASE3D_ERROR|") or x.startswith("PHASE3D_API_ERROR|")]
    if errors:
        raise SystemExit(f"{cid}: explicit OpenVSP error: {'; '.join(errors)}")
    found=next((x for x in lines if x.startswith(f"PHASE3D_CONTROL_FOUND|{cid}|")),None)
    geom=next((x for x in lines if x.startswith(f"PHASE3D_CONTROL_GEOM|{cid}|")),None)
    case=next((x for x in lines if x.startswith(f"PHASE3D_CASE|{cid}|")),None)
    complete=f"PHASE3D_COMPLETE|{cid}" in lines
    if not found or not geom or not case or not complete:
        raise SystemExit(f"{cid}: missing required log evidence")
    f=[x.strip() for x in found.split("|")]
    if f[2:] != ["1"]*7:
        raise SystemExit(f"{cid}: control parameter contract incomplete: {f}")
    g=[x.strip() for x in geom.split("|")]
    if len(g) != 8:
        raise SystemExit(f"{cid}: malformed control geometry marker: {g}")
    c=[x.strip() for x in case.split("|")]
    return {
        "tail_id": c[2], "span_fraction": float(c[3]), "chord_fraction": float(c[4]),
        "deflection_deg": float(c[5]), "cg_fraction_mac": float(c[6]), "xcg_m": float(c[7]),
        "control_geometry": {
            "requested_eta_start": float(g[2]), "requested_eta_end": float(g[3]),
            "actual_eta_start": float(g[4]), "actual_eta_end": float(g[5]),
            "actual_chord_fraction_start": float(g[6]), "actual_chord_fraction_end": float(g[7]),
        },
    }


def parse_polar(path: Path) -> list[dict[str,float]]:
    lines=path.read_text(errors="replace").splitlines()
    header=None; start=None
    for i,line in enumerate(lines):
        f=line.split()
        if all(k in f for k in ("AoA","CLtot","CDi","CMytot")):
            header=f; start=i+1; break
    if header is None:
        raise SystemExit(f"{path}: polar header missing")
    idx={k:header.index(k) for k in ("AoA","CLtot","CDi","CMytot")}
    rows=[]
    for line in lines[start:]:
        f=line.split()
        if len(f)<len(header): continue
        try:
            row={"alpha_deg":float(f[idx["AoA"]]),"cl":float(f[idx["CLtot"]]),"cdi":float(f[idx["CDi"]]),"cm":float(f[idx["CMytot"]])}
        except (ValueError,IndexError):
            continue
        if all(math.isfinite(v) for v in row.values()): rows.append(row)
    rows.sort(key=lambda x:x["alpha_deg"])
    if not rows: raise SystemExit(f"{path}: no polar rows")
    return rows


def fitted(rows: list[dict]) -> dict:
    a_deg=[r["alpha_deg"] for r in rows]
    a_rad=[math.radians(x) for x in a_deg]
    cl=[r["cl"] for r in rows]; cm=[r["cm"] for r in rows]
    cla,cl0,r2cl=linear_fit(a_rad,cl)
    cma,cm0,r2cm=linear_fit(a_rad,cm)
    cmcl,cmcl0,r2cmcl=linear_fit(cl,cm)
    return {"cl_alpha_per_rad":cla,"cl0":cl0,"cm_alpha_per_rad":cma,"cm0":cm0,"dcm_dcl":cmcl,"cm_at_cl0":cmcl0,"static_margin_fraction_mac":-cmcl,"r2_cl_alpha":r2cl,"r2_cm_alpha":r2cm,"r2_cm_cl":r2cmcl}


def fitted_alpha_window(rows: list[dict], alpha_min: float, alpha_max: float) -> dict:
    selected=[r for r in rows if alpha_min-1e-9 <= float(r["alpha_deg"]) <= alpha_max+1e-9]
    if len(selected) < 3:
        raise ValueError(f"insufficient points in alpha window {alpha_min}..{alpha_max}")
    return fitted(selected)


def cm_alpha_at_cl(fit: dict, cl_req: float) -> tuple[float,float]:
    alpha_rad=(cl_req-fit["cl0"])/fit["cl_alpha_per_rad"]
    cm=fit["dcm_dcl"]*cl_req+fit["cm_at_cl0"]
    return cm, math.degrees(alpha_rad)


def main() -> None:
    root=Path("analysis/phase3d")
    manifest=json.loads((root/"manifest.json").read_text())
    base=json.loads(Path("config/he1_baseline.json").read_text())
    wing=manifest["main_wing"]
    cases=[]
    for meta in manifest["cases"]:
        cid=meta["id"]
        log=parse_log(root/f"{cid}.log",cid)
        rows=parse_polar(root/f"{cid}.polar")
        cases.append({**meta,"log":log,"point_count":len(rows),"points":rows,"fit":fitted(rows)})

    rho=float(base["environment"]["density_kg_m3"]); g=float(base["environment"]["gravity_m_s2"])
    mass=float(manifest["trim_screen"]["gross_mass_kg"]); S=float(wing["area_m2"])
    ref_cg=0.23
    by_geom: dict[tuple[str,float],list[dict]]={}
    for c in cases:
        if abs(float(c["cg_fraction_mac"])-ref_cg)<1e-9:
            by_geom.setdefault((c["tail_id"],float(c["elevator_span_fraction"])),[]).append(c)

    trim=[]
    for (tid,span), group in sorted(by_geom.items()):
        group=sorted(group,key=lambda c:float(c["deflection_deg"]))
        deltas=[float(c["deflection_deg"]) for c in group]
        if len(deltas)<3: continue
        for speed in [float(x) for x in manifest["trim_screen"]["speeds_m_s"]]:
            cl_req=mass*g/(0.5*rho*speed*speed*S)
            base_cm=[]; base_alpha=[]
            for c in group:
                cm,alpha=cm_alpha_at_cl(c["fit"],cl_req)
                base_cm.append(cm); base_alpha.append(alpha)
            for cg in [float(x) for x in manifest["trim_screen"]["cg_fraction_mac"]]:
                cm_target=[cm+cl_req*(cg-ref_cg) for cm in base_cm]
                slope,intercept,r2=linear_fit(deltas,cm_target)
                delta_trim=-intercept/slope if abs(slope)>1e-12 else None
                aslope,aintercept,ar2=linear_fit(deltas,base_alpha)
                alpha_trim=aslope*delta_trim+aintercept if delta_trim is not None else None
                trim.append({
                    "tail_id":tid,"elevator_span_fraction":span,"speed_m_s":speed,"cg_fraction_mac":cg,"required_cl":cl_req,
                    "dcm_ddeflection_per_deg":slope,"cm_vs_deflection_r2":r2,"alpha_vs_deflection_r2":ar2,
                    "trim_deflection_deg":delta_trim,"trim_alpha_deg":alpha_trim,
                    "within_tested_deflection_range":delta_trim is not None and min(deltas)<=delta_trim<=max(deltas),
                    "trim_alpha_inside_solver_sweep":alpha_trim is not None and manifest["alpha_sweep_deg"][0]<=alpha_trim<=manifest["alpha_sweep_deg"][1],
                    "tested_deflections_deg":deltas,
                })

    # Validate the moment-reference translation independently on the control-surface model.
    ref_case=next(c for c in cases if c["tail_id"]=="MID" and abs(c["elevator_span_fraction"]-0.85)<1e-9 and abs(c["deflection_deg"])<1e-9 and abs(c["cg_fraction_mac"]-0.23)<1e-9)
    cg_checks=[]
    for target in (0.18,0.28):
        actual=next(c for c in cases if c["tail_id"]=="MID" and abs(c["elevator_span_fraction"]-0.85)<1e-9 and abs(c["deflection_deg"])<1e-9 and abs(c["cg_fraction_mac"]-target)<1e-9)
        for cl_test in (0.8,1.0,1.2):
            cm_ref,_=cm_alpha_at_cl(ref_case["fit"],cl_test)
            cm_expected=cm_ref+cl_test*(target-ref_cg)
            cm_actual,_=cm_alpha_at_cl(actual["fit"],cl_test)
            cg_checks.append({"target_cg_fraction_mac":target,"cl":cl_test,"expected_cm":cm_expected,"actual_cm":cm_actual,"absolute_error":abs(cm_actual-cm_expected)})

    # Phase 3C's stability comparison used its common linear alpha range. Phase 3D
    # deliberately extends the sweep to 14 deg for trim screening; fitting that
    # broader curved range biases the apparent static margin. Compare like-for-like
    # on the shared -2..+6 deg window while retaining the full fit for trim work.
    neutral=[]
    phase3c_sm={x["id"]:float(x["phase3c_static_margin_fraction_mac"]) for x in manifest["tail_candidates"]}
    for tid in phase3c_sm:
        c=next(c for c in cases if c["tail_id"]==tid and abs(c["elevator_span_fraction"]-0.85)<1e-9 and abs(c["deflection_deg"])<1e-9 and abs(c["cg_fraction_mac"]-0.23)<1e-9)
        common_fit=fitted_alpha_window(c["points"],-2.0,6.0)
        sm=common_fit["static_margin_fraction_mac"]
        neutral.append({"tail_id":tid,"comparison_alpha_deg":[-2.0,6.0],"phase3c_static_margin_fraction_mac":phase3c_sm[tid],"phase3d_zero_elevator_static_margin_fraction_mac":sm,"absolute_difference":abs(sm-phase3c_sm[tid]),"common_window_fit":common_fit})

    out={
        "status":manifest["status"],"source_main_sha":manifest["source_main_sha"],"main_wing":wing,
        "case_count":len(cases),"cases":cases,"trim":trim,"cg_reference_validation":cg_checks,"neutral_static_margin_comparison":neutral,
        "boundary":manifest["boundary"],
    }
    (root/"results.json").write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps({"case_count":len(cases),"trim_rows":len(trim),"max_cg_transform_error":max(x["absolute_error"] for x in cg_checks)},indent=2))


if __name__=="__main__":
    main()
