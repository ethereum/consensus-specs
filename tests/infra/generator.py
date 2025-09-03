import functools


def only_generator(func):
    """
    Decorator that only calls the decorated function when test vectors are being generated.
    It should be used before vector_test decorator and other decorators that use it like spec_test.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if kwargs.get("generator_mode", False):
            return func(*args, **kwargs)
        return None

    return wrapper
