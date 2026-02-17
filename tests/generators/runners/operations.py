from collections.abc import Iterable

from eth_consensus_specs.gen_helpers.gen_base.gen_typing import TestCase
from eth_consensus_specs.gen_helpers.gen_from_tests.gen import get_test_cases_for


def handler_name_fn(mod):
    handler_name = mod.split(".")[-1]
    if handler_name == "test_process_sync_aggregate_random":
        return "sync_aggregate"
    return handler_name.replace("test_process_", "")


def get_test_cases() -> Iterable[TestCase]:
    return get_test_cases_for("operations", pkg="block_processing", handler_name_fn=handler_name_fn)
