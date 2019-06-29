from eth2spec.test.context import spectest_with_bls_switch, with_phases
from eth2spec.test.helpers.deposits import (
    prepare_genesis_deposits,
)


def create_valid_beacon_state(spec):
    deposit_count = spec.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT
    deposits, _ = prepare_genesis_deposits(spec, deposit_count, spec.MAX_EFFECTIVE_BALANCE)

    eth1_block_hash = b'\x12' * 32
    eth1_timestamp = spec.MIN_GENESIS_TIME
    return spec.initialize_beacon_state_from_eth1(eth1_block_hash, eth1_timestamp, deposits)


@with_phases(['phase0'])
@spectest_with_bls_switch
def test_initialize_beacon_state_from_eth1(spec):
    deposit_count = spec.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT
    deposits, deposit_root = prepare_genesis_deposits(spec, deposit_count, spec.MAX_EFFECTIVE_BALANCE)

    eth1_block_hash = b'\x12' * 32
    eth1_timestamp = spec.MIN_GENESIS_TIME

    yield 'eth1_block_hash', eth1_block_hash
    yield 'eth1_timestamp', eth1_timestamp
    yield 'deposits', deposits

    # initialize beacon_state
    state = spec.initialize_beacon_state_from_eth1(eth1_block_hash, eth1_timestamp, deposits)

    assert state.genesis_time == eth1_timestamp - eth1_timestamp % spec.SECONDS_PER_DAY + 2 * spec.SECONDS_PER_DAY
    assert len(state.validators) == deposit_count
    assert state.eth1_data.deposit_root == deposit_root
    assert state.eth1_data.deposit_count == deposit_count
    assert state.eth1_data.block_hash == eth1_block_hash

    # yield state
    yield 'state', state
