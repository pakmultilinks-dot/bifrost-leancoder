"""Per-task token and cost budget, with a hard stop.

The budget is enforced in code. A run that spends its budget is
marked failed, never silently continued past the limit.
"""
from __future__ import annotations


class BudgetExceeded(Exception):
    """Raised when a token or cost budget is exceeded."""


class TokenBudget:
    """Track prompt, completion, and total tokens plus cost."""

    def __init__(self, max_tokens, max_cost=None):
        if max_tokens is None or int(max_tokens) <= 0:
            raise ValueError("max_tokens must be a positive number")
        self.max_tokens = int(max_tokens)
        self.max_cost = max_cost
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.cost = 0.0

    @property
    def total_tokens(self):
        return self.prompt_tokens + self.completion_tokens

    @property
    def remaining(self):
        return self.max_tokens - self.total_tokens

    @property
    def is_exceeded(self):
        return self.total_tokens > self.max_tokens

    def check(self, prompt_tokens=0, completion_tokens=0, cost=0.0):
        """Raise BudgetExceeded if adding this usage would go over."""
        new_total = self.total_tokens + int(prompt_tokens) + int(completion_tokens)
        if new_total > self.max_tokens:
            raise BudgetExceeded(
                "Token budget exceeded: " + str(new_total) + " tokens "
                "would pass the limit of " + str(self.max_tokens) + " tokens. "
                "The run stops here.")
        if self.max_cost is not None and self.cost + float(cost) > self.max_cost:
            raise BudgetExceeded(
                "Cost budget exceeded: " + str(self.cost + float(cost))
                + " would pass the limit of " + str(self.max_cost) + ". "
                "The run stops here.")

    def add(self, prompt_tokens=0, completion_tokens=0, cost=0.0):
        """Record usage, after checking the budget first."""
        self.check(prompt_tokens, completion_tokens, cost)
        self.prompt_tokens += int(prompt_tokens)
        self.completion_tokens += int(completion_tokens)
        self.cost += float(cost)

    def summary(self):
        return {
            "max_tokens": self.max_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "remaining": self.remaining,
            "cost": self.cost,
        }
