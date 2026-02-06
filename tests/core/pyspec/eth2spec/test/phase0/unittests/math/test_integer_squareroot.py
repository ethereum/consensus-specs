import random
from math import isqrt

from eth2spec.test.context import (
    single_phase,
    spec_test,
    with_all_phases,
)


@with_all_phases
@spec_test
@single_phase
def test_integer_squareroot(spec):
    values = [0, 100, 2**64 - 2, 2**64 - 1]
    for n in values:
        uint64_n = spec.uint64(n)
        assert spec.integer_squareroot(uint64_n) == isqrt(n)

    rng = random.Random(5566)
    for _ in range(10):
        n = rng.randint(0, 2**64 - 1)
        uint64_n = spec.uint64(n)
        assert spec.integer_squareroot(uint64_n) == isqrt(n)

    bad = False
    try:
        spec.integer_squareroot(spec.uint64(2**64))
        bad = True
    except ValueError:
        pass
    assert not bad
