from eth2spec.phase0 import spec as spec_phase0
from eth2spec.phase1 import spec as spec_phase1
from eth2spec.utils import bls

from .helpers.genesis import create_genesis_state

from .utils import vector_test, with_meta_tags

from random import Random
from typing import Any, Callable, Sequence, TypedDict, Protocol

from importlib import reload


def reload_specs():
    reload(spec_phase0)
    reload(spec_phase1)


# Some of the Spec module functionality is exposed here to deal with phase-specific changes.

# TODO: currently phases are defined as python modules.
# It would be better if they would be more well-defined interfaces for stronger typing.
class Spec(Protocol):
    version: str


class Phase0(Spec):
    ...


class Phase1(Spec):
    def upgrade_to_phase1(self, state: spec_phase0.BeaconState) -> spec_phase1.BeaconState:
        ...


# add transfer, bridge, etc. as the spec evolves
class SpecForks(TypedDict, total=False):
    phase0: Phase0
    phase1: Phase1


def with_custom_state(balances_fn: Callable[[Any], Sequence[int]],
                      threshold_fn: Callable[[Any], int]):
    def deco(fn):
        def entry(*args, spec: Spec, phases: SpecForks, **kw):
            try:
                p0 = phases["phase0"]
                balances = balances_fn(p0)
                activation_threshold = threshold_fn(p0)

                state = create_genesis_state(spec=p0, validator_balances=balances,
                                             activation_threshold=activation_threshold)
                if spec.fork == 'phase1':
                    # TODO: instead of upgrading a test phase0 genesis state we can also write a phase1 state helper.
                    # Decide based on performance/consistency results later.
                    state = phases["phase1"].upgrade_to_phase1(state)

                kw['state'] = state
            except KeyError:
                raise TypeError('Spec decorator must come within state decorator to inject spec into state.')
            return fn(*args, spec=spec, phases=phases, **kw)
        return entry
    return deco


def default_activation_threshold(spec):
    """
    Helper method to use the default balance activation threshold for state creation for tests.
    Usage: `@with_custom_state(threshold_fn=default_activation_threshold, ...)`
    """
    return spec.MAX_EFFECTIVE_BALANCE


def zero_activation_threshold(spec):
    """
    Helper method to use 0 gwei as the activation threshold for state creation for tests.
    Usage: `@with_custom_state(threshold_fn=zero_activation_threshold, ...)`
    """
    return 0


def default_balances(spec):
    """
    Helper method to create a series of default balances.
    Usage: `@with_custom_state(balances_fn=default_balances, ...)`
    """
    num_validators = spec.SLOTS_PER_EPOCH * 8
    return [spec.MAX_EFFECTIVE_BALANCE] * num_validators


with_state = with_custom_state(default_balances, default_activation_threshold)


def low_balances(spec):
    """
    Helper method to create a series of low balances.
    Usage: `@with_custom_state(balances_fn=low_balances, ...)`
    """
    num_validators = spec.SLOTS_PER_EPOCH * 8
    # Technically the balances cannot be this low starting from genesis, but it is useful for testing
    low_balance = 18 * 10 ** 9
    return [low_balance] * num_validators


def misc_balances(spec):
    """
    Helper method to create a series of balances that includes some misc. balances.
    Usage: `@with_custom_state(balances_fn=misc_balances, ...)`
    """
    num_validators = spec.SLOTS_PER_EPOCH * 8
    balances = [spec.MAX_EFFECTIVE_BALANCE * 2 * i // num_validators for i in range(num_validators)]
    rng = Random(1234)
    rng.shuffle(balances)
    return balances


def low_single_balance(spec):
    """
    Helper method to create a single of balance of 1 Gwei.
    Usage: `@with_custom_state(balances_fn=low_single_balance, ...)`
    """
    return [1]


def single_phase(fn):
    """
    Decorator that filters out the phases data.
    most state tests only focus on behavior of a single phase (the "spec").
    This decorator is applied as part of spec_state_test(fn).
    """
    def entry(*args, **kw):
        if 'phases' in kw:
            kw.pop('phases')
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


# shorthand for decorating @spectest() @with_state @single_phase
def spec_state_test(fn):
    return spec_test(with_state(single_phase(fn)))


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
        res = fn(*args, **kw)
        if res is not None:
            yield from res
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


def with_phases(phases, other_phases=None):
    """
    Decorator factory that returns a decorator that runs a test for the appropriate phases.
    Additional phases that do not initially run, but are made available through the test, are optional.
    """
    def decorator(fn):
        def wrapper(*args, **kw):
            run_phases = phases

            # limit phases if one explicitly specified
            if 'phase' in kw:
                phase = kw.pop('phase')
                if phase not in phases:
                    return
                run_phases = [phase]

            available_phases = set(run_phases)
            if other_phases is not None:
                available_phases += set(other_phases)

            # TODO: test state is dependent on phase0 but is immediately transitioned to phase1.
            #  A new state-creation helper for phase 1 may be in place, and then phase1+ tests can run without phase0
            available_phases.add('phase0')

            phase_dir = {}
            if 'phase0' in available_phases:
                phase_dir['phase0'] = spec_phase0
            if 'phase1' in available_phases:
                phase_dir['phase1'] = spec_phase1

            # return is ignored whenever multiple phases are ran. If
            if 'phase0' in run_phases:
                ret = fn(spec=spec_phase0, phases=phase_dir, *args, **kw)
            if 'phase1' in run_phases:
                ret = fn(spec=spec_phase1, phases=phase_dir, *args, **kw)
            return ret
        return wrapper
    return decorator
