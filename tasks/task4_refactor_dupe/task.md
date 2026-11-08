# Task 4: Refactor a duplicated block

The tax calculation `amount * 0.20` plus adding it to the amount
appears twice in `pricing.py`, once in `price_with_tax` and once in
`price_with_discount`. Refactor the duplicated block into one helper
function called `add_tax`, and use that helper in both functions.

- `price_with_tax(100)` must still return 120.0
- `price_with_discount(100, 10)` must still return 108.0
- `add_tax` must exist and be used by both functions
- No test result may change
