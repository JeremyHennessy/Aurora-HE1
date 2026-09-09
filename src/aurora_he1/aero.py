from __future__ import annotations

import math
from dataclasses import dataclass

from .geometry import WingGeometry


@dataclass(frozen=True)
class AeroPoint:
    speed_m_s: float
    cl: float
    cd_induced: float
    cd_total: float
    drag_n: float
    lift_to_drag: float
    aerodynamic_power_w: float


def dynamic_pressure(rho_kg_m3: float, speed_m_s: float) -> float:
    return 0.5 * rho_kg_m3 * speed_m_s**2


def lift_coefficient(weight_n: float, rho_kg_m3: float, speed_m_s: float, area_m2: float) -> float:
    return weight_n / (dynamic_pressure(rho_kg_m3, speed_m_s) * area_m2)


def induced_drag_factor(wing: WingGeometry, oswald_efficiency: float) -> float:
    if not 0 < oswald_efficiency <= 1:
        raise ValueError("oswald_efficiency must be in (0, 1]")
    return 1.0 / (math.pi * oswald_efficiency * wing.aspect_ratio)


def aero_point(*, weight_n: float, rho_kg_m3: float, speed_m_s: float, wing: WingGeometry, cd0: float, oswald_efficiency: float) -> AeroPoint:
    cl = lift_coefficient(weight_n, rho_kg_m3, speed_m_s, wing.area_m2)
    cdi = induced_drag_factor(wing, oswald_efficiency) * cl**2
    cd = cd0 + cdi
    q = dynamic_pressure(rho_kg_m3, speed_m_s)
    drag = q * wing.area_m2 * cd
    ld = weight_n / drag
    return AeroPoint(speed_m_s, cl, cdi, cd, drag, ld, drag * speed_m_s)


def stall_speed(weight_n: float, rho_kg_m3: float, area_m2: float, cl_max: float) -> float:
    if cl_max <= 0:
        raise ValueError("cl_max must be positive")
    return math.sqrt(2.0 * weight_n / (rho_kg_m3 * area_m2 * cl_max))


def speed_for_best_ld(weight_n: float, rho_kg_m3: float, wing: WingGeometry, cd0: float, oswald_efficiency: float) -> float:
    k = induced_drag_factor(wing, oswald_efficiency)
    cl_best_ld = math.sqrt(cd0 / k)
    return math.sqrt(2.0 * weight_n / (rho_kg_m3 * wing.area_m2 * cl_best_ld))
