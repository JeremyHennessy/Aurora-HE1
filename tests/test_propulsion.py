import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aurora_he1.propulsion import prop_rpm_from_mid_drive, propeller_advance_ratio


class PropulsionTests(unittest.TestCase):
    def test_sprocket_ratio(self):
        self.assertAlmostEqual(prop_rpm_from_mid_drive(90.0, 48, 33), 130.9090909, places=6)

    def test_advance_ratio(self):
        j = propeller_advance_ratio(9.5, 130.0, 2.85)
        self.assertAlmostEqual(j, 1.5384615, places=6)


if __name__ == "__main__":
    unittest.main()
