#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from aurora_he1.polars import read_xfoil_polar, write_polar_csv


def xfoil_input(airfoil_path: Path, polar_path: Path, reynolds: int, cfg: dict) -> str:
    alpha_start = float(cfg["alpha_start_deg"])
    alpha_end = float(cfg["alpha_end_deg"])
    alpha_step = abs(float(cfg["alpha_step_deg"]))
    return f"""PLOP
G F

LOAD {airfoil_path}
PANE
OPER
VISC {reynolds}
ITER {int(cfg['iteration_limit'])}
VPAR
N {float(cfg['ncrit'])}

PACC
{polar_path}

ALFA 0.0
ASEQ {alpha_step} {alpha_end} {alpha_step}
INIT
ALFA 0.0
ASEQ {-alpha_step} {alpha_start} {-alpha_step}
PACC

QUIT
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/airfoil_sources.json")
    parser.add_argument("--airfoils", default="analysis/airfoils")
    parser.add_argument("--output", default="analysis/polars")
    args = parser.parse_args()

    exe = shutil.which("xfoil")
    if not exe:
        raise RuntimeError("xfoil executable not found")
    cfg = json.loads(Path(args.config).read_text())
    xcfg = cfg["xfoil"]
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    results = []
    minimum_points = int(xcfg["minimum_converged_points"])
    required_min = float(xcfg["required_alpha_min_deg"])
    required_max = float(xcfg["required_alpha_max_deg"])

    for name, airfoil_meta in cfg["airfoils"].items():
        reynolds_values = airfoil_meta["analysis_reynolds"]
        for re in reynolds_values:
            with tempfile.TemporaryDirectory(prefix="he1_xfoil_") as td:
                raw_polar = Path(td) / "polar.txt"
                commands = xfoil_input(Path(args.airfoils) / f"{name}.dat", raw_polar, int(re), xcfg)
                proc = subprocess.run([exe], input=commands, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=45)
                if not raw_polar.exists():
                    raise RuntimeError(f"XFOIL produced no polar for {name} Re={re}:\n{proc.stdout[-3000:]}")
                try:
                    points = read_xfoil_polar(raw_polar)
                except Exception as exc:
                    raise RuntimeError(f"unusable XFOIL polar for {name} Re={re}: {exc}\n{proc.stdout[-3000:]}") from exc

                alpha_min = min(p.alpha_deg for p in points)
                alpha_max = max(p.alpha_deg for p in points)
                coverage_ok = len(points) >= minimum_points and alpha_min <= required_min and alpha_max >= required_max
                if not coverage_ok:
                    raise RuntimeError(
                        f"XFOIL coverage insufficient for {name} Re={re}: points={len(points)}, "
                        f"alpha=[{alpha_min}, {alpha_max}], exit={proc.returncode}\n{proc.stdout[-3000:]}"
                    )

                csv_path = out / f"{name}_re{int(re)}.csv"
                write_polar_csv(points, csv_path)
                results.append({
                    "airfoil": name,
                    "reynolds": int(re),
                    "converged_points": len(points),
                    "alpha_min": alpha_min,
                    "alpha_max": alpha_max,
                    "cl_max_observed": max(p.cl for p in points),
                    "cd_min_observed": min(p.cd for p in points),
                    "best_section_ld_observed": max(p.cl / p.cd for p in points if p.cl > 0),
                    "xfoil_exit_code": proc.returncode,
                    "partial_after_solver_failure": proc.returncode != 0,
                    "path": str(csv_path),
                })
    (out / "summary.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"generated {len(results)} viscous polar cases")


if __name__ == "__main__":
    main()
