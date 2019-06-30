from typing import Dict, Any, Callable, Iterable
from eth2spec.debug.encode import encode
from eth2spec.utils.ssz.ssz_typing import SSZValue


def spectest(description: str = None):
    def runner(fn):
        # this wraps the function, to hide that the function actually is yielding data, instead of returning once.
        def entry(*args, **kw):
            # check generator mode, may be None/else.
            # "pop" removes it, so it is not passed to the inner function.
            if kw.pop('generator_mode', False) is True:
                out = {}
                if description is None:
                    # fall back on function name for test description
                    name = fn.__name__
                    if name.startswith('test_'):
                        name = name[5:]
                    out['description'] = name
                else:
                    # description can be explicit
                    out['description'] = description
                has_contents = False
                # put all generated data into a dict.
                for data in fn(*args, **kw):
                    has_contents = True
                    # If there is a type argument, encode it as that type.
                    if len(data) == 3:
                        (key, value, typ) = data
                        out[key] = encode(value, typ)
                    else:
                        # Otherwise, try to infer the type, but keep it as-is if it's not a SSZ type or bytes.
                        (key, value) = data
                        if isinstance(value, (SSZValue, bytes)):
                            out[key] = encode(value)
                        elif isinstance(value, list) and all([isinstance(el, (SSZValue, bytes)) for el in value]):
                            out[key] = [encode(el) for el in value]
                        else:
                            # not a ssz value.
                            # It could be vector or bytes still, but it is a rare case,
                            # and lists can't be inferred fully (generics lose element type).
                            # In such cases, explicitly state the type of the yielded value as a third yielded object.
                            out[key] = value
                if has_contents:
                    return out
                else:
                    return None
            else:
                # just complete the function, ignore all yielded data, we are not using it
                for _ in fn(*args, **kw):
                    continue
                return None
        return entry
    return runner


def with_tags(tags: Dict[str, Any]):
    """
    Decorator factory, adds tags (key, value) pairs to the output of the function.
    Useful to build test-vector annotations with.
    This decorator is applied after the ``spectest`` decorator is applied.
    :param tags: dict of tags
    :return: Decorator.
    """
    def runner(fn):
        def entry(*args, **kw):
            fn_out = fn(*args, **kw)
            # do not add tags if the function is not returning a dict at all (i.e. not in generator mode)
            if fn_out is None:
                return None
            return {**tags, **fn_out}
        return entry
    return runner


def with_args(create_args: Callable[[], Iterable[Any]]):
    """
    Decorator factory, adds given extra arguments to the decorated function.
    :param create_args: function to create arguments with.
    :return: Decorator.
    """
    def runner(fn):
        # this wraps the function, to hide that the function actually yielding data.
        def entry(*args, **kw):
            return fn(*(list(create_args()) + list(args)), **kw)
        return entry
    return runner
