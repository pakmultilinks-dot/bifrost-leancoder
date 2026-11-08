"""Counting helpers."""


def total_upto(n):
    """Return 1 + 2 + ... + n."""
    total = 0
    for i in range(n):
        total += i
    return total
