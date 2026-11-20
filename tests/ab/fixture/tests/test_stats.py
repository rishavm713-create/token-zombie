import unittest
from statlib import stats


class T(unittest.TestCase):
    def test_mean(self): self.assertEqual(stats.mean([1, 2, 3]), 2)
    def test_median_odd(self): self.assertEqual(stats.median([3, 1, 2]), 2)
    def test_median_even(self): self.assertEqual(stats.median([1, 2, 3, 4]), 2.5)
    def test_mode(self): self.assertEqual(stats.mode([1, 2, 2, 3]), 2)
    def test_variance_sample(self): self.assertAlmostEqual(stats.variance([2, 4, 4, 4, 5, 5, 7, 9]), 4.571428571, places=6)
    def test_percentile_interp(self): self.assertAlmostEqual(stats.percentile([1, 2, 3, 4], 50), 2.5)


if __name__ == "__main__":
    unittest.main()
