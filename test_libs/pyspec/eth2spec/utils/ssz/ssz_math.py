def next_power_of_two(v: int) -> int:
    """
    Get the next power of 2.
    0 is a special case, to have non-empty defaults.
    Examples:
    0 -> 1, 1 -> 1, 2 -> 2, 3 -> 4, 32 -> 32, 33 -> 64
    """
    if v == 0:
        return 1
    return 1 << (v - 1).bit_length()


def previous_power_of_two(v: int) -> int:
    """
    Get the previous power of 2.
    0 is a special case, to have non-empty defaults.
    Examples:
    0 -> 1, 1 -> 1, 2 -> 2, 3 -> 2, 32 -> 32, 33 -> 32
    """
    if v == 0:
        return 1
    return 1 << (v.bit_length() - 1)
