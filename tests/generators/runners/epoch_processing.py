from collections.abc import Iterable

from eth2spec.gen_helpers.gen_base.gen_typing import TestCase
from eth2spec.gen_helpers.gen_from_tests.gen import get_test_cases_for


def handler_name_fn(mod):
    handler_name = mod.split(".")[-1]
    if handler_name == "test_apply_pending_deposit":
        return "pending_deposits"
    handler_name = handler_name.replace("test_process_", "")
    handler_name = handler_name.replace("test_apply_", "")
    return handler_name


def get_test_cases() -> Iterable[TestCase]:
    return get_test_cases_for("epoch_processing", handler_name_fn=handler_name_fn)
