from eth2spec.phase0 import spec
from eth2spec.utils import bls

from .helpers import create_genesis_state

from .utils import spectest, with_args

# Provides a genesis state as first argument to the function decorated with this
with_state = with_args(lambda: [create_genesis_state(spec.SLOTS_PER_EPOCH * 8)])


# shorthand for decorating @with_state @spectest()
def spec_state_test(fn):
    return with_state(bls_switch(spectest()(fn)))


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


def always_bls(fn):
    """
    Decorator to apply on ``bls_switch`` decorator to force BLS activation. Useful to mark tests as BLS-dependent.
    """
    def entry(*args, **kw):
        # override bls setting
        kw['bls_active'] = True
        fn(*args, **kw)
    return entry


def bls_switch(fn):
    """
    Decorator to make a function execute with BLS ON, or BLS off.
    Based on an optional bool argument ``bls_active``, passed to the function at runtime.
    """
    def entry(*args, **kw):
        old_state = bls.bls_active
        bls.bls_active = kw.pop('bls_active', False)
        fn(*args, **kw)
        bls.bls_active = old_state
    return entry
