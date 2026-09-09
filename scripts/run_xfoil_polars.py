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

ASEQ {float(cfg['alpha_start_deg'])} {float(cfg['alpha_end_deg'])} {float(cfg['alpha_step_deg'])}
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
    for name in cfg["airfoils"]:
        reynolds_values = xcfg["propeller_reynolds"] if name == "dae51" else xcfg["wing_reynolds"]
        for re in reynolds_values:
            with tempfile.TemporaryDirectory(prefix="he1_xfoil_") as td:
                raw_polar = Path(td) / "polar.txt"
                commands = xfoil_input(Path(args.airfoils) / f"{name}.dat", raw_polar, int(re), xcfg)
                proc = subprocess.run([exe], input=commands, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=45)
                if proc.returncode != 0:
                    raise RuntimeError(f"XFOIL failed for {name} Re={re}:\n{proc.stdout[-3000:]}")
                points = read_xfoil_polar(raw_polar)
                if len(points) < 12:
                    raise RuntimeError(f"XFOIL produced only {len(points)} converged points for {name} Re={re}")
                csv_path = out / f"{name}_re{int(re)}.csv"
                write_polar_csv(points, csv_path)
                results.append({
                    "airfoil": name,
                    "reynolds": int(re),
                    "converged_points": len(points),
                    "alpha_min": min(p.alpha_deg for p in points),
                    "alpha_max": max(p.alpha_deg for p in points),
                    "cl_max_observed": max(p.cl for p in points),
                    "cd_min_observed": min(p.cd for p in points),
                    "best_section_ld_observed": max(p.cl / p.cd for p in points if p.cl > 0),
                    "path": str(csv_path),
                })
    (out / "summary.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"generated {len(results)} viscous polar cases")


if __name__ == "__main__":
    main()
