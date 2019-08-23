from eth2spec.phase0 import spec as spec_phase0
from eth2spec.phase1 import spec as spec_phase1
from eth2spec.utils import bls

from .helpers.genesis import create_genesis_state

from .utils import vector_test, with_meta_tags


def with_state(fn):
    def entry(*args, **kw):
        try:
            kw['state'] = create_genesis_state(spec=kw['spec'], num_validators=spec_phase0.SLOTS_PER_EPOCH * 8)
        except KeyError:
            raise TypeError('Spec decorator must come within state decorator to inject spec into state.')
        return fn(*args, **kw)
    return entry


# BLS is turned off by default *for performance purposes during TESTING*.
# The runner of the test can indicate the preferred setting (test generators prefer BLS to be ON).
# - Some tests are marked as BLS-requiring, and ignore this setting.
#    (tests that express differences caused by BLS, e.g. invalid signatures being rejected)
# - Some other tests are marked as BLS-ignoring, and ignore this setting.
#    (tests that are heavily performance impacted / require unsigned state transitions)
# - Most tests respect the BLS setting.
DEFAULT_BLS_ACTIVE = False


def spec_test(fn):
    # Bls switch must be wrapped by vector_test,
    # to fully go through the yielded bls switch data, before setting back the BLS setting.
    # A test may apply BLS overrides such as @always_bls,
    #  but if it yields data (n.b. @always_bls yields the bls setting), it should be wrapped by this decorator.
    #  This is why @alway_bls has its own bls switch, since the override is beyond the reach of the outer switch.
    return vector_test()(bls_switch(fn))


# shorthand for decorating @spectest() @with_state
def spec_state_test(fn):
    return spec_test(with_state(fn))


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


def never_bls(fn):
    """
    Decorator to apply on ``bls_switch`` decorator to force BLS de-activation. Useful to mark tests as BLS-ignorant.
    This decorator may only be applied to yielding spec test functions, and should be wrapped by vector_test,
     as the yielding needs to complete before setting back the BLS setting.
    """
    def entry(*args, **kw):
        # override bls setting
        kw['bls_active'] = False
        return bls_switch(fn)(*args, **kw)
    return with_meta_tags({'bls_setting': 2})(entry)


def always_bls(fn):
    """
    Decorator to apply on ``bls_switch`` decorator to force BLS activation. Useful to mark tests as BLS-dependent.
    This decorator may only be applied to yielding spec test functions, and should be wrapped by vector_test,
     as the yielding needs to complete before setting back the BLS setting.
    """
    def entry(*args, **kw):
        # override bls setting
        kw['bls_active'] = True
        return bls_switch(fn)(*args, **kw)
    return with_meta_tags({'bls_setting': 1})(entry)


def bls_switch(fn):
    """
    Decorator to make a function execute with BLS ON, or BLS off.
    Based on an optional bool argument ``bls_active``, passed to the function at runtime.
    This decorator may only be applied to yielding spec test functions, and should be wrapped by vector_test,
     as the yielding needs to complete before setting back the BLS setting.
    """
    def entry(*args, **kw):
        old_state = bls.bls_active
        bls.bls_active = kw.pop('bls_active', DEFAULT_BLS_ACTIVE)
        yield from fn(*args, **kw)
        bls.bls_active = old_state
    return entry


all_phases = ['phase0', 'phase1']


def with_all_phases(fn):
    """
    A decorator for running a test with every phase
    """
    return with_phases(all_phases)(fn)


def with_all_phases_except(exclusion_phases):
    """
    A decorator factory for running a tests with every phase except the ones listed
    """
    def decorator(fn):
        return with_phases([phase for phase in all_phases if phase not in exclusion_phases])(fn)
    return decorator


def with_phases(phases):
    """
    Decorator factory that returns a decorator that runs a test for the appropriate phases
    """
    def decorator(fn):
        def run_with_spec_version(spec, *args, **kw):
            kw['spec'] = spec
            return fn(*args, **kw)

        def wrapper(*args, **kw):
            run_phases = phases

            # limit phases if one explicitly specified
            if 'phase' in kw:
                phase = kw.pop('phase')
                if phase not in phases:
                    return
                run_phases = [phase]

            if 'phase0' in run_phases:
                ret = run_with_spec_version(spec_phase0, *args, **kw)
            if 'phase1' in run_phases:
                ret = run_with_spec_version(spec_phase1, *args, **kw)
            return ret
        return wrapper
    return decorator
