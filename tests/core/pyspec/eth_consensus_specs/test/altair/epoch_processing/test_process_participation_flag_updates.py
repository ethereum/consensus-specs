from random import Random

from eth_consensus_specs.test.context import (
    single_phase,
    spec_state_test,
    spec_test,
    with_altair_and_later,
    with_custom_state,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import MINIMAL
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_with
from eth_consensus_specs.test.helpers.state import next_epoch_via_block


def get_full_flags(spec):
    full_flags = spec.ParticipationFlags(0)
    for flag_index in range(len(spec.PARTICIPATION_FLAG_WEIGHTS)):
        full_flags = spec.add_flag(full_flags, flag_index)
    return full_flags


def run_process_participation_flag_updates(spec, state):
    old = state.current_epoch_participation.copy()
    yield from run_epoch_processing_with(spec, state, "process_participation_flag_updates")
    assert state.current_epoch_participation == [0] * len(state.validators)
    assert state.previous_epoch_participation == old


@with_altair_and_later
@spec_state_test
def test_all_zeroed(spec, state):
    next_epoch_via_block(spec, state)
    state.current_epoch_participation = [0] * len(state.validators)
    state.previous_epoch_participation = [0] * len(state.validators)
    yield from run_process_participation_flag_updates(spec, state)


@with_altair_and_later
@spec_state_test
def test_filled(spec, state):
    next_epoch_via_block(spec, state)

    state.previous_epoch_participation = [get_full_flags(spec)] * len(state.validators)
    state.current_epoch_participation = [get_full_flags(spec)] * len(state.validators)

    yield from run_process_participation_flag_updates(spec, state)


@with_altair_and_later
@spec_state_test
def test_previous_filled(spec, state):
    next_epoch_via_block(spec, state)

    state.previous_epoch_participation = [get_full_flags(spec)] * len(state.validators)
    state.current_epoch_participation = [0] * len(state.validators)

    yield from run_process_participation_flag_updates(spec, state)


@with_altair_and_later
@spec_state_test
def test_current_filled(spec, state):
    next_epoch_via_block(spec, state)

    state.previous_epoch_participation = [0] * len(state.validators)
    state.current_epoch_participation = [get_full_flags(spec)] * len(state.validators)

    yield from run_process_participation_flag_updates(spec, state)


def random_flags(spec, state, seed: int, previous=True, current=True):
    rng = Random(seed)
    count = len(state.validators)
    max_flag_value_excl = 2 ** len(spec.PARTICIPATION_FLAG_WEIGHTS)
    if previous:
        state.previous_epoch_participation = [
            rng.randrange(0, max_flag_value_excl) for _ in range(count)
        ]
    if current:
        state.current_epoch_participation = [
            rng.randrange(0, max_flag_value_excl) for _ in range(count)
        ]


@with_altair_and_later
@spec_state_test
def test_random_0(spec, state):
    next_epoch_via_block(spec, state)
    random_flags(spec, state, 100)
    yield from run_process_participation_flag_updates(spec, state)


@with_altair_and_later
@spec_state_test
def test_random_1(spec, state):
    next_epoch_via_block(spec, state)
    random_flags(spec, state, 101)
    yield from run_process_participation_flag_updates(spec, state)


@with_altair_and_later
@spec_state_test
def test_random_2(spec, state):
    next_epoch_via_block(spec, state)
    random_flags(spec, state, 102)
    yield from run_process_participation_flag_updates(spec, state)


@with_altair_and_later
@spec_state_test
def test_random_genesis(spec, state):
    random_flags(spec, state, 11)
    yield from run_process_participation_flag_updates(spec, state)


@with_altair_and_later
@spec_state_test
def test_current_epoch_zeroed(spec, state):
    next_epoch_via_block(spec, state)
    random_flags(spec, state, 12, current=False)
    state.current_epoch_participation = [0] * len(state.validators)
    yield from run_process_participation_flag_updates(spec, state)


@with_altair_and_later
@spec_state_test
def test_previous_epoch_zeroed(spec, state):
    next_epoch_via_block(spec, state)
    random_flags(spec, state, 13, previous=False)
    state.previous_epoch_participation = [0] * len(state.validators)
    yield from run_process_participation_flag_updates(spec, state)


def custom_validator_count(factor: float):
    def initializer(spec):
        num_validators = (
            spec.SLOTS_PER_EPOCH * spec.MAX_COMMITTEES_PER_SLOT * spec.TARGET_COMMITTEE_SIZE
        )
        return [spec.MAX_EFFECTIVE_BALANCE] * int(float(int(num_validators)) * factor)

    return initializer


@with_altair_and_later
@with_presets(
    [MINIMAL], reason="mainnet config requires too many pre-generated public/private keys"
)
@spec_test
@with_custom_state(
    balances_fn=custom_validator_count(1.3), threshold_fn=lambda spec: spec.config.EJECTION_BALANCE
)
@single_phase
def test_slightly_larger_random(spec, state):
    next_epoch_via_block(spec, state)
    random_flags(spec, state, 14)
    yield from run_process_participation_flag_updates(spec, state)


@with_altair_and_later
@with_presets(
    [MINIMAL], reason="mainnet config requires too many pre-generated public/private keys"
)
@spec_test
@with_custom_state(
    balances_fn=custom_validator_count(2.6), threshold_fn=lambda spec: spec.config.EJECTION_BALANCE
)
@single_phase
def test_large_random(spec, state):
    next_epoch_via_block(spec, state)
    random_flags(spec, state, 15)
    yield from run_process_participation_flag_updates(spec, state)
