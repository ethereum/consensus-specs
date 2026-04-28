from eth_consensus_specs.test.context import (
    default_activation_threshold,
    scaled_churn_balances_exceed_activation_exit_churn_limit,
    single_phase,
    spec_state_test,
    spec_test,
    with_custom_state,
    with_gloas_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import MINIMAL


@with_gloas_and_later
@spec_state_test
def test_get_consolidation_churn_limit_independent(spec, state):
    """Consolidation churn uses its own quotient, independent of exit/activation."""
    churn = spec.get_consolidation_churn_limit(state)
    total = spec.get_total_active_balance(state)
    expected = total // spec.config.CONSOLIDATION_CHURN_LIMIT_QUOTIENT
    expected = expected - expected % spec.EFFECTIVE_BALANCE_INCREMENT
    assert churn == expected


@with_gloas_and_later
@spec_state_test
def test_get_consolidation_churn_limit_rounded(spec, state):
    """Consolidation churn must be a multiple of EFFECTIVE_BALANCE_INCREMENT."""
    assert spec.get_consolidation_churn_limit(state) % spec.EFFECTIVE_BALANCE_INCREMENT == 0


@with_gloas_and_later
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_get_consolidation_churn_limit_slower_than_exit(spec, state):
    """Consolidation quotient is 2x exit quotient, so consolidation churn <= exit churn."""
    assert spec.get_consolidation_churn_limit(state) <= spec.get_exit_churn_limit(state)


@with_gloas_and_later
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_exit_churn_approximately_double_consolidation(spec, state):
    """Since CONSOLIDATION_CHURN_LIMIT_QUOTIENT == 2 * CHURN_LIMIT_QUOTIENT_GLOAS,
    exit churn should be approximately 2x consolidation churn (before rounding)."""
    exit_churn = spec.get_exit_churn_limit(state)
    consolidation_churn = spec.get_consolidation_churn_limit(state)
    assert abs(exit_churn - 2 * consolidation_churn) <= 2 * spec.EFFECTIVE_BALANCE_INCREMENT


@with_gloas_and_later
@spec_state_test
def test_compute_weak_subjectivity_period_weighted_delta(spec, state):
    """WSP uses the EIP-8061 weighted formula: delta = 2*E//3 + A//3 + C."""
    t = spec.get_total_active_balance(state)
    exit_churn = spec.get_exit_churn_limit(state)
    activation_churn = spec.get_activation_churn_limit(state)
    consolidation_churn = spec.get_consolidation_churn_limit(state)

    expected_delta = 2 * exit_churn // 3 + activation_churn // 3 + consolidation_churn
    expected_epochs = spec.SAFETY_DECAY * t // (2 * expected_delta * 100)
    expected_wsp = spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY + expected_epochs

    actual_wsp = spec.compute_weak_subjectivity_period(state)
    assert actual_wsp == expected_wsp


@with_gloas_and_later
@with_presets(
    [MINIMAL],
    reason="mainnet config leads to larger validator set than limit of public/private keys pre-generated",
)
@spec_test
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@single_phase
def test_compute_weak_subjectivity_period_scaled(spec, state):
    """WSP with scaled validators — exit churn exceeds activation cap, affecting delta."""
    exit_churn = spec.get_exit_churn_limit(state)
    activation_churn = spec.get_activation_churn_limit(state)
    assert exit_churn > activation_churn

    t = spec.get_total_active_balance(state)
    consolidation_churn = spec.get_consolidation_churn_limit(state)
    expected_delta = 2 * exit_churn // 3 + activation_churn // 3 + consolidation_churn
    expected_epochs = spec.SAFETY_DECAY * t // (2 * expected_delta * 100)
    expected_wsp = spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY + expected_epochs

    actual_wsp = spec.compute_weak_subjectivity_period(state)
    assert actual_wsp == expected_wsp


@with_gloas_and_later
@with_presets(
    [MINIMAL],
    reason="mainnet config leads to larger validator set than limit of public/private keys pre-generated",
)
@spec_test
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@single_phase
def test_compute_consolidation_epoch_uses_new_quotient(spec, state):
    """compute_consolidation_epoch_and_update_churn should pick up the redefined
    get_consolidation_churn_limit with CONSOLIDATION_CHURN_LIMIT_QUOTIENT."""
    consolidation_churn = spec.get_consolidation_churn_limit(state)
    current_epoch = spec.get_current_epoch(state)
    earliest_consolidation_epoch = spec.compute_activation_exit_epoch(current_epoch)

    epoch = spec.compute_consolidation_epoch_and_update_churn(state, consolidation_churn)
    assert epoch == earliest_consolidation_epoch
    assert state.consolidation_balance_to_consume == 0

    state.earliest_consolidation_epoch = spec.Epoch(0)
    state.consolidation_balance_to_consume = spec.Gwei(0)

    epoch = spec.compute_consolidation_epoch_and_update_churn(state, consolidation_churn + 1)
    assert epoch == earliest_consolidation_epoch + 1
    assert state.consolidation_balance_to_consume == consolidation_churn - 1
