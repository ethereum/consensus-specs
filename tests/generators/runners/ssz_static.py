import hashlib

from random import Random
from typing import Iterable
from inspect import getmembers, isclass

from eth2spec.gen_helpers.gen_base.gen_typing import TestCase, TestCasePart

from eth2spec.debug import random_value, encode
from eth2spec.test.helpers.constants import TESTGEN_FORKS, MINIMAL, MAINNET
from eth2spec.test.context import spec_targets
from eth2spec.utils.ssz.ssz_typing import Container
from eth2spec.utils.ssz.ssz_impl import (
    hash_tree_root,
    serialize,
)


MAX_BYTES_LENGTH = 1000
MAX_LIST_LENGTH = 10


def create_test_case(
    seed: int, typ, mode: random_value.RandomizationMode, chaos: bool
) -> Iterable[TestCasePart]:
    rng = Random(seed)
    value = random_value.get_random_ssz_object(
        rng, typ, MAX_BYTES_LENGTH, MAX_LIST_LENGTH, mode, chaos
    )
    yield "value", "data", encode.encode(value)
    yield "serialized", "ssz", serialize(value)
    roots_data = {"root": "0x" + hash_tree_root(value).hex()}
    yield "roots", "data", roots_data


def get_spec_ssz_types(spec):
    return [
        (name, value)
        for (name, value) in getmembers(spec, isclass)
        if issubclass(value, Container)
        and value != Container  # only the subclasses, not the imported base class
    ]


def deterministic_seed(**kwargs) -> int:
    """Need this since hash() is not deterministic between runs."""
    m = hashlib.sha256()
    for k, v in sorted(kwargs.items()):
        m.update(f"{k}={v}".encode("utf-8"))
    return int.from_bytes(m.digest()[:8], "little")


def ssz_static_cases(
    fork_name: str,
    preset_name: str,
    name,
    ssz_type,
    mode: random_value.RandomizationMode,
    chaos: bool,
    count: int,
):
    random_mode_name = mode.to_name()
    for i in range(count):
        seed = deterministic_seed(
            fork_name=fork_name,
            preset_name=preset_name,
            name=name,
            ssz_type_name=ssz_type.__name__,
            random_mode_name=random_mode_name,
            chaos=chaos,
            count=count,
            i=i,
        )

        def case_fn(seed=seed):
            """Need to bind to seed value."""
            return create_test_case(seed, ssz_type, mode, chaos)

        yield TestCase(
            fork_name=fork_name,
            preset_name=preset_name,
            runner_name="ssz_static",
            handler_name=name,
            suite_name=f"ssz_{random_mode_name}{'_chaos' if chaos else ''}",
            case_name=f"case_{i}",
            case_fn=case_fn,
        )


def get_test_cases() -> Iterable[TestCase]:
    settings = []
    for mode in random_value.RandomizationMode:
        settings.append((MINIMAL, mode, False, 30))
    settings.append((MINIMAL, random_value.RandomizationMode.mode_random, True, 30))
    settings.append((MAINNET, random_value.RandomizationMode.mode_random, False, 5))

    test_cases = []
    for fork in TESTGEN_FORKS:
        for preset, mode, chaos, cases_if_random in settings:
            count = cases_if_random if chaos or mode.is_changing() else 1
            spec = spec_targets[preset][fork]
            for name, ssz_type in get_spec_ssz_types(spec):
                test_cases.extend(
                    ssz_static_cases(fork, preset, name, ssz_type, mode, chaos, count)
                )

    return test_cases
