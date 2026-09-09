from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class MassItem:
    name: str
    mass_kg: float
    x_m: float


def total_mass(items: Iterable[MassItem]) -> float:
    return sum(i.mass_kg for i in items)


def cg_x(items: Iterable[MassItem]) -> float:
    items = list(items)
    mass = total_mass(items)
    if mass <= 0:
        raise ValueError("total mass must be positive")
    return sum(i.mass_kg * i.x_m for i in items) / mass


def combine_mass_and_cg(mass_a_kg: float, cg_a_m: float, mass_b_kg: float, cg_b_m: float) -> tuple[float, float]:
    total = mass_a_kg + mass_b_kg
    if total <= 0:
        raise ValueError("combined mass must be positive")
    return total, (mass_a_kg * cg_a_m + mass_b_kg * cg_b_m) / total


def cg_fraction_mac(cg_x_m: float, wing_root_le_x_m: float, mac_m: float) -> float:
    return (cg_x_m - wing_root_le_x_m) / mac_m
