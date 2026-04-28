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
from eth_consensus_specs.test.helpers.keys import pubkey_to_privkey
from eth_consensus_specs.test.helpers.voluntary_exits import (
    run_voluntary_exit_processing,
    sign_voluntary_exit,
)


def run_exit_at_churn_boundary(spec, state):
    """
    Exit one validator and verify its scheduled exit epoch and the resulting
    ``exit_balance_to_consume`` reflect the exit churn limit. Spans multiple
    epochs when the validator's effective balance exceeds the per-epoch churn.
    """
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    exit_churn = spec.get_exit_churn_limit(state)

    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    to_exit = state.validators[validator_index].effective_balance

    earliest_exit_epoch = spec.compute_activation_exit_epoch(current_epoch)
    additional_epochs = (to_exit - 1) // exit_churn
    expected_exit_epoch = earliest_exit_epoch + additional_epochs
    expected_withdrawable_epoch = (
        expected_exit_epoch + spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    )

    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]
    signed_voluntary_exit = sign_voluntary_exit(
        spec,
        state,
        spec.VoluntaryExit(epoch=current_epoch, validator_index=validator_index),
        privkey,
    )

    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit)

    assert state.validators[validator_index].exit_epoch == expected_exit_epoch
    assert state.validators[validator_index].withdrawable_epoch == expected_withdrawable_epoch
    assert state.exit_balance_to_consume == (additional_epochs + 1) * exit_churn - to_exit
    assert state.earliest_exit_epoch == expected_exit_epoch


@with_gloas_and_later
@spec_state_test
def test_exit_churn__less_than_activation_cap(spec, state):
    """Default state: exit churn is at the floor, equal to activation churn."""
    exit_churn = spec.get_exit_churn_limit(state)
    activation_churn = spec.get_activation_churn_limit(state)
    assert exit_churn == activation_churn
    yield from run_exit_at_churn_boundary(spec, state)


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
    yield from run_exit_at_churn_boundary(spec, state)


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
    yield from run_exit_at_churn_boundary(spec, state)
