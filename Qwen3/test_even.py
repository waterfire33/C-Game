from __future__ import annotations

def is_even(n: int) -> bool:
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError("n must be an integer")
    return n % 2 == 0