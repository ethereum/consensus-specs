import pytest
from dataclasses import dataclass
import importlib
from eth_utils import encode_hex

from eth2spec.phase0 import mainnet as spec_phase0_mainnet, minimal as spec_phase0_minimal
from eth2spec.altair import mainnet as spec_altair_mainnet, minimal as spec_altair_minimal
from eth2spec.bellatrix import mainnet as spec_bellatrix_mainnet, minimal as spec_bellatrix_minimal
from eth2spec.utils import bls

from .exceptions import SkippedTest
from .helpers.constants import (
    PHASE0, ALTAIR, BELLATRIX, MINIMAL, MAINNET,
    ALL_PHASES, FORKS_BEFORE_ALTAIR, FORKS_BEFORE_BELLATRIX,
    ALL_FORK_UPGRADES,
)
from .helpers.typing import SpecForkName, PresetBaseName
from .helpers.genesis import create_genesis_state
from .utils import (
    vector_test,
    with_meta_tags,
)

from random import Random
from typing import Any, Callable, Sequence, TypedDict, Protocol, Dict

from lru import LRU

# Without pytest CLI arg or pyspec-test-generator 'preset' argument, this will be the config to apply.
DEFAULT_TEST_PRESET = MINIMAL

# Without pytest CLI arg or pyspec-test-generator 'run-phase' argument, this will be the config to apply.
DEFAULT_PYTEST_FORKS = ALL_PHASES


# TODO: currently phases are defined as python modules.
# It would be better if they would be more well-defined interfaces for stronger typing.

class Configuration(Protocol):
    PRESET_BASE: str


class Spec(Protocol):
    fork: str
    config: Configuration


class SpecPhase0(Spec):
    ...


class SpecAltair(Spec):
    ...


class SpecBellatrix(Spec):
    ...


@dataclass(frozen=True)
class ForkMeta:
    pre_fork_name: str
    post_fork_name: str
    fork_epoch: int


spec_targets: Dict[PresetBaseName, Dict[SpecForkName, Spec]] = {
    MINIMAL: {
        PHASE0: spec_phase0_minimal,
        ALTAIR: spec_altair_minimal,
        BELLATRIX: spec_bellatrix_minimal,
    },
    MAINNET: {
        PHASE0: spec_phase0_mainnet,
        ALTAIR: spec_altair_mainnet,
        BELLATRIX: spec_bellatrix_mainnet,
    },
}


class SpecForks(TypedDict, total=False):
    PHASE0: SpecPhase0
    ALTAIR: SpecAltair
    BELLATRIX: SpecBellatrix


def _prepare_state(balances_fn: Callable[[Any], Sequence[int]], threshold_fn: Callable[[Any], int],
                   spec: Spec, phases: SpecForks):
    balances = balances_fn(spec)
    activation_threshold = threshold_fn(spec)
    state = create_genesis_state(spec=spec, validator_balances=balances,
                                 activation_threshold=activation_threshold)
    return state


_custom_state_cache_dict = LRU(size=10)


def with_custom_state(balances_fn: Callable[[Any], Sequence[int]],
                      threshold_fn: Callable[[Any], int]):
    def deco(fn):
        def entry(*args, spec: Spec, phases: SpecForks, **kw):
            # make a key for the state, unique to the fork + config (incl preset choice) and balances/activations
            key = (spec.fork, spec.config.__hash__(), spec.__file__, balances_fn, threshold_fn)
            global _custom_state_cache_dict
            if key not in _custom_state_cache_dict:
                state = _prepare_state(balances_fn, threshold_fn, spec, phases)
                _custom_state_cache_dict[key] = state.get_backing()

            # Take an entry out of the LRU.
            # No copy is necessary, as we wrap the immutable backing with a new view.
            state = spec.BeaconState(backing=_custom_state_cache_dict[key])
            kw['state'] = state
            return fn(*args, spec=spec, phases=phases, **kw)
        return entry
    return deco


def default_activation_threshold(spec: Spec):
    """
    Helper method to use the default balance activation threshold for state creation for tests.
    Usage: `@with_custom_state(threshold_fn=default_activation_threshold, ...)`
    """
    return spec.MAX_EFFECTIVE_BALANCE


def zero_activation_threshold(spec: Spec):
    """
    Helper method to use 0 gwei as the activation threshold for state creation for tests.
    Usage: `@with_custom_state(threshold_fn=zero_activation_threshold, ...)`
    """
    return 0


def default_balances(spec: Spec):
    """
    Helper method to create a series of default balances.
    Usage: `@with_custom_state(balances_fn=default_balances, ...)`
    """
    num_validators = spec.SLOTS_PER_EPOCH * 8
    return [spec.MAX_EFFECTIVE_BALANCE] * num_validators


def scaled_churn_balances(spec: Spec):
    """
    Helper method to create enough validators to scale the churn limit.
    (This is *firmly* over the churn limit -- thus the +2 instead of just +1)
    See the second argument of ``max`` in ``get_validator_churn_limit``.
    Usage: `@with_custom_state(balances_fn=scaled_churn_balances, ...)`
    """
    num_validators = spec.config.CHURN_LIMIT_QUOTIENT * (2 + spec.config.MIN_PER_EPOCH_CHURN_LIMIT)
    return [spec.MAX_EFFECTIVE_BALANCE] * num_validators


with_state = with_custom_state(default_balances, default_activation_threshold)


def low_balances(spec: Spec):
    """
    Helper method to create a series of low balances.
    Usage: `@with_custom_state(balances_fn=low_balances, ...)`
    """
    num_validators = spec.SLOTS_PER_EPOCH * 8
    # Technically the balances cannot be this low starting from genesis, but it is useful for testing
    low_balance = 18 * 10 ** 9
    return [low_balance] * num_validators


def misc_balances(spec: Spec):
    """
    Helper method to create a series of balances that includes some misc. balances.
    Usage: `@with_custom_state(balances_fn=misc_balances, ...)`
    """
    num_validators = spec.SLOTS_PER_EPOCH * 8
    balances = [spec.MAX_EFFECTIVE_BALANCE * 2 * i // num_validators for i in range(num_validators)]
    rng = Random(1234)
    rng.shuffle(balances)
    return balances


def misc_balances_in_default_range_with_many_validators(spec: Spec):
    """
    Helper method to create a series of balances that includes some misc. balances but
    none that are below the ``EJECTION_BALANCE``.
    """
    # Double validators to facilitate randomized testing
    num_validators = spec.SLOTS_PER_EPOCH * 8 * 2
    floor = spec.config.EJECTION_BALANCE + spec.EFFECTIVE_BALANCE_INCREMENT
    balances = [
        max(spec.MAX_EFFECTIVE_BALANCE * 2 * i // num_validators, floor) for i in range(num_validators)
    ]
    rng = Random(1234)
    rng.shuffle(balances)
    return balances


def low_single_balance(spec: Spec):
    """
    Helper method to create a single of balance of 1 Gwei.
    Usage: `@with_custom_state(balances_fn=low_single_balance, ...)`
    """
    return [1]


def large_validator_set(spec: Spec):
    """
    Helper method to create a large series of default balances.
    Usage: `@with_custom_state(balances_fn=default_balances, ...)`
    """
    num_validators = 2 * spec.SLOTS_PER_EPOCH * spec.MAX_COMMITTEES_PER_SLOT * spec.TARGET_COMMITTEE_SIZE
    return [spec.MAX_EFFECTIVE_BALANCE] * num_validators


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


# BLS is turned on by default, it can be disabled in tests by overriding this, or using `--disable-bls`.
# *This is for performance purposes during TESTING, DO NOT DISABLE IN PRODUCTION*.
# The runner of the test can indicate the preferred setting (test generators prefer BLS to be ON).
# - Some tests are marked as BLS-requiring, and ignore this setting.
#    (tests that express differences caused by BLS, e.g. invalid signatures being rejected)
# - Some other tests are marked as BLS-ignoring, and ignore this setting.
#    (tests that are heavily performance impacted / require unsigned state transitions)
# - Most tests respect the BLS setting.
DEFAULT_BLS_ACTIVE = True


is_pytest = True


def dump_skipping_message(reason: str) -> None:
    message = f"[Skipped test] {reason}"
    if is_pytest:
        pytest.skip(message)
    else:
        raise SkippedTest(message)


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


def spec_configured_state_test(conf):
    overrides = with_config_overrides(conf)

    def decorator(fn):
        return spec_test(overrides(with_state(single_phase(fn))))
    return decorator


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


def disable_process_reveal_deadlines(fn):
    """
    Decorator to make a function execute with `process_reveal_deadlines` OFF.
    This is for testing long-range epochs transition without considering the reveal-deadline slashing effect.
    """
    def entry(*args, spec: Spec, **kw):
        if hasattr(spec, 'process_reveal_deadlines'):
            old_state = spec.process_reveal_deadlines
            spec.process_reveal_deadlines = lambda state: None

        yield from fn(*args, spec=spec, **kw)

        if hasattr(spec, 'process_reveal_deadlines'):
            spec.process_reveal_deadlines = old_state

    return with_meta_tags({'reveal_deadlines_setting': 1})(entry)


def with_all_phases(fn):
    """
    A decorator for running a test with every phase
    """
    return with_phases(ALL_PHASES)(fn)


def with_all_phases_except(exclusion_phases):
    """
    A decorator factory for running a tests with every phase except the ones listed
    """
    def decorator(fn):
        return with_phases([phase for phase in ALL_PHASES if phase not in exclusion_phases])(fn)
    return decorator


def _get_preset_targets(kw):
    preset_name = DEFAULT_TEST_PRESET
    if 'preset' in kw:
        preset_name = kw.pop('preset')
    return spec_targets[preset_name]


def _get_run_phases(phases, kw):
    """
    Return the fork names for the base `spec` in test cases
    """
    if 'phase' in kw:
        # Limit phases if one explicitly specified
        phase = kw.pop('phase')
        if phase not in phases:
            dump_skipping_message(f"doesn't support this fork: {phase}")
            return None
        run_phases = [phase]
    else:
        # If pytest `--fork` flag is set, filter out the rest of the forks
        run_phases = set(phases).intersection(DEFAULT_PYTEST_FORKS)

    return run_phases


def _get_available_phases(run_phases, other_phases):
    """
    Return the available fork names for multi-phase tests
    """
    available_phases = set(run_phases)
    if other_phases is not None:
        available_phases |= set(other_phases)
    return available_phases


def _run_test_case_with_phases(fn, phases, other_phases, kw, args, is_fork_transition=False):
    run_phases = _get_run_phases(phases, kw)

    if len(run_phases) == 0:
        if not is_fork_transition:
            dump_skipping_message("none of the recognized phases are executable, skipping test.")
        return None

    available_phases = _get_available_phases(run_phases, other_phases)

    targets = _get_preset_targets(kw)

    # Populate all phases for multi-phase tests
    phase_dir = {}
    for phase in available_phases:
        phase_dir[phase] = targets[phase]

    # Return is ignored whenever multiple phases are ran.
    # This return is for test generators to emit python generators (yielding test vector outputs)
    for phase in run_phases:
        ret = fn(spec=targets[phase], phases=phase_dir, *args, **kw)

    return ret


def with_phases(phases, other_phases=None):
    """
    Decorator factory that returns a decorator that runs a test for the appropriate phases.
    Additional phases that do not initially run, but are made available through the test, are optional.
    """
    def decorator(fn):
        def wrapper(*args, **kw):
            if 'fork_metas' in kw:
                fork_metas = kw.pop('fork_metas')
                if 'phase' in kw:
                    # When running test generator, it sets specific `phase`
                    phase = kw['phase']
                    _phases = [phase]
                    _other_phases = [ALL_FORK_UPGRADES[phase]]
                    ret = _run_test_case_with_phases(fn, _phases, _other_phases, kw, args, is_fork_transition=True)
                else:
                    # When running pytest, go through `fork_metas` instead of using `phases`
                    for fork_meta in fork_metas:
                        _phases = [fork_meta.pre_fork_name]
                        _other_phases = [fork_meta.post_fork_name]
                        ret = _run_test_case_with_phases(fn, _phases, _other_phases, kw, args, is_fork_transition=True)
            else:
                ret = _run_test_case_with_phases(fn, phases, other_phases, kw, args)
            return ret
        return wrapper
    return decorator


def with_presets(preset_bases, reason=None):
    available_presets = set(preset_bases)

    def decorator(fn):
        def wrapper(*args, spec: Spec, **kw):
            if spec.config.PRESET_BASE not in available_presets:
                message = f"doesn't support this preset base: {spec.config.PRESET_BASE}."
                if reason is not None:
                    message = f"{message} Reason: {reason}"
                dump_skipping_message(message)
                return None

            return fn(*args, spec=spec, **kw)
        return wrapper
    return decorator


def _get_basic_dict(ssz_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get dict of Python built-in types from a dict of SSZ objects.
    """
    result = {}
    for k, v in ssz_dict.items():
        if isinstance(v, int):
            value = int(v)
        elif isinstance(v, bytes):
            value = encode_hex(v)
        else:
            value = str(v)
        result[k] = value
    return result


def _get_copy_of_spec(spec):
    fork = spec.fork
    preset = spec.config.PRESET_BASE
    module_path = f"eth2spec.{fork}.{preset}"
    module_spec = importlib.util.find_spec(module_path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def with_config_overrides(config_overrides):
    """
    WARNING: the spec_test decorator must wrap this, to ensure the decorated test actually runs.
    This decorator forces the test to yield, and pytest doesn't run generator tests, and instead silently passes it.
    Use 'spec_configured_state_test' instead of 'spec_state_test' if you are unsure.

    This is a decorator that applies a dict of config value overrides to the spec during execution.
    """
    def decorator(fn):
        def wrapper(*args, spec: Spec, **kw):
            spec = _get_copy_of_spec(spec)

            # apply our overrides to a copy of it, and apply it to the spec
            config = spec.config._asdict()
            config.update(config_overrides)
            config_types = spec.Configuration.__annotations__
            modified_config = {k: config_types[k](v) for k, v in config.items()}

            # To output the changed config to could be serialized with yaml test vectors,
            # the dict SSZ objects have to be converted into Python built-in types.
            output_config = _get_basic_dict(modified_config)
            yield 'config', 'data', output_config

            spec.config = spec.Configuration(**modified_config)

            # Run the function
            out = fn(*args, spec=spec, **kw)
            # If it's not returning None like a normal test function,
            # it's generating things, and we need to complete it before setting back the config.
            if out is not None:
                yield from out
        return wrapper
    return decorator


def is_post_altair(spec):
    return spec.fork not in FORKS_BEFORE_ALTAIR


def is_post_bellatrix(spec):
    return spec.fork not in FORKS_BEFORE_BELLATRIX


with_altair_and_later = with_all_phases_except([PHASE0])
with_bellatrix_and_later = with_all_phases_except([PHASE0, ALTAIR])


def only_generator(reason):
    def _decorator(inner):
        def _wrapper(*args, **kwargs):
            if is_pytest:
                dump_skipping_message(reason)
                return None
            return inner(*args, **kwargs)
        return _wrapper
    return _decorator


#
# Fork transition state tests
#


def set_fork_metas(fork_metas: Sequence[ForkMeta]):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            return fn(*args, fork_metas=fork_metas, **kwargs)
        return wrapper
    return decorator


def with_fork_metas(fork_metas: Sequence[ForkMeta]):
    """
    A decorator to construct a "transition" test from one fork to another.

    Decorator takes a list of `ForkMeta` and each item defines `pre_fork_name`,
    `post_fork_name`, and `fork_epoch`.

    Decorator assumes a transition from the `pre_fork_name` fork to the
    `post_fork_name` fork. The user can supply a `fork_epoch` at which the
    fork occurs or they must compute one (yielding to the generator) during the test
    if more custom behavior is desired.

    A test using this decorator should expect to receive as parameters:
    `state`: the default state constructed for the `pre_fork_name` fork
        according to the `with_state` decorator.
    `fork_epoch`: the `fork_epoch` provided to this decorator, if given.
    `spec`: the version of the eth2 spec corresponding to `pre_fork_name`.
    `post_spec`: the version of the eth2 spec corresponding to `post_fork_name`.
    `pre_tag`: a function to tag data as belonging to `pre_fork_name` fork.
        Used to discriminate data during consumption of the generated spec tests.
    `post_tag`: a function to tag data as belonging to `post_fork_name` fork.
        Used to discriminate data during consumption of the generated spec tests.
    """
    run_yield_fork_meta = yield_fork_meta(fork_metas)
    run_with_phases = with_phases(ALL_PHASES)
    run_set_fork_metas = set_fork_metas(fork_metas)

    def decorator(fn):
        return run_set_fork_metas(run_with_phases(spec_test(with_state(run_yield_fork_meta(fn)))))
    return decorator


def yield_fork_meta(fork_metas: Sequence[ForkMeta]):
    """
    Yield meta fields to `meta.yaml` and pass post spec and meta fields to `fn`.
    """
    def decorator(fn):
        def wrapper(*args, **kw):
            phases = kw.pop('phases')
            spec = kw["spec"]
            try:
                fork_meta = next(filter(lambda m: m.pre_fork_name == spec.fork, fork_metas))
            except StopIteration:
                dump_skipping_message(f"doesn't support this fork: {spec.fork}")

            post_spec = phases[fork_meta.post_fork_name]

            # Reset counter
            pre_fork_counter = 0

            def pre_tag(obj):
                nonlocal pre_fork_counter
                pre_fork_counter += 1
                return obj

            def post_tag(obj):
                return obj

            yield "post_fork", "meta", fork_meta.post_fork_name

            has_fork_epoch = False
            if fork_meta.fork_epoch:
                kw["fork_epoch"] = fork_meta.fork_epoch
                has_fork_epoch = True
                yield "fork_epoch", "meta", fork_meta.fork_epoch

            result = fn(
                *args,
                post_spec=post_spec,
                pre_tag=pre_tag,
                post_tag=post_tag,
                **kw,
            )
            if result is not None:
                for part in result:
                    if part[0] == "fork_epoch":
                        has_fork_epoch = True
                    yield part
            assert has_fork_epoch

            if pre_fork_counter > 0:
                yield "fork_block", "meta", pre_fork_counter - 1

        return wrapper
    return decorator
