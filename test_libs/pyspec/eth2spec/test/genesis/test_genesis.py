from eth2spec.test.context import with_phases, spectest_with_bls_switch
from eth2spec.test.helpers.deposits import (
    prepare_genesis_deposits,
)


@with_phases(['phase0'])
@spectest_with_bls_switch
def test_get_genesis_beacon_state_success(spec):
    deposit_count = spec.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT
    deposits, deposit_root = prepare_genesis_deposits(spec, deposit_count, spec.MAX_EFFECTIVE_BALANCE)

    eth1_block_hash = b'\x12' * 32
    eth1_timestamp = spec.MIN_GENESIS_TIME

    yield "eth1_block_hash", eth1_block_hash
    yield "eth1_timestamp", eth1_timestamp
    yield "deposits", deposits
    genesis_state = spec.get_genesis_beacon_state(
        eth1_block_hash,
        eth1_timestamp,
        deposits,
    )

    assert genesis_state.genesis_time == eth1_timestamp - eth1_timestamp % spec.SECONDS_PER_DAY + 2 * spec.SECONDS_PER_DAY
    assert len(genesis_state.validators) == deposit_count
    assert genesis_state.eth1_data.deposit_root == deposit_root
    assert genesis_state.eth1_data.deposit_count == deposit_count
    assert genesis_state.eth1_data.block_hash == eth1_block_hash

    yield "state", genesis_state
