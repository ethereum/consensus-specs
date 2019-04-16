from eth_utils import (
    to_tuple, to_dict
)
from preset_loader import loader
from eth2spec.phase0 import spec
from eth2spec.utils.minimal_ssz import hash_tree_root, serialize
from eth2spec.debug import random_value, encode

from gen_base import gen_runner, gen_suite, gen_typing
from random import Random


@to_dict
def render_test_case(rng: Random, name):
    typ = spec.get_ssz_type_by_name(name)
    # TODO: vary randomization args
    value = random_value.get_random_ssz_object(rng, typ, 100, 10, random_value.RandomizationMode.mode_random, False)
    yield "type_name", name
    yield "value", encode.encode(value, typ)
    yield "serialized", serialize(value)
    yield "root", '0x' + hash_tree_root(value).hex()


@to_tuple
def ssz_static_cases(rng: Random):
    for type_name in spec.ssz_types:
        # TODO more types
        for i in range(10):
            render_test_case(rng, type_name)


def min_ssz_suite(configs_path: str) -> gen_typing.TestSuiteOutput:
    presets = loader.load_presets(configs_path, 'minimal')
    spec.apply_constants_preset(presets)
    rng = Random(123)

    return ("ssz_min_values_minimal", "core", gen_suite.render_suite(
        title="ssz testing, with minimal config",
        summary="Test suite for ssz serialization and hash-tree-root",
        forks_timeline="testing",
        forks=["phase0"],
        config="minimal",
        runner="ssz",
        handler="static",
        test_cases=ssz_static_cases(rng)))

# TODO more suites

# Variation in: randomization-mode, chaos mode, configuration


if __name__ == "__main__":
    gen_runner.run_generator("ssz_static", [
        min_ssz_suite
    ])
