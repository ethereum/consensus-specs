from eth2spec.phase0 import spec

from .helpers import create_genesis_state

from .utils import spectest, with_args

# Provides a genesis state as first argument to the function decorated with this
with_state = with_args(lambda: [create_genesis_state(spec.SLOTS_PER_EPOCH * 8)])


# shorthand for decorating @with_state @spectest()
def spec_state_test(fn):
    return with_state(spectest()(fn))


def expect_assertion_error(fn):
    bad = False
    try:
        fn()
        bad = True
    except AssertionError:
        pass
    except IndexError:
        # Index errors are special; the spec is not explicit on bound checking, an IndexError is like a failed assert.
        pass
    if bad:
        raise AssertionError('expected an assertion error, but got none.')
