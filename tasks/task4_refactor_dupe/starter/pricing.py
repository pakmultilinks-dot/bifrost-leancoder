"""Pricing helpers, 20 percent tax."""


def price_with_tax(amount):
    """Add 20 percent tax, round to 2 decimals."""
    tax = amount * 0.20
    total = amount + tax
    return round(total, 2)


def price_with_discount(amount, percent):
    """Apply a percent discount, then add 20 percent tax."""
    discount = amount * (percent / 100)
    after = amount - discount
    tax = after * 0.20
    total = after + tax
    return round(total, 2)
