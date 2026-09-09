#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/airfoil_sources.json")
    parser.add_argument("--output", default="analysis/airfoils")
    args = parser.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"source_authority": cfg["source_authority"], "source_index": cfg["source_index"], "files": {}}
    for name, meta in cfg["airfoils"].items():
        req = urllib.request.Request(meta["url"], headers={"User-Agent": "Aurora-HE1-engineering/1.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read()
        if len(data) < 200 or b"DAE" not in data[:64].upper():
            raise RuntimeError(f"download for {name} does not look like an airfoil coordinate file")
        sha256 = hashlib.sha256(data).hexdigest()
        expected = meta.get("expected_sha256")
        if expected and sha256 != expected:
            raise RuntimeError(f"source hash mismatch for {name}: expected {expected}, got {sha256}")
        path = out / f"{name}.dat"
        path.write_bytes(data)
        manifest["files"][name] = {
            **meta,
            "sha256": sha256,
            "bytes": len(data),
            "path": str(path),
        }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
