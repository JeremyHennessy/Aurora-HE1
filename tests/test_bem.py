import math
import unittest

from aurora_he1.bem import design_constant_alpha_blade, optimize_seed_blade, solve_bem
from aurora_he1.polars import SectionCoefficients


class SyntheticPolar:
    def coefficients(self, reynolds, alpha_deg):
        cl = max(-1.3, min(1.3, 0.25 + 2.0 * math.pi * math.radians(alpha_deg)))
        cd = 0.011 + 0.012 * cl * cl + 0.0015 * (150000.0 / max(75000.0, reynolds))
        return SectionCoefficients(cl, cd, -0.05)


class BEMTests(unittest.TestCase):
    def test_positive_thrust_and_power(self):
        stations = design_constant_alpha_blade(diameter_m=2.85, speed_m_s=9.5, rpm=130, target_alpha_deg=5.0, chord_scale=1.7)
        result = solve_bem(stations=stations, polar=SyntheticPolar(), blade_count=2, diameter_m=2.85, rpm=130, speed_m_s=9.5, density_kg_m3=1.225, dynamic_viscosity_pa_s=1.7894e-5)
        self.assertGreater(result.thrust_n, 20)
        self.assertGreater(result.shaft_power_w, 200)
        self.assertGreater(result.propulsive_efficiency, 0.70)
        self.assertLessEqual(result.propulsive_efficiency, 1.0)

    def test_optimizer_meets_required_thrust(self):
        _stations, result, controls = optimize_seed_blade(polar=SyntheticPolar(), blade_count=2, diameter_m=2.85, rpm=130, speed_m_s=9.5, density_kg_m3=1.225, dynamic_viscosity_pa_s=1.7894e-5, required_thrust_n=31.7)
        self.assertGreaterEqual(result.thrust_n, 31.7)
        self.assertGreater(controls["chord_scale"], 0)


if __name__ == "__main__":
    unittest.main()
