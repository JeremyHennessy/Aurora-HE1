from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aurora_he1.config import load_config
from aurora_he1.model import evaluate
from aurora_he1.validation import validate


def main() -> int:
    cfg = load_config(ROOT / "config" / "he1_baseline.json")
    result = evaluate(cfg)
    errors = validate(cfg, result)
    if errors:
        print("DESIGN VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("DESIGN VALIDATION PASSED")
    print(f"gross mass: {result['gross_mass_kg']:.2f} kg")
    print(f"gross CG: {result['gross_cg_fraction_mac']*100:.2f}% MAC")
    print(f"stall: {result['stall_speed_km_h']:.2f} km/h")
    print(f"cruise shaft power: {result['power_split']['prop_shaft_required_w']:.1f} W")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
