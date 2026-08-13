from eth_consensus_specs.test.context import spec_state_test, with_eip8148_and_later
from eth_consensus_specs.test.helpers.epoch_processing import (
    run_epoch_processing_to,
    run_process_slots_up_to_epoch_boundary,
)
from eth_consensus_specs.test.helpers.withdrawals import (
    set_compounding_withdrawal_credential_with_balance,
)


@with_eip8148_and_later
@spec_state_test
def test_effective_balance_capped_by_custom_sweep_threshold(spec, state):
    """Test that a custom sweep threshold caps effective balance growth."""
    run_process_slots_up_to_epoch_boundary(spec, state)
    run_epoch_processing_to(
        spec, state, "process_effective_balance_updates", enable_slots_processing=False
    )

    validator_index = 0
    threshold = spec.MIN_ACTIVATION_BALANCE + 8 * spec.EFFECTIVE_BALANCE_INCREMENT
    effective_balance = threshold - spec.EFFECTIVE_BALANCE_INCREMENT
    balance = threshold + 2 * spec.EFFECTIVE_BALANCE_INCREMENT
    set_compounding_withdrawal_credential_with_balance(
        spec,
        state,
        validator_index,
        effective_balance=effective_balance,
        balance=balance,
    )
    state.validator_sweep_thresholds[validator_index] = threshold

    hysteresis_increment = spec.EFFECTIVE_BALANCE_INCREMENT // spec.HYSTERESIS_QUOTIENT
    upward_threshold = hysteresis_increment * spec.HYSTERESIS_UPWARD_MULTIPLIER
    assert effective_balance + upward_threshold < balance

    yield "pre", state
    spec.process_effective_balance_updates(state)
    yield "post", state

    assert state.validators[validator_index].effective_balance == threshold
