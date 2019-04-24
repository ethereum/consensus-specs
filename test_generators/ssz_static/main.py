from random import Random

from eth2spec.debug import random_value, encode
from eth2spec.phase0 import spec
from eth2spec.utils.minimal_ssz import (
    hash_tree_root,
    signing_root,
    serialize,
)
from eth_utils import (
    to_tuple, to_dict
)
from gen_base import gen_runner, gen_suite, gen_typing
from preset_loader import loader

MAX_BYTES_LENGTH = 100
MAX_LIST_LENGTH = 10


@to_dict
def create_test_case(rng: Random, name: str, mode: random_value.RandomizationMode, chaos: bool):
    typ = spec.get_ssz_type_by_name(name)
    value = random_value.get_random_ssz_object(rng, typ, MAX_BYTES_LENGTH, MAX_LIST_LENGTH, mode, chaos)
    yield "type_name", name
    yield "value", encode.encode(value, typ)
    yield "serialized", '0x' + serialize(value).hex()
    yield "root", '0x' + hash_tree_root(value).hex()
    if hasattr(value, "signature"):
        yield "signing_root", '0x' + signing_root(value).hex()


@to_tuple
def ssz_static_cases(rng: Random, mode: random_value.RandomizationMode, chaos: bool, count: int):
    for type_name in spec.ssz_types:
        for i in range(count):
            yield create_test_case(rng, type_name, mode, chaos)


def get_ssz_suite(seed: int, config_name: str, mode: random_value.RandomizationMode, chaos: bool, cases_if_random: int):
    def ssz_suite(configs_path: str) -> gen_typing.TestSuiteOutput:
        # Apply changes to presets, this affects some of the vector types.
        presets = loader.load_presets(configs_path, config_name)
        spec.apply_constants_preset(presets)

        # Reproducible RNG
        rng = Random(seed)

        random_mode_name = mode.to_name()

        suite_name = f"ssz_{config_name}_{random_mode_name}{'_chaos' if chaos else ''}"

        count = cases_if_random if chaos or mode.is_changing() else 1
        print(f"generating SSZ-static suite ({count} cases per ssz type): {suite_name}")

        return (suite_name, "core", gen_suite.render_suite(
            title=f"ssz testing, with {config_name} config, randomized with mode {random_mode_name}{' and with chaos applied' if chaos else ''}",
            summary="Test suite for ssz serialization and hash-tree-root",
            forks_timeline="testing",
            forks=["phase0"],
            config=config_name,
            runner="ssz",
            handler="static",
            test_cases=ssz_static_cases(rng, mode, chaos, count)))

    return ssz_suite


if __name__ == "__main__":
    # [(seed, config name, randomization mode, chaos on/off, cases_if_random)]
    settings = []
    seed = 1
    for mode in random_value.RandomizationMode:
        settings.append((seed, "minimal", mode, False, 30))
        seed += 1
    settings.append((seed, "minimal", random_value.RandomizationMode.mode_random, True, 30))
    seed += 1
    settings.append((seed, "mainnet", random_value.RandomizationMode.mode_random, False, 5))
    seed += 1

    print("Settings: %d, SSZ-types: %d" % (len(settings), len(spec.ssz_types)))

    gen_runner.run_generator("ssz_static", [
        get_ssz_suite(seed, config_name, mode, chaos, cases_if_random)
            for (seed, config_name, mode, chaos, cases_if_random) in settings
    ])
