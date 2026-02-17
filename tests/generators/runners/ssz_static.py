from collections.abc import Iterable

from eth_consensus_specs.gen_helpers.gen_base.gen_typing import TestCase
from tests.core.pyspec.eth_consensus_specs.gen_helpers.gen_from_tests.gen import get_test_cases_for


def get_test_cases() -> Iterable[TestCase]:
    # Use the backup implementation for now
    return get_test_cases_for("ssz_static", pkg="ssz_static")
