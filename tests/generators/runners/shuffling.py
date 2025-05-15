from typing import Iterable
import random

from eth2spec.gen_helpers.gen_base.gen_typing import TestCase

from eth2spec.phase0 import mainnet as spec_mainnet, minimal as spec_minimal
from eth2spec.test.helpers.constants import PHASE0, ALL_PRESETS, MINIMAL, MAINNET


def generate_random_bytes(rng=random.Random(5566)):
    random_bytes = bytes(rng.randint(0, 255) for _ in range(32))
    return random_bytes


def shuffling_case_fn(spec, seed, count):
    yield "mapping", "data", {
        "seed": "0x" + seed.hex(),
        "count": count,
        "mapping": [int(spec.compute_shuffled_index(i, count, seed)) for i in range(count)],
    }


def shuffling_case(spec, seed, count):
    return f"shuffle_0x{seed.hex()}_{count}", lambda: shuffling_case_fn(spec, seed, count)


def shuffling_test_cases(spec):
    # NOTE: somehow the random.Random generated seeds do not have pickle issue.
    rng = random.Random(1234)
    seeds = [generate_random_bytes(rng) for i in range(30)]
    for seed in seeds:
        for count in [0, 1, 2, 3, 5, 10, 33, 100, 1000, 9999]:
            yield shuffling_case(spec, seed, count)


def get_test_cases() -> Iterable[TestCase]:
    test_cases = []

    for preset in ALL_PRESETS:
        spec = {MAINNET: spec_mainnet, MINIMAL: spec_minimal}[preset]
        for case_name, case_fn in shuffling_test_cases(spec):
            test_cases.append(
                TestCase(
                    fork_name=PHASE0,
                    preset_name=preset,
                    runner_name="shuffling",
                    handler_name="core",
                    suite_name="shuffle",
                    case_name=case_name,
                    case_fn=case_fn,
                )
            )
    return test_cases
