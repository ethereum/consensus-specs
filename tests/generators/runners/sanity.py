from typing import Iterable

from eth2spec.gen_helpers.gen_base.gen_typing import TestCase
from eth2spec.gen_helpers.gen_from_tests.gen import get_test_cases_for


def handler_name_fn(mod):
    handler_name = mod.split(".")[-1]
    if handler_name == "test_deposit_transition":
        return "blocks"
    return handler_name.replace("test_", "")


def get_test_cases() -> Iterable[TestCase]:
    return get_test_cases_for("sanity", handler_name_fn=handler_name_fn)
