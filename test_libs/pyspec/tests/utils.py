from eth2spec.debug.encode import encode


def spectest(description: str = None):
    def runner(fn):
        # this wraps the function, to hide that the function actually yielding data.
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
                # put all generated data into a dict.
                for data in fn(*args, **kw):
                    # If there is a type argument, encode it as that type.
                    if len(data) == 3:
                        (key, value, typ) = data
                        out[key] = encode(value, typ)
                    else:
                        # Otherwise, just put the raw value.
                        (key, value) = data
                        out[key] = value
                return out
            else:
                # just complete the function, ignore all yielded data, we are not using it
                for _ in fn(*args, **kw):
                    continue
        return entry
    return runner


def with_args(create_args):
    def runner(fn):
        # this wraps the function, to hide that the function actually yielding data.
        def entry(*args, **kw):
            return fn(*(create_args() + list(args)), **kw)
        return entry
    return runner
