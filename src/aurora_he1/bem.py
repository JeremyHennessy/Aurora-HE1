from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol


class SectionPolar(Protocol):
    def coefficients(self, reynolds: float, alpha_deg: float): ...


@dataclass(frozen=True)
class BladeStation:
    radius_m: float
    chord_m: float
    beta_deg: float


@dataclass(frozen=True)
class BEMResult:
    thrust_n: float
    torque_n_m: float
    shaft_power_w: float
    propulsive_efficiency: float
    advance_ratio: float
    disk_loading_n_m2: float
    max_reynolds: float
    min_reynolds: float
    min_alpha_deg: float
    max_alpha_deg: float


def design_constant_alpha_blade(*, diameter_m: float, speed_m_s: float, rpm: float, target_alpha_deg: float, chord_scale: float, radial_stations: int = 24, root_fraction: float = 0.20) -> list[BladeStation]:
    """Create a first-pass blade with geometric pitch matched to design inflow.

    Chord is a smooth linear taper before later circulation optimization. This is a seed geometry,
    not a final Larrabee design.
    """
    if not 0 < root_fraction < 1:
        raise ValueError("root_fraction must be in (0, 1)")
    radius = diameter_m / 2.0
    omega = rpm * 2.0 * math.pi / 60.0
    stations: list[BladeStation] = []
    for i in range(radial_stations):
        frac = root_fraction + (1.0 - root_fraction) * i / (radial_stations - 1)
        r = frac * radius
        base_chord = 0.20 + (0.055 - 0.20) * ((frac - root_fraction) / (1.0 - root_fraction))
        chord = base_chord * chord_scale
        inflow_deg = math.degrees(math.atan2(speed_m_s, omega * r))
        beta_deg = inflow_deg + target_alpha_deg
        stations.append(BladeStation(r, chord, beta_deg))
    return stations


def _prandtl_tip_loss(blade_count: int, radius_m: float, r_m: float, phi_rad: float) -> float:
    sin_phi = max(1e-5, abs(math.sin(phi_rad)))
    exponent = -0.5 * blade_count * (radius_m - r_m) / (r_m * sin_phi)
    value = (2.0 / math.pi) * math.acos(min(1.0, max(0.0, math.exp(exponent))))
    return max(0.08, value)


def solve_bem(*, stations: list[BladeStation], polar: SectionPolar, blade_count: int, diameter_m: float, rpm: float, speed_m_s: float, density_kg_m3: float, dynamic_viscosity_pa_s: float, axial_induction_initial: float = 0.02, iterations: int = 60) -> BEMResult:
    if len(stations) < 3:
        raise ValueError("at least 3 blade stations are required")
    if rpm <= 0:
        raise ValueError("rpm must be positive")
    if speed_m_s <= 0:
        raise ValueError("BEM implementation requires positive axial speed; static analysis needs a separate formulation")
    radius = diameter_m / 2.0
    omega = rpm * 2.0 * math.pi / 60.0
    sorted_stations = sorted(stations, key=lambda s: s.radius_m)
    thrust = 0.0
    torque = 0.0
    min_re = math.inf
    max_re = 0.0
    min_alpha = math.inf
    max_alpha = -math.inf
    for left, right in zip(sorted_stations[:-1], sorted_stations[1:]):
        dr = right.radius_m - left.radius_m
        r = 0.5 * (left.radius_m + right.radius_m)
        chord = 0.5 * (left.chord_m + right.chord_m)
        beta = math.radians(0.5 * (left.beta_deg + right.beta_deg))
        a = axial_induction_initial
        aprime = 0.0
        dthrust = dtorque = 0.0
        reynolds = 0.0
        alpha_deg = 0.0
        for _ in range(iterations):
            va = speed_m_s * (1.0 + a)
            vt = omega * r * (1.0 - aprime)
            w = math.hypot(va, vt)
            phi = math.atan2(va, vt)
            alpha_deg = math.degrees(beta - phi)
            reynolds = density_kg_m3 * w * chord / dynamic_viscosity_pa_s
            coeff = polar.coefficients(reynolds, alpha_deg)
            q = 0.5 * density_kg_m3 * w * w
            d_lift = q * chord * coeff.cl * blade_count * dr
            d_drag = q * chord * coeff.cd * blade_count * dr
            dthrust = d_lift * math.cos(phi) - d_drag * math.sin(phi)
            dtorque = (d_lift * math.sin(phi) + d_drag * math.cos(phi)) * r
            f_tip = _prandtl_tip_loss(blade_count, radius, r, phi)
            k = dthrust / max(1e-9, 4.0 * math.pi * density_kg_m3 * r * speed_m_s**2 * f_tip * dr)
            a_new = max(0.0, (-1.0 + math.sqrt(max(0.0, 1.0 + 4.0 * k))) / 2.0)
            denom = max(1e-9, 4.0 * math.pi * density_kg_m3 * r**3 * speed_m_s * omega * f_tip * (1.0 + a) * dr)
            ap_new = max(0.0, min(0.35, dtorque / denom))
            a = 0.70 * a + 0.30 * min(0.45, a_new)
            aprime = 0.70 * aprime + 0.30 * ap_new
        thrust += dthrust
        torque += dtorque
        min_re = min(min_re, reynolds)
        max_re = max(max_re, reynolds)
        min_alpha = min(min_alpha, alpha_deg)
        max_alpha = max(max_alpha, alpha_deg)
    shaft_power = torque * omega
    useful_power = thrust * speed_m_s
    efficiency = useful_power / shaft_power if shaft_power > 0 else 0.0
    n_rps = rpm / 60.0
    advance_ratio = speed_m_s / (n_rps * diameter_m)
    disk_area = math.pi * radius**2
    return BEMResult(thrust, torque, shaft_power, efficiency, advance_ratio, thrust / disk_area, max_re, min_re, min_alpha, max_alpha)


def optimize_seed_blade(*, polar: SectionPolar, blade_count: int, diameter_m: float, rpm: float, speed_m_s: float, density_kg_m3: float, dynamic_viscosity_pa_s: float, required_thrust_n: float) -> tuple[list[BladeStation], BEMResult, dict[str, float]]:
    """Grid-search seed twist/chord parameters; intended to precede higher-order optimization."""
    candidates: list[tuple[float, float, list[BladeStation], BEMResult]] = []
    for alpha in (3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5):
        for scale_i in range(90, 281, 5):
            scale = scale_i / 100.0
            stations = design_constant_alpha_blade(diameter_m=diameter_m, speed_m_s=speed_m_s, rpm=rpm, target_alpha_deg=alpha, chord_scale=scale)
            result = solve_bem(stations=stations, polar=polar, blade_count=blade_count, diameter_m=diameter_m, rpm=rpm, speed_m_s=speed_m_s, density_kg_m3=density_kg_m3, dynamic_viscosity_pa_s=dynamic_viscosity_pa_s)
            if result.thrust_n >= required_thrust_n:
                candidates.append((result.shaft_power_w, -result.propulsive_efficiency, stations, result))
    if not candidates:
        raise RuntimeError("no seed blade satisfies required thrust within search bounds")
    candidates.sort(key=lambda item: (item[0], item[1]))
    _, _, stations, result = candidates[0]
    first = stations[0]
    radius = diameter_m / 2.0
    frac = first.radius_m / radius
    base_first = 0.20 + (0.055 - 0.20) * ((frac - 0.20) / 0.80)
    chord_scale = first.chord_m / base_first
    omega = rpm * 2.0 * math.pi / 60.0
    inflow_first = math.degrees(math.atan2(speed_m_s, omega * first.radius_m))
    alpha_target = first.beta_deg - inflow_first
    return stations, result, {"target_alpha_deg": alpha_target, "chord_scale": chord_scale}
