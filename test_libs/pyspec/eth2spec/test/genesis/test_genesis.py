from eth2spec.test.context import with_phases, spectest_with_bls_switch
from eth2spec.test.helpers.deposits import (
    prepare_genesis_deposits,
)


@with_phases(['phase0'])
@spectest_with_bls_switch
def test_genesis(spec):
    deposit_count = spec.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT
    genesis_deposits, deposit_root = prepare_genesis_deposits(spec, deposit_count, spec.MAX_EFFECTIVE_BALANCE)
    genesis_time = 1546300800
    genesis_eth1_block_hash = b'\x12' * 32

    yield "deposits", genesis_deposits
    yield "genesis_time", genesis_time

    yield "genesis_eth1_block_hash", genesis_eth1_block_hash
    genesis_state = spec.get_genesis_beacon_state(
        genesis_deposits,
        genesis_time,
        genesis_eth1_block_hash,
    )

    assert genesis_state.genesis_time == genesis_time
    assert len(genesis_state.validators) == deposit_count
    assert genesis_state.eth1_data.deposit_root == deposit_root
    assert genesis_state.eth1_data.deposit_count == deposit_count
    assert genesis_state.eth1_data.block_hash == genesis_eth1_block_hash

    yield "state", genesis_state
