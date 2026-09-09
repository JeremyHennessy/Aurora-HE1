import math
import unittest

from aurora_he1.polars import SectionCoefficients
from aurora_he1.propeller_trade import design_seed_family, polar_envelope_ok, select_operating_point


class SyntheticPolar:
    def coefficients(self, reynolds, alpha_deg):
        cl = max(-1.3, min(1.3, 0.25 + 2.0 * math.pi * math.radians(alpha_deg)))
        cd = 0.011 + 0.012 * cl * cl + 0.0015 * (150000.0 / max(75000.0, reynolds))
        return SectionCoefficients(cl, cd, -0.05)


class PropellerTradeTests(unittest.TestCase):
    def test_family_respects_ground_clearance_constraint(self):
        candidates, selected = design_seed_family(
            polar=SyntheticPolar(),
            blade_count=2,
            diameters_m=[2.50, 2.85, 3.00],
            design_rpms=[120.0, 130.0, 140.0],
            design_speed_m_s=9.5,
            density_kg_m3=1.225,
            dynamic_viscosity_pa_s=1.7894e-5,
            required_thrust_n=31.7,
            shaft_center_height_m=1.75,
            minimum_ground_clearance_m=0.30,
            trusted_min_reynolds=50000.0,
            trusted_max_reynolds=500000.0,
            trusted_min_alpha_deg=-10.0,
            trusted_max_alpha_deg=10.0,
            minimum_power_w=200.0,
            maximum_power_w=800.0,
        )
        by_diameter = {candidate.diameter_m: candidate for candidate, _stations in candidates if candidate.design_rpm == 130.0}
        self.assertFalse(by_diameter[3.00].ground_clearance_ok)
        self.assertTrue(selected[0].ground_clearance_ok)
        self.assertLessEqual(selected[0].diameter_m, 2.90)

    def test_off_design_selector_requires_thrust_and_polar_coverage(self):
        _candidates, selected = design_seed_family(
            polar=SyntheticPolar(),
            blade_count=2,
            diameters_m=[2.85],
            design_rpms=[130.0],
            design_speed_m_s=9.5,
            density_kg_m3=1.225,
            dynamic_viscosity_pa_s=1.7894e-5,
            required_thrust_n=31.7,
            shaft_center_height_m=1.75,
            minimum_ground_clearance_m=0.30,
            trusted_min_reynolds=50000.0,
            trusted_max_reynolds=500000.0,
            trusted_min_alpha_deg=-10.0,
            trusted_max_alpha_deg=10.0,
            minimum_power_w=200.0,
            maximum_power_w=800.0,
        )
        candidate, stations = selected
        point = select_operating_point(
            stations=stations,
            polar=SyntheticPolar(),
            blade_count=2,
            diameter_m=candidate.diameter_m,
            speed_m_s=9.5,
            rpm_values=[110.0, 120.0, 130.0, 140.0, 150.0],
            density_kg_m3=1.225,
            dynamic_viscosity_pa_s=1.7894e-5,
            required_thrust_n=31.7,
            trusted_min_reynolds=50000.0,
            trusted_max_reynolds=500000.0,
            trusted_min_alpha_deg=-10.0,
            trusted_max_alpha_deg=10.0,
            minimum_power_w=200.0,
            maximum_power_w=800.0,
        )
        self.assertIsNotNone(point)
        self.assertGreaterEqual(point.result.thrust_n, 31.7)
        self.assertTrue(point.polar_envelope_ok)
        self.assertTrue(polar_envelope_ok(
            point.result,
            min_reynolds=50000.0,
            max_reynolds=500000.0,
            min_alpha_deg=-10.0,
            max_alpha_deg=10.0,
        ))


if __name__ == "__main__":
    unittest.main()
