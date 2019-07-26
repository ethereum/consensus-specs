from typing import Dict, Any
from eth2spec.debug.encode import encode
from eth2spec.utils.ssz.ssz_typing import SSZValue


def spectest(description: str = None):
    """
    Spectest decorator, should always be the most outer decorator around functions that yield data.
    to deal with silent iteration through yielding function when in a pytest context (i.e. not in generator mode).
    :param description: Optional description for the test to add to the metadata.
    :return: Decorator.
    """
    def runner(fn):
        # this wraps the function, to yield type-annotated entries of data.
        # Valid types are:
        #   - "meta": all key-values with this type can be collected by the generator, to put somewhere together.
        #   - "ssz": raw SSZ bytes
        #   - "data": a python structure to be encoded by the user.
        def entry(*args, **kw):
            # check generator mode, may be None/else.
            # "pop" removes it, so it is not passed to the inner function.
            if kw.pop('generator_mode', False) is True:

                if description is not None:
                    # description can be explicit
                    yield 'description', 'meta', description

                # transform the yielded data, and add type annotations
                for data in fn(*args, **kw):
                    # If there is a type argument, encode it as that type.
                    if len(data) == 3:
                        (key, value, typ) = data
                        yield key, 'data', encode(value, typ)
                        # TODO: add SSZ bytes as second output
                    else:
                        # Otherwise, try to infer the type, but keep it as-is if it's not a SSZ type or bytes.
                        (key, value) = data
                        if isinstance(value, (SSZValue, bytes)):
                            yield key, 'data', encode(value)
                            # TODO: add SSZ bytes as second output
                        elif isinstance(value, list) and all([isinstance(el, (SSZValue, bytes)) for el in value]):
                            for i, el in enumerate(value):
                                yield f'{key}_{i}', 'data', encode(el)
                                # TODO: add SSZ bytes as second output
                            yield f'{key}_count', 'meta', len(value)
                        else:
                            # not a ssz value.
                            # It could be vector or bytes still, but it is a rare case,
                            # and lists can't be inferred fully (generics lose element type).
                            # In such cases, explicitly state the type of the yielded value as a third yielded object.
                            # The data will now just be yielded as any python data,
                            #  something that should be encodeable by the generator runner.
                            yield key, 'data', value
            else:
                # Just complete the function, ignore all yielded data,
                # we are not using it (or processing it, i.e. nearly zero efficiency loss)
                # Pytest does not support yielded data in the outer function, so we need to wrap it like this.
                for _ in fn(*args, **kw):
                    continue
                return None

        return entry

    return runner


def with_meta_tags(tags: Dict[str, Any]):
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
                for k, v in tags:
                    yield k, 'meta', v
        return entry
    return runner

