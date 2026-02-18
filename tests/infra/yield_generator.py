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
    Decorator to make a test function optionally operate in "generator mode".

    This decorator is intended for test functions that yield data (i.e. are generator
    functions). It lets callers request a generator object from the test by passing
    generator_mode=True as a keyword when calling the decorated function. When
    generator_mode is not requested the decorator will execute the generator to
    completion and ignore all yielded values so the function behaves like a normal
    (non-yielding) test function in test runners that do not support yielded tests.
    """

    def wrapper_generator(*args, **kw) -> Generator | None:
        # check generator mode, may be None/else.
        # "pop" removes it, so it is not passed to the inner function.
        if kw.pop("generator_mode", False) is True:
            # return the yielding function as a generator object.
            return _yield_generator_post_processing(fn(*args, **kw))
        else:
            # Just complete the function, ignore all yielded data
            for _ in fn(*args, **kw):
                continue

    if inspect.isgeneratorfunction(fn):
        # Lazy import to avoid circular dependency with eth_consensus_specs.test.context
        from eth_consensus_specs.test import context  # noqa: PLC0415

        if not context.is_pytest:
            return wrapper_generator
        else:
            # pytest does not support yielded data in the outer function,
            # so we need to wrap it like this.
            return _drain_wrapper(fn)
    else:
        # If the function is not a generator, just return it as-is.
        return fn
