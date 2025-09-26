from collections.abc import Callable

from eth2spec.debug.encode import encode
from eth2spec.utils.ssz.ssz_impl import deserialize, hash_tree_root, serialize
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
        serialized = serialize(value)
        assert deserialize(value.__class__, serialized) == value
        yield "value", "data", encode(value)
        yield "serialized", "ssz", serialized
        yield "root", "meta", "0x" + hash_tree_root(value).hex()

    return case_fn


def invalid_test_case(typ: type[View], bytez_fn: Callable[[], bytes]):
    def case_fn():
        serialized = safe_lambda(bytez_fn)()
        try:
            _ = deserialize(typ, serialized)
            assert False  # Invalid data should not deserialize
        except Exception:
            yield "serialized", "ssz", serialized

    return case_fn
