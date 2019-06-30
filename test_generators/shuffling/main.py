from eth2spec.phase0 import spec as spec
from eth_utils import (
    to_dict, to_tuple
)
from gen_base import gen_runner, gen_suite, gen_typing
from preset_loader import loader


@to_dict
def shuffling_case(seed, count):
    yield 'seed', '0x' + seed.hex()
    yield 'count', count
    yield 'shuffled', [spec.compute_shuffle_index(i, count, seed) for i in range(count)]


@to_tuple
def shuffling_test_cases():
    for seed in [spec.hash(spec.int_to_bytes(seed_init_value, length=4)) for seed_init_value in range(30)]:
        for count in [0, 1, 2, 3, 5, 10, 33, 100, 1000]:
            yield shuffling_case(seed, count)


def mini_shuffling_suite(configs_path: str) -> gen_typing.TestSuiteOutput:
    presets = loader.load_presets(configs_path, 'minimal')
    spec.apply_constants_preset(presets)

    return ("shuffling_minimal", "core", gen_suite.render_suite(
        title="Swap-or-Not Shuffling tests with minimal config",
        summary="Swap or not shuffling, with minimally configured testing round-count",
        forks_timeline="testing",
        forks=["phase0"],
        config="minimal",
        runner="shuffling",
        handler="core",
        test_cases=shuffling_test_cases()))


def full_shuffling_suite(configs_path: str) -> gen_typing.TestSuiteOutput:
    presets = loader.load_presets(configs_path, 'mainnet')
    spec.apply_constants_preset(presets)

    return ("shuffling_full", "core", gen_suite.render_suite(
        title="Swap-or-Not Shuffling tests with mainnet config",
        summary="Swap or not shuffling, with normal configured (secure) mainnet round-count",
        forks_timeline="mainnet",
        forks=["phase0"],
        config="mainnet",
        runner="shuffling",
        handler="core",
        test_cases=shuffling_test_cases()))


if __name__ == "__main__":
    gen_runner.run_generator("shuffling", [mini_shuffling_suite, full_shuffling_suite])
