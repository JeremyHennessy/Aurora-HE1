import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aurora_he1.geometry import chord_at_eta, solve_trapezoidal_wing


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.wing = solve_trapezoidal_wing(23.0, 18.0, 0.48)

    def test_baseline_geometry(self):
        self.assertAlmostEqual(self.wing.aspect_ratio, 29.3888888889, places=8)
        self.assertAlmostEqual(self.wing.root_chord_m, 1.0575793184, places=8)
        self.assertAlmostEqual(self.wing.tip_chord_m, 0.5076380728, places=8)
        self.assertAlmostEqual(self.wing.mean_aerodynamic_chord_m, 0.8148124623, places=8)

    def test_chord_endpoints(self):
        self.assertAlmostEqual(chord_at_eta(self.wing, 0), self.wing.root_chord_m)
        self.assertAlmostEqual(chord_at_eta(self.wing, 1), self.wing.tip_chord_m)


if __name__ == "__main__":
    unittest.main()
