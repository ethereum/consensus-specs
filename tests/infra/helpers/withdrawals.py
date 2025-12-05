from eth2spec.test.helpers.forks import is_post_electra, is_post_gloas


# Import needed helper functions from test helpers (avoiding circular import)
def _import_test_helpers():
    from tests.core.pyspec.eth2spec.test.helpers.withdrawals import (  # noqa: PLC0415
        prepare_pending_withdrawal,
        set_validator_fully_withdrawable,
        set_validator_partially_withdrawable,
    )

    return (
        prepare_pending_withdrawal,
        set_validator_fully_withdrawable,
        set_validator_partially_withdrawable,
    )


def prepare_withdrawals(
    spec,
    state,
    builder_indices=[],
    pending_partial_indices=[],
    full_withdrawal_indices=[],
    partial_withdrawal_indices=[],
    builder_withdrawal_amounts=None,
    pending_partial_amounts=None,
    partial_excess_balances=None,
    builder_withdrawable_offsets=None,
    pending_partial_withdrawable_offsets=None,
    full_withdrawable_offsets=None,
):
    """
    Populate the state with all three types of withdrawals based on configuration.

    Note: For builder withdrawals, validators must already have builder withdrawal credentials
    set (0x03 prefix). Use set_builder_withdrawal_credential() or
    set_builder_withdrawal_credential_with_balance() before calling this function.

    Args:
        spec: The spec object
        state: The beacon state to modify
        builder_indices: List of validator indices (must already have builder credentials)
                        to add builder pending withdrawals for
        pending_partial_indices: List of validator indices to set up with pending partial withdrawals
        full_withdrawal_indices: List of validator indices to set up as fully withdrawable
        partial_withdrawal_indices: List of validator indices to set up as partially withdrawable
        builder_withdrawal_amounts: Single amount or list of amounts for builder withdrawals
                                    (default: MIN_ACTIVATION_BALANCE for each)
        pending_partial_amounts: Single amount or list of amounts for pending partial withdrawals
                                 (default: 1_000_000_000 for each)
        partial_excess_balances: Single amount or list of excess balances for partial withdrawals
                                 (default: 1_000_000_000 for each)
        builder_withdrawable_offsets: Single offset or list of epoch offsets for builder withdrawals
                                      (default: 0, i.e., withdrawable immediately)
        pending_partial_withdrawable_offsets: Single offset or list of epoch offsets for pending partial
                                             withdrawals (default: 0, i.e., withdrawable immediately)
        full_withdrawable_offsets: Single offset or list of epoch offsets for full withdrawals
                                  (default: 0, i.e., withdrawable immediately)
    """
    current_epoch = spec.get_current_epoch(state)

    # Helper to get parameter value from single value, list, or None
    def get_param_value(param, index, default):
        """
        Extract a value from a parameter that can be:
        - None: returns the default value
        - A single value: returns that value for all indices
        - A list: returns the value at the given index (or default if out of bounds)
        """
        if param is None:
            return default
        if isinstance(param, (int, type(spec.Gwei(0)))):
            return param
        return param[index] if index < len(param) else default

    # 1. Set up builder pending withdrawals (Gloas only)
    if is_post_gloas(spec) and builder_indices:
        for i, validator_index in enumerate(builder_indices):
            amount = get_param_value(builder_withdrawal_amounts, i, spec.MIN_ACTIVATION_BALANCE)
            epoch_offset = get_param_value(builder_withdrawable_offsets, i, 0)

            # Verify the validator is already set up as a builder
            validator = state.validators[validator_index]
            assert spec.has_builder_withdrawal_credential(validator), (
                f"Validator {validator_index} must have builder withdrawal credentials. "
                f"Use set_builder_withdrawal_credential() or set_builder_withdrawal_credential_with_balance() first."
            )

            # Verify the builder has sufficient balance
            assert state.balances[validator_index] >= amount + spec.MIN_ACTIVATION_BALANCE, (
                f"Validator {validator_index} needs balance >= {amount + spec.MIN_ACTIVATION_BALANCE}, "
                f"but has {state.balances[validator_index]}"
            )

            # Add builder pending withdrawal
            address = validator.withdrawal_credentials[12:]
            state.builder_pending_withdrawals.append(
                spec.BuilderPendingWithdrawal(
                    fee_recipient=address,
                    amount=amount,
                    builder_index=validator_index,
                    withdrawable_epoch=current_epoch + epoch_offset,  # Can be in the future
                )
            )

    # Import helpers lazily to avoid circular imports
    (
        prepare_pending_withdrawal,
        set_validator_fully_withdrawable,
        set_validator_partially_withdrawable,
    ) = _import_test_helpers()

    # 2. Set up pending partial withdrawals (Electra+)
    if is_post_electra(spec) and pending_partial_indices:
        for i, validator_index in enumerate(pending_partial_indices):
            amount = get_param_value(pending_partial_amounts, i, 1_000_000_000)
            epoch_offset = get_param_value(pending_partial_withdrawable_offsets, i, 0)

            prepare_pending_withdrawal(
                spec,
                state,
                validator_index,
                amount=amount,
                withdrawable_epoch=current_epoch + epoch_offset,  # Can be in the future
            )

    # 3. Set up full withdrawals
    for i, validator_index in enumerate(full_withdrawal_indices):
        epoch_offset = get_param_value(full_withdrawable_offsets, i, 0)
        set_validator_fully_withdrawable(
            spec,
            state,
            validator_index,
            withdrawable_epoch=current_epoch + epoch_offset,  # Can be in the future
        )

    # 4. Set up partial withdrawals
    for i, validator_index in enumerate(partial_withdrawal_indices):
        excess_balance = get_param_value(partial_excess_balances, i, 1_000_000_000)

        set_validator_partially_withdrawable(
            spec,
            state,
            validator_index,
            excess_balance=excess_balance,
        )


def get_expected_withdrawals(spec, state):
    if is_post_gloas(spec):
        withdrawals, _, _ = spec.get_expected_withdrawals(state)
        return withdrawals
    elif is_post_electra(spec):
        withdrawals, _ = spec.get_expected_withdrawals(state)
        return withdrawals
    else:
        return spec.get_expected_withdrawals(state)


def verify_withdrawals_post_state(
    spec,
    pre_state,
    post_state,
    execution_payload,
    expected_withdrawals,
    fully_withdrawable_indices,
    partial_withdrawals_indices,
    pending_withdrawal_requests,
):
    """
    Verifies the correctness of the post-state after processing withdrawals.
    """

    # Since gloas, if parent block was not full, no withdrawals processed, indices unchanged
    if is_post_gloas(spec) and not spec.is_parent_block_full(pre_state):
        assert post_state.next_withdrawal_index == pre_state.next_withdrawal_index
        assert (
            post_state.next_withdrawal_validator_index == pre_state.next_withdrawal_validator_index
        )
        return

    _verify_withdrawals_next_withdrawal_index(spec, pre_state, post_state, expected_withdrawals)

    # Verify withdrawals indexes
    for index, withdrawal in enumerate(
        expected_withdrawals if is_post_gloas(spec) else execution_payload.withdrawals
    ):
        assert withdrawal.index == pre_state.next_withdrawal_index + index

    if fully_withdrawable_indices is not None or partial_withdrawals_indices is not None:
        _verify_withdrawals_post_state_balances(
            spec,
            post_state,
            expected_withdrawals,
            fully_withdrawable_indices,
            partial_withdrawals_indices,
        )

    # Check withdrawal requests
    if pending_withdrawal_requests is not None:
        _verify_withdrawals_requests(execution_payload, pending_withdrawal_requests)


def _verify_withdrawals_next_withdrawal_index(spec, pre_state, post_state, expected_withdrawals):
    """
    Verify post_state.next_withdrawal_index
    """
    assert post_state.next_withdrawal_index == pre_state.next_withdrawal_index + len(
        expected_withdrawals
    )
    if len(expected_withdrawals) == 0:
        assert post_state.next_withdrawal_index == pre_state.next_withdrawal_index
    elif len(expected_withdrawals) <= spec.MAX_WITHDRAWALS_PER_PAYLOAD:
        latest_withdrawal = expected_withdrawals[-1]
        assert post_state.next_withdrawal_index == latest_withdrawal.index + 1

        # variable expected_withdrawals comes from pre_state
        assert expected_withdrawals != get_expected_withdrawals(spec, post_state)
        bound = min(spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP, spec.MAX_WITHDRAWALS_PER_PAYLOAD)
        assert len(get_expected_withdrawals(spec, post_state)) <= bound
    else:
        raise ValueError(
            "len(expected_withdrawals) should not be greater than MAX_WITHDRAWALS_PER_PAYLOAD"
        )

    # Verify post_state.next_withdrawal_validator_index
    if len(expected_withdrawals) == spec.MAX_WITHDRAWALS_PER_PAYLOAD:
        # Next sweep starts after the latest withdrawal's validator index
        next_validator_index = (expected_withdrawals[-1].validator_index + 1) % len(
            post_state.validators
        )
        assert post_state.next_withdrawal_validator_index == next_validator_index
    else:
        # Advance sweep by the max length if there was not a full set of withdrawals
        next_index = (
            pre_state.next_withdrawal_validator_index + spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP
        )
        next_validator_index = next_index % len(post_state.validators)
        assert post_state.next_withdrawal_validator_index == next_validator_index


def _verify_withdrawals_post_state_balances(
    spec, state, expected_withdrawals, fully_withdrawable_indices, partial_withdrawals_indices
):
    if len(expected_withdrawals) == 0:
        return

    expected_withdrawals_validator_indices = [
        withdrawal.validator_index for withdrawal in expected_withdrawals
    ]

    for index in fully_withdrawable_indices:
        if index in expected_withdrawals_validator_indices:
            assert state.balances[index] == 0
        else:
            assert state.balances[index] > 0
    for index in partial_withdrawals_indices:
        if is_post_electra(spec):
            max_effective_balance = spec.get_max_effective_balance(state.validators[index])
        else:
            max_effective_balance = spec.MAX_EFFECTIVE_BALANCE

        if index in expected_withdrawals_validator_indices:
            assert state.balances[index] == max_effective_balance
        else:
            assert state.balances[index] > max_effective_balance


def _verify_withdrawals_requests(execution_payload, pending_withdrawal_requests):
    assert len(pending_withdrawal_requests) <= len(execution_payload.withdrawals)
    for index, request in enumerate(pending_withdrawal_requests):
        withdrawal = execution_payload.withdrawals[index]
        assert withdrawal.validator_index == request.validator_index
        assert withdrawal.amount == request.amount
