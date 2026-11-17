from eth_consensus_specs.test.context import (
    single_phase,
    spec_test,
    with_all_phases_from_to,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import ELECTRA, FULU, MAINNET, PHASE0
from eth_consensus_specs.test.helpers.forks import is_post_electra


def create_active_state(spec, validator_count, balance_eth):
    balance = spec.Gwei(balance_eth * 10**9)
    validator = spec.Validator(
        effective_balance=balance,
        activation_epoch=0,
        exit_epoch=spec.FAR_FUTURE_EPOCH,
        withdrawable_epoch=spec.FAR_FUTURE_EPOCH,
    )
    state = spec.BeaconState()
    state.validators = type(state.validators)(data=[validator] * validator_count)
    state.balances = type(state.balances)(data=[balance] * validator_count)
    return state


@with_all_phases_from_to(PHASE0, FULU)
@spec_test
@single_phase
def test_compute_weak_subjectivity_period_high_balance(spec):
    # Before Electra, this exercises the max of validator churn and balance top-ups.
    state = create_active_state(spec, 32768, 32)
    period = spec.compute_weak_subjectivity_period(state)

    if spec.config.PRESET_BASE == MAINNET:
        expected = 665
    elif is_post_electra(spec):
        expected = 257
    else:
        expected = 354
    assert isinstance(period, spec.Epoch)
    assert period == expected


@with_all_phases_from_to(PHASE0, FULU)
@spec_test
@single_phase
def test_compute_weak_subjectivity_period_low_balance(spec):
    # Before Electra, this exercises the lower-average-balance branch.
    state = create_active_state(spec, 32768, 16)
    period = spec.compute_weak_subjectivity_period(state)

    if is_post_electra(spec):
        expected = 460 if spec.config.PRESET_BASE == MAINNET else 257
    else:
        expected = 265 if spec.config.PRESET_BASE == MAINNET else 294
    assert isinstance(period, spec.Epoch)
    assert period == expected


@with_all_phases_from_to(PHASE0, ELECTRA)
@spec_test
@single_phase
@with_presets([MAINNET], reason="reference table uses the mainnet preset")
def test_compute_weak_subjectivity_period_reference_table(spec):
    # Literal expected values from the Phase 0 weak subjectivity guide.
    for balance_eth, validator_count, expected in (
        (28, 32768, 504),
        (28, 65536, 752),
        (32, 32768, 665),
        (32, 65536, 1075),
    ):
        state = create_active_state(spec, validator_count, balance_eth)
        period = spec.compute_weak_subjectivity_period(state)
        assert isinstance(period, spec.Epoch)
        assert period == expected
