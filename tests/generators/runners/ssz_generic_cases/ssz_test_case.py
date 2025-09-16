from collections.abc import Callable

from eth2spec.debug.encode import encode
from eth2spec.utils.ssz.ssz_impl import hash_tree_root, serialize
from eth2spec.utils.ssz.ssz_typing import View


def safe_lambda(fn: Callable):
    code = fn.__code__
    if code.co_freevars:
        raise ValueError(
            f"Multi-threading requires all variables to be captured: {list(code.co_freevars)} in {code.co_filename}:{code.co_firstlineno}"
        )
    return fn


def valid_test_case(value_fn: Callable[[], View]):
    def case_fn():
        value = safe_lambda(value_fn)()
        yield "value", "data", encode(value)
        yield "serialized", "ssz", serialize(value)
        yield "root", "meta", "0x" + hash_tree_root(value).hex()

    return case_fn


def invalid_test_case(bytez_fn: Callable[[], bytes]):
    def case_fn():
        yield "serialized", "ssz", safe_lambda(bytez_fn)()

    return case_fn
