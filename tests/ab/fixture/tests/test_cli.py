import unittest
from statlib import cli


class T(unittest.TestCase):
    def test_summarize_keys(self): self.assertEqual(set(cli.summarize([1, 2, 3, 4])), {"mean", "median", "stdev", "p90"})


if __name__ == "__main__":
    unittest.main()
