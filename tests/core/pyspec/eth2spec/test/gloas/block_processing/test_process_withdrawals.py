from tests.core.pyspec.eth2spec.test.context import (
    spec_state_test,
    with_gloas_and_later,
)


@with_gloas_and_later
@spec_state_test
def test_full_builder_payload_next_validator_index_bug(spec, state):
    """
    Documents spec bug: When all withdrawals in a full payload are builder withdrawals,
    next_withdrawal_validator_index is calculated incorrectly.

    The spec uses (withdrawals[-1].validator_index + 1) % num_validators, but builder
    withdrawals have BUILDER_INDEX_FLAG (2^40) set in validator_index, producing
    incorrect results.

    Input State:
        - builder_pending_withdrawals: MAX_WITHDRAWALS_PER_PAYLOAD entries
        - All validator balances capped (no validator withdrawals)
        - next_withdrawal_validator_index: Known starting value

    Bug Demonstrated:
        - Actual: (builder_validator_index + 1) % num_validators (incorrect)
        - Expected: (start_index + MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP) % num_validators

    This test passes with current spec behavior (documenting the bug).
    When the spec is fixed, this test should be updated to verify correct behavior.
    """
    # Setup: Record initial state
    num_validators = len(state.validators)
    starting_validator_index = state.next_withdrawal_validator_index

    # Setup: Create MAX builder pending withdrawals manually
    withdrawal_amount = spec.Gwei(1_000_000_000)
    state.builder_pending_withdrawals = []
    for builder_index in range(spec.MAX_WITHDRAWALS_PER_PAYLOAD):
        state.builders[builder_index].balance = withdrawal_amount + spec.MIN_DEPOSIT_AMOUNT
        state.builder_pending_withdrawals.append(
            spec.BuilderPendingWithdrawal(
                builder_index=spec.BuilderIndex(builder_index),
                fee_recipient=state.builders[builder_index].execution_address,
                amount=withdrawal_amount,
            )
        )

    # Setup: Cap validator balances to prevent any sweep withdrawals
    for i, validator in enumerate(state.validators):
        if validator.withdrawal_credentials[0:1] == spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX:
            state.balances[i] = min(state.balances[i], spec.MAX_EFFECTIVE_BALANCE)

    # Verify setup: All expected withdrawals are builder withdrawals
    expected_result = spec.get_expected_withdrawals(state)
    assert len(expected_result.withdrawals) == spec.MAX_WITHDRAWALS_PER_PAYLOAD
    for w in expected_result.withdrawals:
        assert spec.is_builder_index(w.validator_index), "All withdrawals must be builder withdrawals"

    # Execute
    pre_state = state.copy()
    yield "pre", pre_state
    spec.process_withdrawals(state)
    yield "post", state

    # Calculate what spec actually produces in update_next_withdrawal_validator_index (CAPELLA)
    # expected_result.withdrawals[-1].validator_index has BUILDER_INDEX_FLAG set !!
    assert spec.is_builder_index(expected_result.withdrawals[-1].validator_index), "Last withdrawal must be a builder withdrawal"
    last_builder_validator_index = expected_result.withdrawals[-1].validator_index
    buggy_result = (last_builder_validator_index + 1) % num_validators

    # Calculate what the correct result should be
    correct_result = (
        starting_validator_index + spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP
    ) % num_validators

    # Assert current behavior
    assert state.next_withdrawal_validator_index == buggy_result, (
        f"Spec produces {state.next_withdrawal_validator_index}, expected buggy result {buggy_result}"
    )
    assert buggy_result != correct_result, (
        f"Bug demonstration: spec produces {buggy_result}, correct would be {correct_result}"
    )
