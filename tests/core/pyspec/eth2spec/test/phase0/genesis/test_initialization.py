from eth2spec.test.context import PHASE0, spec_test, with_phases, single_phase
from eth2spec.test.helpers.deposits import (
    prepare_genesis_deposits,
)


@with_phases(([PHASE0]))
@spec_test
@single_phase
def test_initialize_beacon_state_from_eth1(spec):
    deposit_count = spec.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT
    deposits, deposit_root, _ = prepare_genesis_deposits(spec, deposit_count, spec.MAX_EFFECTIVE_BALANCE, signed=True)

    eth1_block_hash = b'\x12' * 32
    eth1_timestamp = spec.MIN_GENESIS_TIME

    yield 'eth1_block_hash', eth1_block_hash
    yield 'eth1_timestamp', eth1_timestamp
    yield 'deposits', deposits

    # initialize beacon_state
    state = spec.initialize_beacon_state_from_eth1(eth1_block_hash, eth1_timestamp, deposits)

    assert state.genesis_time == eth1_timestamp + spec.GENESIS_DELAY
    assert len(state.validators) == deposit_count
    assert state.eth1_data.deposit_root == deposit_root
    assert state.eth1_data.deposit_count == deposit_count
    assert state.eth1_data.block_hash == eth1_block_hash
    assert spec.get_total_active_balance(state) == deposit_count * spec.MAX_EFFECTIVE_BALANCE

    # yield state
    yield 'state', state


@with_phases([PHASE0])
@spec_test
@single_phase
def test_initialize_beacon_state_some_small_balances(spec):
    main_deposit_count = spec.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT
    main_deposits, _, deposit_data_list = prepare_genesis_deposits(spec, main_deposit_count,
                                                                   spec.MAX_EFFECTIVE_BALANCE, signed=True)
    # For deposits above, and for another deposit_count, add a balance of EFFECTIVE_BALANCE_INCREMENT
    small_deposit_count = main_deposit_count * 2
    small_deposits, deposit_root, _ = prepare_genesis_deposits(spec, small_deposit_count,
                                                               spec.MIN_DEPOSIT_AMOUNT,
                                                               signed=True,
                                                               deposit_data_list=deposit_data_list)
    deposits = main_deposits + small_deposits

    eth1_block_hash = b'\x12' * 32
    eth1_timestamp = spec.MIN_GENESIS_TIME

    yield 'eth1_block_hash', eth1_block_hash
    yield 'eth1_timestamp', eth1_timestamp
    yield 'deposits', deposits

    # initialize beacon_state
    state = spec.initialize_beacon_state_from_eth1(eth1_block_hash, eth1_timestamp, deposits)

    assert state.genesis_time == eth1_timestamp + spec.GENESIS_DELAY
    assert len(state.validators) == small_deposit_count
    assert state.eth1_data.deposit_root == deposit_root
    assert state.eth1_data.deposit_count == len(deposits)
    assert state.eth1_data.block_hash == eth1_block_hash
    # only main deposits participate to the active balance
    assert spec.get_total_active_balance(state) == main_deposit_count * spec.MAX_EFFECTIVE_BALANCE

    # yield state
    yield 'state', state
