"""Hidden grading tests for task 2. Not shown to the agent."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import counter


class TestTotalUpto(unittest.TestCase):
    def test_five(self):
        self.assertEqual(counter.total_upto(5), 15)

    def test_one(self):
        self.assertEqual(counter.total_upto(1), 1)

    def test_zero(self):
        self.assertEqual(counter.total_upto(0), 0)

    def test_ten(self):
        self.assertEqual(counter.total_upto(10), 55)


if __name__ == "__main__":
    unittest.main()
