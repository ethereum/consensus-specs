from collections.abc import Iterable

from eth_consensus_specs.gen_helpers.gen_base.gen_typing import TestCase
from eth_consensus_specs.gen_helpers.gen_from_tests.gen import get_test_cases_for


def get_test_cases() -> Iterable[TestCase]:
    return get_test_cases_for("rewards")
