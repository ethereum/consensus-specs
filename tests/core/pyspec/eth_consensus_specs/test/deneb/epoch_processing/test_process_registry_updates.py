from eth_consensus_specs.test.context import (
    scaled_churn_balances_equal_activation_churn_limit,
    scaled_churn_balances_exceed_activation_churn_limit,
    single_phase,
    spec_state_test,
    spec_test,
    with_custom_state,
    with_deneb_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import MINIMAL
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_with
from eth_consensus_specs.test.helpers.forks import is_post_electra
from eth_consensus_specs.test.helpers.keys import pubkeys


def run_process_registry_updates(spec, state):
    yield from run_epoch_processing_with(spec, state, "process_registry_updates")


def run_test_activation_churn_limit(spec, state):
    mock_activations = spec.get_validator_activation_churn_limit(state) * 2

    validator_count_0 = len(state.validators)

    balance = spec.MIN_ACTIVATION_BALANCE if is_post_electra(spec) else spec.MAX_EFFECTIVE_BALANCE

    for i in range(mock_activations):
        index = validator_count_0 + i
        validator = spec.Validator(
            pubkey=pubkeys[index],
            withdrawal_credentials=spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
            + b"\x00" * 11
            + b"\x56" * 20,
            activation_eligibility_epoch=0,
            activation_epoch=spec.FAR_FUTURE_EPOCH,
            exit_epoch=spec.FAR_FUTURE_EPOCH,
            withdrawable_epoch=spec.FAR_FUTURE_EPOCH,
            effective_balance=balance,
        )
        state.validators.append(validator)
        state.balances.append(balance)
        state.previous_epoch_participation.append(spec.ParticipationFlags(0b0000_0000))
        state.current_epoch_participation.append(spec.ParticipationFlags(0b0000_0000))
        state.inactivity_scores.append(0)
        state.validators[index].activation_epoch = spec.FAR_FUTURE_EPOCH

    churn_limit_0 = spec.get_validator_activation_churn_limit(state)

    yield from run_process_registry_updates(spec, state)

    # Half should churn in first run of registry update
    for i in range(mock_activations):
        index = validator_count_0 + i
        # NOTE: activations are gated different after EIP-7251
        # all eligible validators have been activated
        if index < validator_count_0 + churn_limit_0 or is_post_electra(spec):
            # The eligible validators within the activation churn limit should have been activated
            assert state.validators[index].activation_epoch < spec.FAR_FUTURE_EPOCH
        else:
            assert state.validators[index].activation_epoch == spec.FAR_FUTURE_EPOCH


@with_deneb_and_later
@with_presets(
    [MINIMAL],
    reason="mainnet config leads to larger validator set than limit of public/private keys pre-generated",
)
@spec_test
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_churn_limit,
    threshold_fn=lambda spec: spec.config.EJECTION_BALANCE,
)
@single_phase
def test_activation_churn_limit__greater_than_activation_limit(spec, state):
    assert (
        spec.get_validator_activation_churn_limit(state)
        == spec.config.MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT
    )
    assert spec.get_validator_churn_limit(state) > spec.config.MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT
    yield from run_test_activation_churn_limit(spec, state)


@with_deneb_and_later
@with_presets(
    [MINIMAL],
    reason="mainnet config leads to larger validator set than limit of public/private keys pre-generated",
)
@spec_test
@with_custom_state(
    balances_fn=scaled_churn_balances_equal_activation_churn_limit,
    threshold_fn=lambda spec: spec.config.EJECTION_BALANCE,
)
@single_phase
def test_activation_churn_limit__equal_to_activation_limit(spec, state):
    assert (
        spec.get_validator_activation_churn_limit(state)
        == spec.config.MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT
    )
    assert spec.get_validator_churn_limit(state) == spec.config.MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT
    yield from run_test_activation_churn_limit(spec, state)


@with_deneb_and_later
@with_presets(
    [MINIMAL],
    reason="mainnet config leads to larger validator set than limit of public/private keys pre-generated",
)
@spec_state_test
def test_activation_churn_limit__less_than_activation_limit(spec, state):
    assert (
        spec.get_validator_activation_churn_limit(state)
        < spec.config.MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT
    )
    assert spec.get_validator_churn_limit(state) < spec.config.MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT
    yield from run_test_activation_churn_limit(spec, state)
