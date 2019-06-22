from eth2spec.test.context import with_phases, spectest_with_bls_switch
from eth2spec.test.helpers.deposits import (
    prepare_genesis_deposits,
)


@with_phases(['phase0'])
@spectest_with_bls_switch
def test_is_genesis_trigger_false(spec):
    deposit_count = 2
    genesis_deposits, deposit_root = prepare_genesis_deposits(spec, deposit_count, spec.MAX_EFFECTIVE_BALANCE)
    genesis_time = 1546300800

    yield genesis_deposits
    yield genesis_time
    yield deposit_root

    is_triggered = spec.is_genesis_trigger(genesis_deposits, genesis_time, deposit_root)
    assert is_triggered is False

    yield is_triggered


@with_phases(['phase0'])
@spectest_with_bls_switch
def test_is_genesis_trigger_true(spec):
    deposit_count = spec.GENESIS_ACTIVE_VALIDATOR_COUNT
    genesis_deposits, deposit_root = prepare_genesis_deposits(spec, deposit_count, spec.MAX_EFFECTIVE_BALANCE)
    genesis_time = 1546300800

    yield genesis_deposits
    yield genesis_time
    yield deposit_root

    is_triggered = spec.is_genesis_trigger(genesis_deposits, genesis_time, deposit_root)
    assert is_triggered is True

    yield is_triggered


@with_phases(['phase0'])
@spectest_with_bls_switch
def test_is_genesis_trigger_not_enough_balance(spec):
    deposit_count = spec.GENESIS_ACTIVE_VALIDATOR_COUNT
    genesis_deposits, deposit_root = prepare_genesis_deposits(spec, deposit_count, spec.MAX_EFFECTIVE_BALANCE - 1)
    genesis_time = 1546300800
    yield genesis_deposits
    yield genesis_time
    yield deposit_root

    is_triggered = spec.is_genesis_trigger(genesis_deposits, genesis_time, deposit_root)
    assert is_triggered is False

    yield is_triggered


@with_phases(['phase0'])
@spectest_with_bls_switch
def test_genesis(spec):
    deposit_count = spec.GENESIS_ACTIVE_VALIDATOR_COUNT
    genesis_deposits, deposit_root = prepare_genesis_deposits(spec, deposit_count, spec.MAX_EFFECTIVE_BALANCE)
    genesis_time = 1546300800
    block_hash = b'\x12' * 32

    yield genesis_deposits
    yield genesis_time

    genesis_eth1_data = spec.Eth1Data(
        deposit_root=deposit_root,
        deposit_count=deposit_count,
        block_hash=block_hash,
    )

    yield genesis_eth1_data
    genesis_state = spec.get_genesis_beacon_state(
        genesis_deposits,
        genesis_time,
        genesis_eth1_data,
    )

    assert genesis_state.genesis_time == genesis_time
    assert len(genesis_state.validators) == deposit_count
    assert genesis_state.eth1_data.deposit_root == deposit_root
    assert genesis_state.eth1_data.deposit_count == deposit_count
    assert genesis_state.eth1_data.block_hash == block_hash

    yield genesis_state
