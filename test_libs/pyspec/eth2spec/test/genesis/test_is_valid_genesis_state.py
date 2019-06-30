from eth2spec.test.context import spectest_with_bls_switch, with_phases
from eth2spec.test.helpers.deposits import (
    prepare_genesis_deposits,
)


def create_valid_beacon_state(spec):
    deposit_count = spec.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT
    deposits, _ = prepare_genesis_deposits(spec, deposit_count, spec.MAX_EFFECTIVE_BALANCE, signed=True)

    eth1_block_hash = b'\x12' * 32
    eth1_timestamp = spec.MIN_GENESIS_TIME
    return spec.initialize_beacon_state_from_eth1(eth1_block_hash, eth1_timestamp, deposits)


def run_is_valid_genesis_state(spec, state, valid=True):
    """
    Run ``is_valid_genesis_state``, yielding:
      - state ('state')
      - is_valid ('is_valid')
    If ``valid == False``, run expecting ``AssertionError``
    """
    yield state
    is_valid = spec.is_valid_genesis_state(state)
    yield 'is_valid', is_valid


@with_phases(['phase0'])
@spectest_with_bls_switch
def test_is_valid_genesis_state_true(spec):
    state = create_valid_beacon_state(spec)

    yield from run_is_valid_genesis_state(spec, state, valid=True)


@with_phases(['phase0'])
@spectest_with_bls_switch
def test_is_valid_genesis_state_false_invalid_timestamp(spec):
    state = create_valid_beacon_state(spec)
    state.genesis_time = spec.MIN_GENESIS_TIME - 1

    yield from run_is_valid_genesis_state(spec, state, valid=True)


@with_phases(['phase0'])
@spectest_with_bls_switch
def test_is_valid_genesis_state_true_more_balance(spec):
    state = create_valid_beacon_state(spec)
    state.validators[0].effective_balance = spec.MAX_EFFECTIVE_BALANCE + 1

    yield from run_is_valid_genesis_state(spec, state, valid=True)


@with_phases(['phase0'])
@spectest_with_bls_switch
def test_is_valid_genesis_state_false_not_enough_balance(spec):
    state = create_valid_beacon_state(spec)
    state.validators[0].effective_balance = spec.MAX_EFFECTIVE_BALANCE - 1

    yield from run_is_valid_genesis_state(spec, state, valid=False)


@with_phases(['phase0'])
@spectest_with_bls_switch
def test_is_valid_genesis_state_true_one_more_validator(spec):
    deposit_count = spec.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT + 1
    deposits, _ = prepare_genesis_deposits(spec, deposit_count, spec.MAX_EFFECTIVE_BALANCE, signed=True)

    eth1_block_hash = b'\x12' * 32
    eth1_timestamp = spec.MIN_GENESIS_TIME
    state = spec.initialize_beacon_state_from_eth1(eth1_block_hash, eth1_timestamp, deposits)

    yield from run_is_valid_genesis_state(spec, state, valid=True)


@with_phases(['phase0'])
@spectest_with_bls_switch
def test_is_valid_genesis_state_false_not_enough_validator(spec):
    deposit_count = spec.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT - 1
    deposits, _ = prepare_genesis_deposits(spec, deposit_count, spec.MAX_EFFECTIVE_BALANCE, signed=True)

    eth1_block_hash = b'\x12' * 32
    eth1_timestamp = spec.MIN_GENESIS_TIME
    state = spec.initialize_beacon_state_from_eth1(eth1_block_hash, eth1_timestamp, deposits)

    yield from run_is_valid_genesis_state(spec, state, valid=False)
