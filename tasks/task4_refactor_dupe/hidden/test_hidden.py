"""Hidden grading tests for task 4. Not shown to the agent."""
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pricing


class TestPricing(unittest.TestCase):
    def test_with_tax(self):
        self.assertEqual(pricing.price_with_tax(100), 120.0)

    def test_with_discount(self):
        self.assertEqual(pricing.price_with_discount(100, 10), 108.0)

    def test_zero(self):
        self.assertEqual(pricing.price_with_tax(0), 0)

    def test_helper_exists_and_used(self):
        self.assertTrue(hasattr(pricing, "add_tax"))
        source = inspect.getsource(pricing)
        self.assertIn("def add_tax", source)
        self.assertIn("add_tax(", inspect.getsource(pricing.price_with_tax))
        self.assertIn("add_tax(", inspect.getsource(pricing.price_with_discount))


if __name__ == "__main__":
    unittest.main()
