import pytest


# Note: these functions are extract from merkle-proofs.md (deprecated),
# the tests are temporary to show correctness while the document is still there.


def get_power_of_two_ceil(x: int) -> int:
    if x <= 1:
        return 1
    elif x == 2:
        return 2
    else:
        return 2 * get_power_of_two_ceil((x + 1) // 2)


def get_power_of_two_floor(x: int) -> int:
    if x <= 1:
        return 1
    if x == 2:
        return x
    else:
        return 2 * get_power_of_two_floor(x // 2)


power_of_two_ceil_cases = [
    (0, 1),
    (1, 1),
    (2, 2),
    (3, 4),
    (4, 4),
    (5, 8),
    (6, 8),
    (7, 8),
    (8, 8),
    (9, 16),
]

power_of_two_floor_cases = [
    (0, 1),
    (1, 1),
    (2, 2),
    (3, 2),
    (4, 4),
    (5, 4),
    (6, 4),
    (7, 4),
    (8, 8),
    (9, 8),
]


@pytest.mark.parametrize(
    "value,expected",
    power_of_two_ceil_cases,
)
def test_get_power_of_two_ceil(value, expected):
    assert get_power_of_two_ceil(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    power_of_two_floor_cases,
)
def test_get_power_of_two_floor(value, expected):
    assert get_power_of_two_floor(value) == expected
