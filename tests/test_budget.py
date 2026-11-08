"""Tests for the token budget."""
import unittest

from leancoder.budget import BudgetExceeded, TokenBudget


class TestTokenBudget(unittest.TestCase):
    def test_add_within_budget(self):
        budget = TokenBudget(100)
        budget.add(10, 5)
        self.assertEqual(budget.total_tokens, 15)
        self.assertEqual(budget.remaining, 85)
        self.assertFalse(budget.is_exceeded)

    def test_check_raises_before_overrun(self):
        budget = TokenBudget(100)
        budget.add(90, 0)
        with self.assertRaises(BudgetExceeded):
            budget.add(20, 0)
        self.assertEqual(budget.total_tokens, 90)

    def test_summary(self):
        budget = TokenBudget(50, max_cost=1.0)
        budget.add(10, 5, cost=0.25)
        summary = budget.summary()
        self.assertEqual(summary["total_tokens"], 15)
        self.assertEqual(summary["remaining"], 35)
        self.assertEqual(summary["cost"], 0.25)

    def test_cost_budget_exceeded(self):
        budget = TokenBudget(1000, max_cost=1.0)
        with self.assertRaises(BudgetExceeded):
            budget.add(10, 5, cost=2.0)

    def test_invalid_max_tokens(self):
        with self.assertRaises(ValueError):
            TokenBudget(0)
        with self.assertRaises(ValueError):
            TokenBudget(-5)


if __name__ == "__main__":
    unittest.main()
