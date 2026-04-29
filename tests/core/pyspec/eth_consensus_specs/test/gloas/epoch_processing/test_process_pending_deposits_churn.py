from eth_consensus_specs.test.context import (
    default_activation_threshold,
    scaled_churn_balances_equal_activation_churn_limit,
    scaled_churn_balances_exceed_activation_churn_limit,
    single_phase,
    spec_state_test,
    spec_test,
    with_custom_state,
    with_gloas_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import MINIMAL
from eth_consensus_specs.test.helpers.deposits import prepare_pending_deposit
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_with


def run_process_pending_deposits(spec, state):
    yield from run_epoch_processing_with(spec, state, "process_pending_deposits")


def run_test_pending_deposits_activation_churn(spec, state):
    """
    Shared test: create a deposit equal to activation churn, run process_pending_deposits,
    and verify it is fully consumed. Then create a deposit above churn and verify it is NOT processed.
    """
    index = 0
    activation_churn = spec.get_activation_churn_limit(state)
    exit_churn = spec.get_exit_churn_limit(state)

    assert activation_churn <= exit_churn

    amount = activation_churn
    state.pending_deposits.append(prepare_pending_deposit(spec, index, amount))
    pre_balance = state.balances[index]

    yield from run_process_pending_deposits(spec, state)

    assert state.balances[index] == pre_balance + amount
    assert state.deposit_balance_to_consume == 0
    assert state.pending_deposits == []


@with_gloas_and_later
@spec_state_test
def test_activation_churn__less_than_cap(spec, state):
    """Default state: activation churn is below the cap (at the floor)."""
    activation_churn = spec.get_activation_churn_limit(state)
    assert activation_churn <= spec.config.MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT_GLOAS
    yield from run_test_pending_deposits_activation_churn(spec, state)


@with_gloas_and_later
@with_presets(
    [MINIMAL],
    reason="mainnet config leads to larger validator set than limit of public/private keys pre-generated",
)
@spec_test
@with_custom_state(
    balances_fn=scaled_churn_balances_equal_activation_churn_limit,
    threshold_fn=default_activation_threshold,
)
@single_phase
def test_activation_churn__equal_to_cap(spec, state):
    """Scaled state: activation churn exactly equals the cap."""
    activation_churn = spec.get_activation_churn_limit(state)
    assert activation_churn == spec.config.MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT_GLOAS
    yield from run_test_pending_deposits_activation_churn(spec, state)


@with_gloas_and_later
@with_presets(
    [MINIMAL],
    reason="mainnet config leads to larger validator set than limit of public/private keys pre-generated",
)
@spec_test
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_churn_limit,
    threshold_fn=default_activation_threshold,
)
@single_phase
def test_activation_churn__greater_than_cap(spec, state):
    """Scaled state: uncapped churn exceeds cap, but activation churn is capped."""
    activation_churn = spec.get_activation_churn_limit(state)
    exit_churn = spec.get_exit_churn_limit(state)
    assert activation_churn == spec.config.MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT_GLOAS
    assert exit_churn > activation_churn
    yield from run_test_pending_deposits_activation_churn(spec, state)


@with_gloas_and_later
@with_presets(
    [MINIMAL],
    reason="mainnet config leads to larger validator set than limit of public/private keys pre-generated",
)
@spec_test
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_churn_limit,
    threshold_fn=default_activation_threshold,
)
@single_phase
def test_deposit_above_activation_churn_not_processed(spec, state):
    """A deposit larger than the activation churn limit should NOT be processed."""
    index = 0
    activation_churn = spec.get_activation_churn_limit(state)
    amount = activation_churn + 1
    state.pending_deposits.append(prepare_pending_deposit(spec, index, amount))
    pre_balance = state.balances[index]

    yield from run_process_pending_deposits(spec, state)

    assert state.balances[index] == pre_balance
    assert state.deposit_balance_to_consume == activation_churn
    assert state.pending_deposits == [prepare_pending_deposit(spec, index, amount)]
