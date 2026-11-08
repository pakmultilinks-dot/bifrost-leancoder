# Task 5: Add input validation

The function `parse_age` in `validate.py` accepts any input that
`int()` accepts, including bad ages. Add input validation so it
raises ValueError with a clear message on bad input.

- `parse_age("25")` returns 25
- `parse_age("abc")` raises ValueError
- `parse_age("")` raises ValueError
- `parse_age("-1")` raises ValueError, ages cannot be negative
- `parse_age("200")` raises ValueError, ages cannot be over 150

Do not change the function signature.
