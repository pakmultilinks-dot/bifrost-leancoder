"""Hidden grading tests for task 5. Not shown to the agent."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import validate


class TestParseAge(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate.parse_age("25"), 25)

    def test_non_numeric(self):
        with self.assertRaises(ValueError):
            validate.parse_age("abc")

    def test_empty(self):
        with self.assertRaises(ValueError):
            validate.parse_age("")

    def test_negative(self):
        with self.assertRaises(ValueError):
            validate.parse_age("-1")

    def test_too_old(self):
        with self.assertRaises(ValueError):
            validate.parse_age("200")


if __name__ == "__main__":
    unittest.main()
