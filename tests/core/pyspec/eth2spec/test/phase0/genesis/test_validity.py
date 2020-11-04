from eth2spec.test.context import PHASE0, spec_test, with_phases, single_phase
from eth2spec.test.helpers.deposits import (
    prepare_full_genesis_deposits,
)


def create_valid_beacon_state(spec):
    deposit_count = spec.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT
    deposits, _, _ = prepare_full_genesis_deposits(
        spec,
        amount=spec.MAX_EFFECTIVE_BALANCE,
        deposit_count=deposit_count,
        signed=True,
    )

    eth1_block_hash = b'\x12' * 32
    eth1_timestamp = spec.MIN_GENESIS_TIME
    return spec.initialize_beacon_state_from_eth1(eth1_block_hash, eth1_timestamp, deposits)


def run_is_valid_genesis_state(spec, state, valid=True):
    """
    Run ``is_valid_genesis_state``, yielding:
      - genesis ('state')
      - is_valid ('is_valid')
    """
    yield 'genesis', state
    is_valid = spec.is_valid_genesis_state(state)
    yield 'is_valid', is_valid
    assert is_valid == valid


@with_phases([PHASE0])
@spec_test
@single_phase
def test_is_valid_genesis_state_true(spec):
    state = create_valid_beacon_state(spec)

    yield from run_is_valid_genesis_state(spec, state, valid=True)


@with_phases([PHASE0])
@spec_test
@single_phase
def test_is_valid_genesis_state_false_invalid_timestamp(spec):
    state = create_valid_beacon_state(spec)
    state.genesis_time = spec.MIN_GENESIS_TIME - 1

    yield from run_is_valid_genesis_state(spec, state, valid=False)


@with_phases([PHASE0])
@spec_test
@single_phase
def test_is_valid_genesis_state_true_more_balance(spec):
    state = create_valid_beacon_state(spec)
    state.validators[0].effective_balance = spec.MAX_EFFECTIVE_BALANCE + 1

    yield from run_is_valid_genesis_state(spec, state, valid=True)


@with_phases([PHASE0])
@spec_test
@single_phase
def test_is_valid_genesis_state_true_one_more_validator(spec):
    deposit_count = spec.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT + 1
    deposits, _, _ = prepare_full_genesis_deposits(
        spec,
        amount=spec.MAX_EFFECTIVE_BALANCE,
        deposit_count=deposit_count,
        signed=True,
    )

    eth1_block_hash = b'\x12' * 32
    eth1_timestamp = spec.MIN_GENESIS_TIME
    state = spec.initialize_beacon_state_from_eth1(eth1_block_hash, eth1_timestamp, deposits)

    yield from run_is_valid_genesis_state(spec, state, valid=True)


@with_phases([PHASE0])
@spec_test
@single_phase
def test_is_valid_genesis_state_false_not_enough_validator(spec):
    deposit_count = spec.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT - 1
    deposits, _, _ = prepare_full_genesis_deposits(
        spec,
        amount=spec.MAX_EFFECTIVE_BALANCE,
        deposit_count=deposit_count,
        signed=True,
    )

    eth1_block_hash = b'\x12' * 32
    eth1_timestamp = spec.MIN_GENESIS_TIME
    state = spec.initialize_beacon_state_from_eth1(eth1_block_hash, eth1_timestamp, deposits)

    yield from run_is_valid_genesis_state(spec, state, valid=False)
