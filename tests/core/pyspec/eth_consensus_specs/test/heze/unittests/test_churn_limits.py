from eth_consensus_specs.test.context import (
    default_activation_threshold,
    default_balances,
    scaled_churn_balances_equal_activation_churn_limit,
    scaled_churn_balances_exceed_activation_churn_limit,
    single_phase,
    spec_test,
    with_config_overrides,
    with_phases,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import HEZE, MINIMAL
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.heze.slot_duration import (
    fork_epoch_cases,
    heze_spec_with_slot_duration,
    SLOT_DURATIONS_MS,
)


def scale_churn(spec, churn, slot_duration_ms):
    churn = churn * slot_duration_ms // int(spec.config.SLOT_DURATION_MS)
    return churn - churn % spec.EFFECTIVE_BALANCE_INCREMENT


def _balances_below_activation_churn_limit(spec):
    minimum = spec.config.MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA
    maximum = spec.config.MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT_GLOAS
    return [(minimum + maximum) // 2] * spec.config.CHURN_LIMIT_QUOTIENT_GLOAS


def _balances_at_exit_churn_minimum(spec):
    total = spec.config.MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA * spec.config.CHURN_LIMIT_QUOTIENT_GLOAS
    balance = min(spec.MAX_EFFECTIVE_BALANCE_ELECTRA, total // int(spec.SLOTS_PER_EPOCH))
    return [balance] * (total // balance)


def _run_churn_limits_with_balances(spec, balances):
    state = create_genesis_state(spec, balances, default_activation_threshold(spec))
    total = spec.get_total_active_balance(state)
    exit_churn_limit_unscaled = max(
        spec.config.MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA,
        total // spec.config.CHURN_LIMIT_QUOTIENT_GLOAS,
    )
    activation_churn_limit_unscaled = min(
        spec.config.MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT_GLOAS, exit_churn_limit_unscaled
    )
    consolidation_churn_limit_unscaled = total // spec.config.CONSOLIDATION_CHURN_LIMIT_QUOTIENT

    for slot_duration_ms in SLOT_DURATIONS_MS:
        for fork_epoch, epoch, duration_ms in fork_epoch_cases(spec, slot_duration_ms):
            state.slot = spec.compute_start_slot_at_epoch(epoch)
            heze_spec = heze_spec_with_slot_duration(spec, slot_duration_ms, fork_epoch)

            exit_churn_limit = scale_churn(spec, exit_churn_limit_unscaled, duration_ms)
            activation_churn_limit = scale_churn(spec, activation_churn_limit_unscaled, duration_ms)
            consolidation_churn_limit = scale_churn(
                spec, consolidation_churn_limit_unscaled, duration_ms
            )
            assert heze_spec.get_exit_churn_limit(state) == exit_churn_limit
            assert heze_spec.get_activation_churn_limit(state) == activation_churn_limit
            assert heze_spec.get_consolidation_churn_limit(state) == consolidation_churn_limit


@with_phases([HEZE])
@spec_test
@with_config_overrides({"HEZE_FORK_EPOCH": 2})
@single_phase
def test_churn_limits_up_to_minimum(spec):
    for balances in (
        default_balances(spec, spec.SLOTS_PER_EPOCH),
        _balances_at_exit_churn_minimum(spec),
    ):
        _run_churn_limits_with_balances(spec, balances)


@with_phases([HEZE])
@with_presets(
    [MINIMAL],
    reason="mainnet config leads to larger validator set than limit of public/private keys pre-generated",
)
@spec_test
@with_config_overrides({"HEZE_FORK_EPOCH": 2})
@single_phase
def test_churn_limits_up_to_maximum(spec):
    below_maximum_balances = _balances_below_activation_churn_limit(spec)
    # Introduce fractional churn to verify that rounding happens after scaling with the slot duration ratio.
    extra = spec.EFFECTIVE_BALANCE_INCREMENT * spec.config.CHURN_LIMIT_QUOTIENT_GLOAS * 3 // 2
    below_maximum_balances[0] += extra

    for balances in (
        below_maximum_balances,
        scaled_churn_balances_equal_activation_churn_limit(spec),
    ):
        _run_churn_limits_with_balances(spec, balances)


@with_phases([HEZE])
@with_presets(
    [MINIMAL],
    reason="mainnet config leads to larger validator set than limit of public/private keys pre-generated",
)
@spec_test
@with_config_overrides({"HEZE_FORK_EPOCH": 2})
@single_phase
def test_churn_limits_above_maximum(spec):
    balances = scaled_churn_balances_exceed_activation_churn_limit(spec) * 2
    _run_churn_limits_with_balances(spec, balances)
