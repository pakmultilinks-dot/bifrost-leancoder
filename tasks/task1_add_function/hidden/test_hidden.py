"""Hidden grading tests for task 1. Not shown to the agent."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mathutil


class TestMedian(unittest.TestCase):
    def test_odd_length(self):
        self.assertEqual(mathutil.median([1, 3, 2]), 2)

    def test_even_length(self):
        self.assertEqual(mathutil.median([1, 2, 3, 4]), 2.5)

    def test_single(self):
        self.assertEqual(mathutil.median([5]), 5)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            mathutil.median([])

    def test_has_docstring(self):
        self.assertTrue(mathutil.median.__doc__)


if __name__ == "__main__":
    unittest.main()
