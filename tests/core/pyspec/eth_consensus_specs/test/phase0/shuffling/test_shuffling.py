import random

from eth_consensus_specs.test.context import (
    only_generator,
    single_phase,
    spec_test,
    with_phases,
    with_test_suite_name,
)
from eth_consensus_specs.test.helpers.constants import PHASE0
from tests.infra.template_test import template_test


def _generate_random_bytes(rng):
    return bytes(rng.randint(0, 255) for _ in range(32))


@template_test
def _template_shuffling_test(seed: bytes, count: int):
    @with_test_suite_name("shuffle")
    @only_generator("shuffling test for reference test generation")
    @with_phases([PHASE0])
    @spec_test
    @single_phase
    def the_test(spec):
        yield (
            "mapping",
            "data",
            {
                "seed": "0x" + seed.hex(),
                "count": count,
                "mapping": [int(spec.compute_shuffled_index(i, count, seed)) for i in range(count)],
            },
        )

    return (the_test, f"test_shuffle_0x{seed.hex()}_{count}")


# Generate 300 test functions (30 seeds x 10 counts) matching the old generator.
_rng = random.Random(1234)
_seeds = [_generate_random_bytes(_rng) for _ in range(30)]

for _seed in _seeds:
    for _count in [0, 1, 2, 3, 5, 10, 33, 100, 1000, 9999]:
        _template_shuffling_test(_seed, _count)
