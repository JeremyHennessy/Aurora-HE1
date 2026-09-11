#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path


def require(ok: bool, msg: str) -> None:
    if not ok:
        raise SystemExit(f"PHASE 3D VALIDATION FAILED: {msg}")


def main() -> None:
    cfg=json.loads(Path("config/phase3d_elevator_trim.json").read_text())
    results=json.loads(Path("analysis/phase3d/results.json").read_text())
    cases=results["cases"]
    require(len(cases)==23, f"expected 23 unique solver cases, found {len(cases)}")
    require(results["source_main_sha"]==cfg["source_main_sha"], "source main SHA drifted")

    for c in cases:
        cid=c["id"]
        require(c["point_count"]==10, f"{cid}: expected 10 alpha points")
        require(abs(float(c["log"]["span_fraction"])-float(c["elevator_span_fraction"]))<1e-9, f"{cid}: span marker mismatch")
        require(abs(float(c["log"]["chord_fraction"])-0.30)<1e-9, f"{cid}: elevator chord marker mismatch")
        require(abs(float(c["log"]["deflection_deg"])-float(c["deflection_deg"]))<1e-9, f"{cid}: deflection marker mismatch")
        require(abs(float(c["log"]["cg_fraction_mac"])-float(c["cg_fraction_mac"]))<1e-9, f"{cid}: CG marker mismatch")
        require(all(math.isfinite(float(p[k])) for p in c["points"] for k in ("alpha_deg","cl","cdi","cm")), f"{cid}: nonfinite polar value")
        require(all(float(p["cdi"])>=0 for p in c["points"]), f"{cid}: negative induced drag")
        f=c["fit"]
        require(float(f["cl_alpha_per_rad"])>0, f"{cid}: nonpositive lift-curve slope")
        require(float(f["r2_cl_alpha"])>0.995, f"{cid}: CL-alpha fit unexpectedly nonlinear")
        require(float(f["r2_cm_alpha"])>0.995, f"{cid}: Cm-alpha fit unexpectedly nonlinear")
        require(float(f["r2_cm_cl"])>0.995, f"{cid}: Cm-CL fit unexpectedly nonlinear")

    # Neutral elevator should preserve the Phase 3C static-margin result closely.
    for x in results["neutral_static_margin_comparison"]:
        require(float(x["absolute_difference"])<0.006, f"{x['tail_id']}: zero-elevator static margin differs too much from Phase 3C: {x}")

    # The moment-reference transformation was already validated in Phase 3C;
    # verify it remains valid after introducing an explicit control sub-surface.
    max_cg=max(float(x["absolute_error"]) for x in results["cg_reference_validation"])
    require(max_cg<0.003, f"CG moment-reference transformation error too large: {max_cg}")

    trims=results["trim"]
    require(len(trims)==45, f"expected 45 trim-screen rows, found {len(trims)}")
    for t in trims:
        require(math.isfinite(float(t["required_cl"])), "nonfinite required CL")
        require(math.isfinite(float(t["dcm_ddeflection_per_deg"])) and abs(float(t["dcm_ddeflection_per_deg"]))>1e-5, f"{t['tail_id']} S{t['elevator_span_fraction']}: negligible elevator authority")
        require(float(t["cm_vs_deflection_r2"])>0.97, f"{t['tail_id']} S{t['elevator_span_fraction']}: poor Cm-vs-deflection linearity")
        require(t["trim_deflection_deg"] is not None and math.isfinite(float(t["trim_deflection_deg"])), "nonfinite trim deflection")
        require(t["trim_alpha_deg"] is not None and math.isfinite(float(t["trim_alpha_deg"])), "nonfinite trim alpha")
        # At cruise and 11 m/s the fitted trim alpha should remain within the actual VLM sweep.
        if float(t["speed_m_s"])>=9.5:
            require(bool(t["trim_alpha_inside_solver_sweep"]), f"{t['tail_id']} {t['speed_m_s']}m/s CG{t['cg_fraction_mac']}: trim alpha outside solver sweep")

    # Elevator span sensitivity: larger span should materially increase pitch authority at cruise.
    mid=[t for t in trims if t["tail_id"]=="MID" and abs(float(t["speed_m_s"])-9.5)<1e-9 and abs(float(t["cg_fraction_mac"])-0.23)<1e-9]
    authority={round(float(t["elevator_span_fraction"]),2):abs(float(t["dcm_ddeflection_per_deg"])) for t in mid}
    require(set(authority)=={0.70,0.85,1.00}, f"missing MID span sensitivity rows: {authority}")
    require(authority[1.00] > authority[0.70]*1.05, f"full-span elevator does not show greater authority than 70% span: {authority}")

    architecture=[t for t in trims if abs(float(t["elevator_span_fraction"])-0.85)<1e-9]
    within=sum(1 for t in architecture if t["within_tested_deflection_range"])
    cruise=[t for t in architecture if abs(float(t["speed_m_s"])-9.5)<1e-9]
    ranking=sorted(cruise,key=lambda t:abs(float(t["trim_deflection_deg"])))
    summary={
        "status":cfg["status"],
        "case_count":len(cases),
        "trim_row_count":len(trims),
        "max_cg_transform_error":max_cg,
        "mid_span_authority_abs_dcm_ddeg_at_9p5":authority,
        "architecture_trim_rows_within_tested_20deg":within,
        "cruise_reference_cg_ranking_by_abs_trim_deflection":[{"tail_id":t["tail_id"],"trim_deflection_deg":t["trim_deflection_deg"],"trim_alpha_deg":t["trim_alpha_deg"]} for t in ranking if abs(float(t["cg_fraction_mac"])-0.23)<1e-9],
        "boundary":cfg["boundary"],
    }
    Path("analysis/phase3d/validation_summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print("PHASE 3D VALIDATION PASSED")
    print(json.dumps(summary,indent=2))


if __name__=="__main__":
    main()
