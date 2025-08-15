from collections.abc import Iterable

from eth2spec.gen_helpers.gen_base.gen_typing import TestCase
from eth2spec.test.helpers.constants import PHASE0

from .ssz_generic_cases import (
    ssz_basic_progressive_list,
    ssz_basic_vector,
    ssz_bitlist,
    ssz_bitvector,
    ssz_boolean,
    ssz_container,
    ssz_progressive_bitlist,
    ssz_uints,
)


def get_test_cases() -> Iterable[TestCase]:
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
        ("containers", "valid", ssz_container.valid_cases),
        ("containers", "invalid", ssz_container.invalid_cases),
        ("progressive_bitlist", "valid", ssz_progressive_bitlist.valid_cases),
        ("progressive_bitlist", "invalid", ssz_progressive_bitlist.invalid_cases),
        ("uints", "valid", ssz_uints.valid_cases),
        ("uints", "invalid", ssz_uints.invalid_cases),
    ]

    test_cases = []
    for handler_name, suite_name, test_case_fn in test_case_fns:
        for case_name, case_fn in test_case_fn():
            test_cases.append(
                TestCase(
                    fork_name=PHASE0,
                    preset_name="general",
                    runner_name="ssz_generic",
                    handler_name=handler_name,
                    suite_name=suite_name,
                    case_name=case_name,
                    case_fn=case_fn,
                )
            )
    return test_cases
