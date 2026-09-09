import tempfile
import unittest
from pathlib import Path

from aurora_he1.polars import PolarFamily, PolarPoint, read_xfoil_polar


class PolarTests(unittest.TestCase):
    def test_xfoil_parser(self):
        text = """XFOIL Version 6.99\n alpha CL CD CDp CM Top_Xtr Bot_Xtr\n ------\n -2.0 -0.10 0.020 0.010 -0.02 1 1\n 0.0 0.20 0.012 0.008 -0.04 1 1\n 4.0 0.60 0.015 0.010 -0.05 1 1\n"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p.txt"
            path.write_text(text)
            points = read_xfoil_polar(path)
            self.assertEqual(len(points), 3)
            self.assertAlmostEqual(points[1].cl, 0.20)

    def test_reynolds_and_alpha_interpolation(self):
        low = [PolarPoint(0, 0.2, 0.020), PolarPoint(4, 0.6, 0.024), PolarPoint(8, 0.9, 0.035)]
        high = [PolarPoint(0, 0.2, 0.010), PolarPoint(4, 0.6, 0.014), PolarPoint(8, 0.9, 0.025)]
        family = PolarFamily({100000: low, 200000: high})
        coefficients = family.coefficients(150000, 2.0)
        self.assertAlmostEqual(coefficients.cl, 0.4, places=6)
        self.assertAlmostEqual(coefficients.cd, 0.017, places=6)


if __name__ == "__main__":
    unittest.main()
