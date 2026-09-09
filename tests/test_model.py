import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aurora_he1.config import load_config
from aurora_he1.model import evaluate
from aurora_he1.validation import validate


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_config(ROOT / "config" / "he1_baseline.json")
        cls.result = evaluate(cls.cfg)

    def test_mass_closes(self):
        self.assertAlmostEqual(self.result["empty_mass_kg"], 37.5, places=8)
        self.assertAlmostEqual(self.result["gross_mass_kg"], 110.0, places=8)

    def test_reference_cg(self):
        self.assertGreater(self.result["gross_cg_fraction_mac"], 0.22)
        self.assertLess(self.result["gross_cg_fraction_mac"], 0.24)

    def test_cruise_is_above_stall_margin_gate(self):
        self.assertGreaterEqual(self.result["cruise"]["speed_m_s"], 1.15 * self.result["stall_speed_m_s"])

    def test_power_is_not_optimistically_low(self):
        self.assertGreater(self.result["power_split"]["prop_shaft_required_w"], 330.0)
        self.assertLess(self.result["power_split"]["prop_shaft_required_w"], 355.0)

    def test_boost_climb_correction(self):
        self.assertGreater(self.result["boost_climb_rate_estimate_m_s"], 0.10)
        self.assertLess(self.result["boost_climb_rate_estimate_m_s"], 0.25)

    def test_validation(self):
        self.assertEqual(validate(self.cfg, self.result), [])


if __name__ == "__main__":
    unittest.main()
