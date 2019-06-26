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

    yield "deposits", genesis_deposits
    yield "time", genesis_time
    yield "deposit_root", deposit_root

    is_triggered = spec.is_genesis_trigger(genesis_deposits, genesis_time)
    assert is_triggered is False

    yield "is_triggered", is_triggered


@with_phases(['phase0'])
@spectest_with_bls_switch
def test_is_genesis_trigger_true(spec):
    deposit_count = spec.GENESIS_ACTIVE_VALIDATOR_COUNT
    genesis_deposits, deposit_root = prepare_genesis_deposits(spec, deposit_count, spec.MAX_EFFECTIVE_BALANCE)
    genesis_time = 1546300800

    yield "deposits", genesis_deposits
    yield "time", genesis_time
    yield "deposit_root", deposit_root

    is_triggered = spec.is_genesis_trigger(genesis_deposits, genesis_time)
    assert is_triggered is True

    yield "is_triggered", is_triggered


@with_phases(['phase0'])
@spectest_with_bls_switch
def test_is_genesis_trigger_not_enough_balance(spec):
    deposit_count = spec.GENESIS_ACTIVE_VALIDATOR_COUNT
    genesis_deposits, deposit_root = prepare_genesis_deposits(spec, deposit_count, spec.MAX_EFFECTIVE_BALANCE - 1)
    genesis_time = 1546300800
    yield "deposits", genesis_deposits
    yield "time", genesis_time
    yield "deposit_root", deposit_root

    is_triggered = spec.is_genesis_trigger(genesis_deposits, genesis_time)
    assert is_triggered is False

    yield "is_triggered", is_triggered
