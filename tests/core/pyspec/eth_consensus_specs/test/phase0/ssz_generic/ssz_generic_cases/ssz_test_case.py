from collections.abc import Callable
from random import Random

from eth_consensus_specs.debug.encode import encode
from eth_consensus_specs.utils.ssz.ssz_impl import deserialize, hash_tree_root, serialize
from eth_consensus_specs.utils.ssz.ssz_typing import View


def safe_lambda(fn: Callable):
    code = fn.__code__
    if code.co_freevars:
        raise ValueError(
            f"Multi-threading requires all variables to be captured: {list(code.co_freevars)} in {code.co_filename}:{code.co_firstlineno}"
        )
    return fn


def capture_seed(rng: Random = None):
    return rng.randint(0, 2**32 - 1) if rng is not None else None


def valid_test_case(value_fn: Callable[[], View], rng: Random = None):
    seed = capture_seed(rng)

    def case_fn():
        if seed is not None:
            value = safe_lambda(value_fn)(rng=Random(seed))
        else:
            value = safe_lambda(value_fn)()
        serialized = serialize(value)
        assert deserialize(value.__class__, serialized) == value
        yield "value", "data", encode(value)
        yield "serialized", "ssz", serialized
        yield "root", "meta", "0x" + hash_tree_root(value).hex()

    return case_fn


def invalid_test_case(typ: type[View], bytez_fn: Callable[[], bytes], rng: Random = None):
    seed = capture_seed(rng)

    def case_fn():
        if seed is not None:
            serialized = safe_lambda(bytez_fn)(rng=Random(seed))
        else:
            serialized = safe_lambda(bytez_fn)()
        try:
            _ = deserialize(typ, serialized)
        except Exception:
            yield "serialized", "ssz", serialized
            return
        code = bytez_fn.__code__
        raise ValueError(
            f"Invalid {typ.type_repr()} data should not deserialize: {serialized.hex()} in {code.co_filename}:{code.co_firstlineno}"
        )

    return case_fn
