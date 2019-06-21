from eth2spec.test.context import spec_state_test, with_phases
from eth2spec.test.helpers.deposits import (
    prepare_genesis_deposits,
)


@with_phases(['phase0'])
@spec_state_test
def test_is_genesis_trigger_false(spec, state):
    deposit_count = 2
    genesis_deposits, deposit_root = prepare_genesis_deposits(spec, deposit_count)
    genesis_time = 1234

    is_triggered = spec.is_genesis_trigger(genesis_deposits, genesis_time, deposit_root)
    assert is_triggered is False

    yield is_triggered


@with_phases(['phase0'])
@spec_state_test
def test_is_genesis_trigger_true(spec, state):
    deposit_count = spec.GENESIS_ACTIVE_VALIDATOR_COUNT
    genesis_deposits, deposit_root = prepare_genesis_deposits(spec, deposit_count)
    genesis_time = 1234

    is_triggered = spec.is_genesis_trigger(genesis_deposits, genesis_time, deposit_root)
    assert is_triggered is True

    yield is_triggered


@with_phases(['phase0'])
@spec_state_test
def test_genesis(spec, state):
    deposit_count = spec.GENESIS_ACTIVE_VALIDATOR_COUNT
    genesis_deposits, deposit_root = prepare_genesis_deposits(spec, deposit_count)
    genesis_time = 1234

    yield genesis_deposits
    yield genesis_time

    genesis_eth1_data = spec.Eth1Data(
        deposit_root=deposit_root,
        deposit_count=deposit_count,
        block_hash=b'\x12' * 32,
    )

    yield genesis_eth1_data
    genesis_state = spec.get_genesis_beacon_state(
        genesis_deposits,
        genesis_time,
        genesis_eth1_data,
    )
    yield genesis_state
