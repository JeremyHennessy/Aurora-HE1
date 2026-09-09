from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WingGeometry:
    span_m: float
    area_m2: float
    taper_ratio: float
    root_chord_m: float
    tip_chord_m: float
    mean_aerodynamic_chord_m: float
    aspect_ratio: float


def solve_trapezoidal_wing(span_m: float, area_m2: float, taper_ratio: float) -> WingGeometry:
    if span_m <= 0 or area_m2 <= 0:
        raise ValueError("span and area must be positive")
    if not 0 < taper_ratio <= 1:
        raise ValueError("taper_ratio must be in (0, 1]")
    root = 2.0 * area_m2 / (span_m * (1.0 + taper_ratio))
    tip = taper_ratio * root
    mac = (2.0 / 3.0) * root * (1.0 + taper_ratio + taper_ratio**2) / (1.0 + taper_ratio)
    ar = span_m**2 / area_m2
    return WingGeometry(span_m, area_m2, taper_ratio, root, tip, mac, ar)


def chord_at_eta(wing: WingGeometry, eta: float) -> float:
    """Chord at nondimensional semi-span station eta=0 root, eta=1 tip."""
    if not 0.0 <= eta <= 1.0:
        raise ValueError("eta must be in [0, 1]")
    return wing.root_chord_m + eta * (wing.tip_chord_m - wing.root_chord_m)


def reynolds_number(rho_kg_m3: float, speed_m_s: float, chord_m: float, dynamic_viscosity_pa_s: float) -> float:
    return rho_kg_m3 * speed_m_s * chord_m / dynamic_viscosity_pa_s


def panel_length_sum(panel_lengths_m: list[float]) -> float:
    return sum(panel_lengths_m)
