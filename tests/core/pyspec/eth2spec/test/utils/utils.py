from typing import Any


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
