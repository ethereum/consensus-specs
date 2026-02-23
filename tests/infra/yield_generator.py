import functools
import inspect
from collections.abc import Generator, Iterable

from eth_consensus_specs.utils.ssz.ssz_impl import serialize
from eth_consensus_specs.utils.ssz.ssz_typing import View


def _yield_generator_post_processing(vector: Iterable) -> Generator:
    # this wraps the function, to yield type-annotated entries of data.
    # Valid types are:
    #   - "meta": all key-values with this type can be collected by the generator, to put somewhere together.
    #   - "cfg": spec config dictionary
    #   - "ssz": raw SSZ bytes
    #   - "data": a python structure to be encoded by the user.
    # transform the yielded data, and add type annotations
    for data in vector:
        # if not 2 items, then it is assumed to be already formatted with a type:
        # e.g. ("bls_setting", "meta", 1)
        if len(data) != 2:
            yield data
            continue
        # Try to infer the type, but keep it as-is if it's not a SSZ type or bytes.
        (key, value) = data
        if value is None:
            continue
        if isinstance(value, View):
            yield key, "ssz", serialize(value)
        elif isinstance(value, bytes):
            yield key, "ssz", value
        elif isinstance(value, list) and all([isinstance(el, View | bytes) for el in value]):
            for i, el in enumerate(value):
                if isinstance(el, View):
                    yield f"{key}_{i}", "ssz", serialize(el)
                elif isinstance(el, bytes):
                    yield f"{key}_{i}", "ssz", el
            yield f"{key}_count", "meta", len(value)
        else:
            # Not a ssz value.
            # The data will now just be yielded as any python data,
            #  something that should be encodable by the generator runner.
            yield key, "data", value


def _drain_wrapper(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kw):
        for _ in fn(*args, **kw):
            continue

    return wrapper


def vector_test(fn):
    """
    Decorator that wraps generator test functions based on context.is_generator.

    When context.is_generator is True, the decorated function returns a generator
    with post-processing applied to its yielded data. When context.is_generator is
    False, the decorator drains the generator to completion, ignoring all yielded
    values so the function behaves like a normal test in pytest.
    """

    def wrapper_generator(*args, **kw) -> Generator:
        return _yield_generator_post_processing(fn(*args, **kw))

    if inspect.isgeneratorfunction(fn):
        # Lazy import to avoid circular dependency with eth_consensus_specs.test.context
        from eth_consensus_specs.test import context  # noqa: PLC0415

        if context.is_generator:
            return wrapper_generator
        else:
            # when pytest is not running in generator mode, we should drain the yields
            # so we need to wrap it like this.
            return _drain_wrapper(fn)
    else:
        # If the function is not a generator, just return it as-is.
        return fn
