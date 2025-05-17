from typing import Callable

from eth2spec.debug.encode import encode
from eth2spec.utils.ssz.ssz_impl import hash_tree_root, serialize
from eth2spec.utils.ssz.ssz_typing import View


def valid_test_case(value_fn: Callable[[], View]):
    def case_fn():
        value = value_fn()
        yield "value", "data", encode(value)
        yield "serialized", "ssz", serialize(value)
        yield "root", "meta", "0x" + hash_tree_root(value).hex()

    return case_fn


def invalid_test_case(bytez_fn: Callable[[], bytes]):
    def case_fn():
        yield "serialized", "ssz", bytez_fn()

    return case_fn
