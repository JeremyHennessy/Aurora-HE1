from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PropulsionState:
    prop_shaft_required_w: float
    human_prop_shaft_w: float
    electric_prop_shaft_w: float
    electric_mid_drive_mechanical_w: float
    battery_input_w: float


def propeller_advance_ratio(speed_m_s: float, rpm: float, diameter_m: float) -> float:
    n_rps = rpm / 60.0
    return speed_m_s / (n_rps * diameter_m)


def propeller_tip_speed_m_s(speed_m_s: float, rpm: float, diameter_m: float) -> float:
    rotational_tip = math.pi * diameter_m * rpm / 60.0
    return math.hypot(rotational_tip, speed_m_s)


def final_drive_ratio(driver_teeth: int, driven_teeth: int) -> float:
    if driver_teeth <= 0 or driven_teeth <= 0:
        raise ValueError("sprocket tooth counts must be positive")
    return driver_teeth / driven_teeth


def prop_rpm_from_mid_drive(mid_drive_rpm: float, driver_teeth: int, prop_teeth: int) -> float:
    return mid_drive_rpm * final_drive_ratio(driver_teeth, prop_teeth)


def cruise_power_split(*, aerodynamic_power_w: float, propulsive_efficiency: float, human_input_w: float, final_drive_efficiency: float, motor_controller_efficiency: float) -> PropulsionState:
    if not 0 < propulsive_efficiency <= 1:
        raise ValueError("propulsive_efficiency must be in (0, 1]")
    prop_shaft_required = aerodynamic_power_w / propulsive_efficiency
    human_prop_shaft = human_input_w * final_drive_efficiency
    electric_prop_shaft = max(0.0, prop_shaft_required - human_prop_shaft)
    electric_mid_drive_mechanical = electric_prop_shaft / final_drive_efficiency
    battery_input = electric_mid_drive_mechanical / motor_controller_efficiency
    return PropulsionState(prop_shaft_required, human_prop_shaft, electric_prop_shaft, electric_mid_drive_mechanical, battery_input)


def battery_endurance_hours(nominal_wh: float, usable_fraction: float, battery_input_w: float) -> float:
    if battery_input_w <= 0:
        return math.inf
    return nominal_wh * usable_fraction / battery_input_w


def approximate_climb_rate_m_s(*, weight_n: float, level_prop_shaft_required_w: float, human_input_w: float, battery_input_w: float, motor_controller_efficiency: float, final_drive_efficiency: float, propulsive_efficiency: float) -> float:
    """Energy-method climb estimate at the evaluated airspeed; not a certification model."""
    available_shaft = (human_input_w + battery_input_w * motor_controller_efficiency) * final_drive_efficiency
    excess_shaft = max(0.0, available_shaft - level_prop_shaft_required_w)
    useful_excess = excess_shaft * propulsive_efficiency
    return useful_excess / weight_n
