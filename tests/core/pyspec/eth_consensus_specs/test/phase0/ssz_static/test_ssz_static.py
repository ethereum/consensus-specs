import hashlib
from inspect import getmembers, isclass
from random import Random

from eth_consensus_specs.debug import encode, random_value
from eth_consensus_specs.test.context import (
    only_generator,
    single_phase,
    spec_targets,
    spec_test,
    with_phases,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import MAINNET, MINIMAL, TESTGEN_FORKS
from eth_consensus_specs.utils.ssz.ssz_impl import (
    hash_tree_root,
    serialize,
)
from eth_consensus_specs.utils.ssz.ssz_typing import Container, ProgressiveContainer
from tests.infra.manifest import Manifest, manifest
from tests.infra.template_test import template_test

MAX_BYTES_LENGTH = 1000
MAX_LIST_LENGTH = 10


@template_test
def _template_ssz_static_tests(
    unique_name: str,
    _manifest: Manifest,
    ssz_type_name,
    phases: list[str],
    mode: random_value.RandomizationMode,
    chaos: bool,
    count: int,
    i: int,
):
    def _deterministic_seed(**kwargs) -> int:
        """Need this since hash() is not deterministic between runs."""
        m = hashlib.sha256()
        for k, v in sorted(kwargs.items()):
            m.update(f"{k}={v}".encode())
        return int.from_bytes(m.digest()[:8], "little")

    @manifest(_manifest)
    @with_phases(phases)
    @with_presets([_manifest.preset_name])
    @spec_test
    @single_phase
    def the_test(spec):
        ssz_type = getattr(spec, ssz_type_name)

        random_mode_name = mode.to_name()
        seed = _deterministic_seed(
            fork_name=_manifest.fork_name,
            preset_name=_manifest.preset_name,
            name=_manifest.handler_name,
            ssz_type_name=ssz_type.__name__,
            random_mode_name=random_mode_name,
            chaos=chaos,
            count=count,
            i=i,
        )

        rng = Random(seed)
        value = random_value.get_random_ssz_object(
            rng, ssz_type, MAX_BYTES_LENGTH, MAX_LIST_LENGTH, mode, chaos
        )
        yield "value", "data", encode.encode(value)
        yield "serialized", "ssz", serialize(value)
        roots_data = {"root": "0x" + hash_tree_root(value).hex()}
        yield "roots", "data", roots_data

    return (the_test, f"test_{unique_name}")


@only_generator("too slow")
def _create_test_cases():
    """
    Create test cases for all SSZ types in all forks and both presets.
    Uses _template_ssz_tests to create the actual tests.
    """

    def _create_test_case(
        phases: list[str],
        preset_name: str,
        ssz_type_name: str,
        mode: random_value.RandomizationMode,
        chaos: bool,
        count: int,
    ):
        random_mode_name = mode.to_name()
        for i in range(count):
            manifest = Manifest(
                preset_name=preset_name,
                runner_name="ssz_static",
                handler_name=ssz_type_name,
                suite_name=f"ssz_{random_mode_name}{'_chaos' if chaos else ''}",
                case_name=f"case_{i}",
            )

            unique_name = f"ssz_{random_mode_name}{'_chaos' if chaos else ''}_{preset_name}_{ssz_type_name}_case_{i}"

            _template_ssz_static_tests(
                unique_name, manifest, ssz_type_name, phases, mode, chaos, count, i
            )

    def _get_spec_ssz_types_names(spec: str) -> list[str]:
        return [
            name
            for (name, value) in getmembers(spec, isclass)
            if issubclass(value, Container | ProgressiveContainer)
            # only the subclasses, not the imported base class
            and value != Container
            and value != ProgressiveContainer
        ]

    def _get_ssz_types_to_specs_mapping() -> dict[str, list[str]]:
        """
        Returns a dictionary where key is a SSZ type name and the value is a list of specs that have it.
        """
        ssz_type_to_specs = {}

        # Check all forks using MINIMAL preset
        for fork in TESTGEN_FORKS:
            spec = spec_targets[MINIMAL][fork]

            # Get all SSZ types for this spec
            ssz_type_names = _get_spec_ssz_types_names(spec)

            # Add each type to the mapping
            for ssz_type_name in ssz_type_names:
                if ssz_type_name not in ssz_type_to_specs:
                    ssz_type_to_specs[ssz_type_name] = []
                ssz_type_to_specs[ssz_type_name].append(fork)

        return ssz_type_to_specs

    settings = []
    for mode in random_value.RandomizationMode:
        settings.append((MINIMAL, mode, False, 30))
    settings.append((MINIMAL, random_value.RandomizationMode.mode_random, True, 30))
    settings.append((MAINNET, random_value.RandomizationMode.mode_random, False, 5))

    ssz_type_to_specs = _get_ssz_types_to_specs_mapping()

    for preset, mode, chaos, cases_if_random in settings:
        count = cases_if_random if chaos or mode.is_changing() else 1
        for ssz_type_name in ssz_type_to_specs:
            _create_test_case(
                ssz_type_to_specs[ssz_type_name], preset, ssz_type_name, mode, chaos, count
            )


_create_test_cases()
