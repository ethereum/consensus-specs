import pytest

from eth_consensus_specs.test import context
from eth_consensus_specs.test.context import (
    only_generator,
    single_phase,
    spec_test,
    with_phases,
)
from eth_consensus_specs.test.exceptions import SkippedTest
from eth_consensus_specs.test.helpers.constants import PHASE0
from tests.infra.manifest import Manifest, manifest
from tests.infra.template_test import template_test

from .ssz_generic_cases import (
    ssz_basic_progressive_list,
    ssz_basic_vector,
    ssz_bitlist,
    ssz_bitvector,
    ssz_boolean,
    ssz_compatible_union,
    ssz_container,
    ssz_progressive_bitlist,
    ssz_progressive_container,
    ssz_uints,
)


@template_test
def _template_ssz_generic_test(handler_name, suite_name, case_name, case_fn):
    _manifest = Manifest(
        preset_name="general",
        runner_name="ssz_generic",
        handler_name=handler_name,
        suite_name=suite_name,
        case_name=case_name,
    )

    @manifest(_manifest)
    @only_generator("ssz_generic test for reference test generation")
    @with_phases([PHASE0])
    @spec_test
    @single_phase
    def the_test(spec):
        try:
            yield from case_fn()
        except SkippedTest as e:
            if context.is_pytest:
                pytest.skip(str(e))
            raise

    return (the_test, f"test_{handler_name}_{suite_name}_{case_name}")


test_case_fns = [
    ("basic_progressive_list", "valid", ssz_basic_progressive_list.valid_cases),
    ("basic_progressive_list", "invalid", ssz_basic_progressive_list.invalid_cases),
    ("basic_vector", "valid", ssz_basic_vector.valid_cases),
    ("basic_vector", "invalid", ssz_basic_vector.invalid_cases),
    ("bitlist", "valid", ssz_bitlist.valid_cases),
    ("bitlist", "invalid", ssz_bitlist.invalid_cases),
    ("bitvector", "valid", ssz_bitvector.valid_cases),
    ("bitvector", "invalid", ssz_bitvector.invalid_cases),
    ("boolean", "valid", ssz_boolean.valid_cases),
    ("boolean", "invalid", ssz_boolean.invalid_cases),
    ("compatible_unions", "valid", ssz_compatible_union.valid_cases),
    ("compatible_unions", "invalid", ssz_compatible_union.invalid_cases),
    ("containers", "valid", ssz_container.valid_cases),
    ("containers", "invalid", ssz_container.invalid_cases),
    ("progressive_bitlist", "valid", ssz_progressive_bitlist.valid_cases),
    ("progressive_bitlist", "invalid", ssz_progressive_bitlist.invalid_cases),
    ("progressive_containers", "valid", ssz_progressive_container.valid_cases),
    ("progressive_containers", "invalid", ssz_progressive_container.invalid_cases),
    ("uints", "valid", ssz_uints.valid_cases),
    ("uints", "invalid", ssz_uints.invalid_cases),
]

for _handler_name, _suite_name, _cases_fn in test_case_fns:
    for _case_name, _case_fn in _cases_fn():
        _template_ssz_generic_test(_handler_name, _suite_name, _case_name, _case_fn)
