from __future__ import annotations

import bisect
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class PolarPoint:
    alpha_deg: float
    cl: float
    cd: float
    cm: float = 0.0


@dataclass(frozen=True)
class SectionCoefficients:
    cl: float
    cd: float
    cm: float


def read_xfoil_polar(path: str | Path) -> list[PolarPoint]:
    """Parse an XFOIL polar text file, ignoring headers and unconverged rows."""
    points: list[PolarPoint] = []
    for raw in Path(path).read_text().splitlines():
        fields = raw.strip().split()
        if len(fields) < 5:
            continue
        try:
            alpha, cl, cd, _cdp, cm = (float(v) for v in fields[:5])
        except ValueError:
            continue
        if cd <= 0:
            continue
        points.append(PolarPoint(alpha, cl, cd, cm))
    if len(points) < 3:
        raise ValueError(f"polar {path} contains fewer than 3 valid points")
    points.sort(key=lambda p: p.alpha_deg)
    return points


def write_polar_csv(points: Iterable[PolarPoint], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["alpha_deg", "cl", "cd", "cm"])
        for p in points:
            writer.writerow([f"{p.alpha_deg:.6f}", f"{p.cl:.8f}", f"{p.cd:.8f}", f"{p.cm:.8f}"])


def _linear_interp(x: float, xs: list[float], ys: list[float]) -> float:
    if x <= xs[0]:
        i0, i1 = 0, 1
    elif x >= xs[-1]:
        i0, i1 = len(xs) - 2, len(xs) - 1
    else:
        i1 = bisect.bisect_right(xs, x)
        i0 = i1 - 1
    x0, x1 = xs[i0], xs[i1]
    y0, y1 = ys[i0], ys[i1]
    if x1 == x0:
        return y0
    t = (x - x0) / (x1 - x0)
    return y0 + t * (y1 - y0)


class PolarFamily:
    """Interpolates alpha within a polar and Reynolds number between polars."""

    def __init__(self, polars_by_re: dict[float, list[PolarPoint]]):
        if not polars_by_re:
            raise ValueError("at least one Reynolds polar is required")
        self._polars = {float(re): sorted(points, key=lambda p: p.alpha_deg) for re, points in polars_by_re.items()}
        self._res = sorted(self._polars)

    @classmethod
    def from_directory(cls, directory: str | Path, prefix: str) -> "PolarFamily":
        directory = Path(directory)
        mapping: dict[float, list[PolarPoint]] = {}
        for path in directory.glob(f"{prefix}_re*.csv"):
            re_text = path.stem.split("_re", 1)[1]
            re_val = float(re_text)
            points: list[PolarPoint] = []
            with path.open(newline="") as f:
                for row in csv.DictReader(f):
                    points.append(PolarPoint(float(row["alpha_deg"]), float(row["cl"]), float(row["cd"]), float(row.get("cm", 0.0))))
            mapping[re_val] = points
        return cls(mapping)

    def _at_re(self, reynolds: float, alpha_deg: float) -> SectionCoefficients:
        points = self._polars[reynolds]
        alphas = [p.alpha_deg for p in points]
        return SectionCoefficients(
            _linear_interp(alpha_deg, alphas, [p.cl for p in points]),
            max(1e-5, _linear_interp(alpha_deg, alphas, [p.cd for p in points])),
            _linear_interp(alpha_deg, alphas, [p.cm for p in points]),
        )

    def coefficients(self, reynolds: float, alpha_deg: float) -> SectionCoefficients:
        if reynolds <= self._res[0]:
            return self._at_re(self._res[0], alpha_deg)
        if reynolds >= self._res[-1]:
            return self._at_re(self._res[-1], alpha_deg)
        hi = bisect.bisect_right(self._res, reynolds)
        r0, r1 = self._res[hi - 1], self._res[hi]
        c0, c1 = self._at_re(r0, alpha_deg), self._at_re(r1, alpha_deg)
        t = (reynolds - r0) / (r1 - r0)
        return SectionCoefficients(
            c0.cl + t * (c1.cl - c0.cl),
            c0.cd + t * (c1.cd - c0.cd),
            c0.cm + t * (c1.cm - c0.cm),
        )
