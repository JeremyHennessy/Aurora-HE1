from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from .bem import BEMResult, BladeStation, SectionPolar, optimize_seed_blade, solve_bem


@dataclass(frozen=True)
class PropellerCandidate:
    diameter_m: float
    design_rpm: float
    ground_clearance_m: float
    ground_clearance_ok: bool
    target_alpha_deg: float
    chord_scale: float
    result: BEMResult
    polar_envelope_ok: bool
    power_band_ok: bool


@dataclass(frozen=True)
class PropellerOperatingPoint:
    speed_m_s: float
    rpm: float
    required_thrust_n: float
    thrust_margin_n: float
    result: BEMResult
    polar_envelope_ok: bool
    power_band_ok: bool


def polar_envelope_ok(result: BEMResult, *, min_reynolds: float, max_reynolds: float, min_alpha_deg: float, max_alpha_deg: float) -> bool:
    return (
        result.min_reynolds >= min_reynolds
        and result.max_reynolds <= max_reynolds
        and result.min_alpha_deg >= min_alpha_deg
        and result.max_alpha_deg <= max_alpha_deg
    )


def design_seed_family(
    *,
    polar: SectionPolar,
    blade_count: int,
    diameters_m: Iterable[float],
    design_rpms: Iterable[float],
    design_speed_m_s: float,
    density_kg_m3: float,
    dynamic_viscosity_pa_s: float,
    required_thrust_n: float,
    shaft_center_height_m: float,
    minimum_ground_clearance_m: float,
    trusted_min_reynolds: float,
    trusted_max_reynolds: float,
    trusted_min_alpha_deg: float,
    trusted_max_alpha_deg: float,
    minimum_power_w: float = 250.0,
    maximum_power_w: float = 800.0,
) -> tuple[list[tuple[PropellerCandidate, list[BladeStation]]], tuple[PropellerCandidate, list[BladeStation]]]:
    candidates: list[tuple[PropellerCandidate, list[BladeStation]]] = []
    for diameter_m in diameters_m:
        for rpm in design_rpms:
            try:
                stations, result, controls = optimize_seed_blade(
                    polar=polar,
                    blade_count=blade_count,
                    diameter_m=diameter_m,
                    rpm=rpm,
                    speed_m_s=design_speed_m_s,
                    density_kg_m3=density_kg_m3,
                    dynamic_viscosity_pa_s=dynamic_viscosity_pa_s,
                    required_thrust_n=required_thrust_n,
                )
            except RuntimeError:
                continue
            clearance = shaft_center_height_m - diameter_m / 2.0
            candidate = PropellerCandidate(
                diameter_m=diameter_m,
                design_rpm=rpm,
                ground_clearance_m=clearance,
                ground_clearance_ok=clearance >= minimum_ground_clearance_m,
                target_alpha_deg=controls["target_alpha_deg"],
                chord_scale=controls["chord_scale"],
                result=result,
                polar_envelope_ok=polar_envelope_ok(
                    result,
                    min_reynolds=trusted_min_reynolds,
                    max_reynolds=trusted_max_reynolds,
                    min_alpha_deg=trusted_min_alpha_deg,
                    max_alpha_deg=trusted_max_alpha_deg,
                ),
                power_band_ok=minimum_power_w <= result.shaft_power_w <= maximum_power_w,
            )
            candidates.append((candidate, stations))
    feasible = [
        item for item in candidates
        if item[0].ground_clearance_ok
        and item[0].polar_envelope_ok
        and item[0].power_band_ok
        and item[0].result.thrust_n >= required_thrust_n
        and 0.0 < item[0].result.propulsive_efficiency <= 1.0
    ]
    if not feasible:
        raise RuntimeError("no propeller family candidate satisfies geometry, polar, power, and thrust gates")
    feasible.sort(key=lambda item: (item[0].result.shaft_power_w, -item[0].result.propulsive_efficiency, item[0].diameter_m))
    return candidates, feasible[0]


def select_operating_point(
    *,
    stations: list[BladeStation],
    polar: SectionPolar,
    blade_count: int,
    diameter_m: float,
    speed_m_s: float,
    rpm_values: Iterable[float],
    density_kg_m3: float,
    dynamic_viscosity_pa_s: float,
    required_thrust_n: float,
    trusted_min_reynolds: float,
    trusted_max_reynolds: float,
    trusted_min_alpha_deg: float,
    trusted_max_alpha_deg: float,
    minimum_power_w: float = 250.0,
    maximum_power_w: float = 800.0,
) -> PropellerOperatingPoint | None:
    valid: list[PropellerOperatingPoint] = []
    for rpm in rpm_values:
        result = solve_bem(
            stations=stations,
            polar=polar,
            blade_count=blade_count,
            diameter_m=diameter_m,
            rpm=rpm,
            speed_m_s=speed_m_s,
            density_kg_m3=density_kg_m3,
            dynamic_viscosity_pa_s=dynamic_viscosity_pa_s,
        )
        envelope_ok = polar_envelope_ok(
            result,
            min_reynolds=trusted_min_reynolds,
            max_reynolds=trusted_max_reynolds,
            min_alpha_deg=trusted_min_alpha_deg,
            max_alpha_deg=trusted_max_alpha_deg,
        )
        point = PropellerOperatingPoint(
            speed_m_s=speed_m_s,
            rpm=rpm,
            required_thrust_n=required_thrust_n,
            thrust_margin_n=result.thrust_n - required_thrust_n,
            result=result,
            polar_envelope_ok=envelope_ok,
            power_band_ok=minimum_power_w <= result.shaft_power_w <= maximum_power_w,
        )
        if result.thrust_n >= required_thrust_n and envelope_ok and result.shaft_power_w > 0:
            valid.append(point)
    if not valid:
        return None
    valid.sort(key=lambda p: (p.result.shaft_power_w, -p.result.propulsive_efficiency, p.rpm))
    return valid[0]


def candidate_to_dict(candidate: PropellerCandidate) -> dict:
    data = asdict(candidate)
    data["result"] = asdict(candidate.result)
    return data


def operating_point_to_dict(point: PropellerOperatingPoint) -> dict:
    data = asdict(point)
    data["result"] = asdict(point.result)
    return data
