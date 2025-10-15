from typing import Any

import inspect

from eth2spec.test import context
from eth2spec.utils.ssz.ssz_impl import serialize
from eth2spec.utils.ssz.ssz_typing import View


def vector_test(description: str = None):
    """
    vector_test decorator: Allow a caller to pass "generator_mode=True" to make the test yield data,
     but behave like a normal test (ignoring the yield, but fully processing) a test when not in "generator_mode"
    This should always be the most outer decorator around functions that yield data.
    This is to deal with silent iteration through yielding function when in a pytest
     context (i.e. not in generator mode).
    :param description: Optional description for the test to add to the metadata.
    :return: Decorator.
    """

    def runner(fn):

        # this wraps the function, to yield type-annotated entries of data.
        # Valid types are:
        #   - "meta": all key-values with this type can be collected by the generator, to put somewhere together.
        #   - "cfg": spec config dictionary
        #   - "ssz": raw SSZ bytes
        #   - "data": a python structure to be encoded by the user.
        def entry(*args, **kw):
            def generator_mode():
                if description is not None:
                    # description can be explicit
                    yield "description", "meta", description

                # transform the yielded data, and add type annotations
                for data in fn(*args, **kw):
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
                    elif isinstance(value, list) and all(
                        [isinstance(el, View | bytes) for el in value]
                    ):
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

            # check generator mode, may be None/else.
            # "pop" removes it, so it is not passed to the inner function.
            if kw.pop("generator_mode", False) is True:
                # return the yielding function as a generator object.
                # Don't yield in this function itself, that would make pytest skip over it.
                return generator_mode()
            else:
                # Just complete the function, ignore all yielded data,
                # we are not using it (or processing it, i.e. nearly zero efficiency loss)
                # Pytest does not support yielded data in the outer function, so we need to wrap it like this.
                for _ in fn(*args, **kw):
                    continue
                return None

        assert context.is_pytest, "vector_test should only be used in a pytest context"
        assert inspect.isgeneratorfunction(fn), "vector_test should only be used on generator functions"

        if inspect.isgeneratorfunction(fn):
            if context.is_pytest:
                # pytest does not support yielded data in the outer function,
                # so we need to wrap it like this.
                def wrapped(*args, **kw):
                    for _ in fn(*args, **kw):
                        continue

                return wrapped
            else:
                return entry
        else:
            return fn

    return runner


def with_meta_tags(tags: dict[str, Any]):
    """
    Decorator factory, yields meta tags (key, value) pairs to the output of the function.
    Useful to build test-vector annotations with.
    :param tags: dict of tags
    :return: Decorator.
    """

    def runner(fn):
        def entry(*args, **kw):
            yielded_any = False
            for part in fn(*args, **kw):
                yield part
                yielded_any = True
            # Do not add tags if the function is not returning a dict at all (i.e. not in generator mode).
            # As a pytest, we do not want to be yielding anything (unsupported by pytest)
            if yielded_any:
                for k, v in tags.items():
                    yield k, "meta", v

        return entry

    return runner
