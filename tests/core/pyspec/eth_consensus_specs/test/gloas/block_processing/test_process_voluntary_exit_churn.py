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


def assert_exit_churn_behavior(spec, state):
    """
    Shared assertions: exercise compute_exit_epoch_and_update_churn with exit churn limit.
    Verify that exiting exactly the churn limit fits in one epoch, and exiting more spills over.
    """
    exit_churn = spec.get_exit_churn_limit(state)
    current_epoch = spec.get_current_epoch(state)
    earliest_exit_epoch = spec.compute_activation_exit_epoch(current_epoch)

    exit_epoch = spec.compute_exit_epoch_and_update_churn(state, exit_churn)
    assert exit_epoch == earliest_exit_epoch
    assert state.exit_balance_to_consume == 0

    state.earliest_exit_epoch = spec.Epoch(0)
    state.exit_balance_to_consume = spec.Gwei(0)

    exit_epoch = spec.compute_exit_epoch_and_update_churn(state, exit_churn + 1)
    assert exit_epoch == earliest_exit_epoch + 1
    assert state.exit_balance_to_consume == exit_churn - 1


@with_gloas_and_later
@spec_state_test
def test_exit_churn__less_than_activation_cap(spec, state):
    """Default state: exit churn is at the floor, equal to activation churn."""
    exit_churn = spec.get_exit_churn_limit(state)
    activation_churn = spec.get_activation_churn_limit(state)
    assert exit_churn == activation_churn
    assert_exit_churn_behavior(spec, state)
    yield "post", state


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
def test_exit_churn__equal_to_activation_cap(spec, state):
    """Scaled state: exit churn equals the activation cap (activation is capped, exit is not)."""
    exit_churn = spec.get_exit_churn_limit(state)
    activation_churn = spec.get_activation_churn_limit(state)
    assert activation_churn == spec.config.MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT_GLOAS
    assert exit_churn >= activation_churn
    assert_exit_churn_behavior(spec, state)
    yield "post", state


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
def test_exit_churn__greater_than_activation_cap(spec, state):
    """Scaled state: exit churn exceeds the activation cap — exit is uncapped."""
    exit_churn = spec.get_exit_churn_limit(state)
    activation_churn = spec.get_activation_churn_limit(state)
    assert exit_churn > activation_churn
    assert activation_churn == spec.config.MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT_GLOAS
    total = spec.get_total_active_balance(state)
    expected = total // spec.config.CHURN_LIMIT_QUOTIENT_GLOAS
    expected = expected - expected % spec.EFFECTIVE_BALANCE_INCREMENT
    assert exit_churn == expected
    assert_exit_churn_behavior(spec, state)
    yield "post", state
