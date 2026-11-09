import unittest

from premiers import est_premier


class TestPremiers(unittest.TestCase):
    def test_1_non_premier(self):
        self.assertFalse(est_premier(1))

    def test_2_premier(self):
        self.assertTrue(est_premier(2))

    def test_15_non_premier(self):
        self.assertFalse(est_premier(15))

    def test_17_premier(self):
        self.assertTrue(est_premier(17))


if __name__ == "__main__":
    unittest.main()
