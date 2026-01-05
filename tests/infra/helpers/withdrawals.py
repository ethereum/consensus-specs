from eth2spec.test.helpers.forks import is_post_electra, is_post_gloas


def set_parent_block_full(spec, state):
    """
    Helper to set state indicating parent block was full.
    """
    state.latest_block_hash = state.latest_execution_payload_bid.block_hash

    # For testing purposes, ensure we have a block hash
    if state.latest_block_hash == b"\x00" * 32:
        state.latest_block_hash = b"\x01" * 32
        state.latest_execution_payload_bid.block_hash = state.latest_block_hash


def set_parent_block_empty(spec, state):
    """
    Helper to set state indicating parent block was empty.
    """
    state.latest_block_hash = b"\x00" * 32
    state.latest_execution_payload_bid.block_hash = b"\x01" * 32


def prepare_process_withdrawals(
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
    builder_credentials=None,
    parent_block_full=True,
    parent_block_empty=False,
):
    """
    Populate the state with all three types of withdrawals based on configuration.

    Args:
        spec: The spec object
        state: The beacon state to modify
        builder_indices: List of validator indices to add builder pending withdrawals for
        pending_partial_indices: List of validator indices to set up with pending partial withdrawals
        full_withdrawal_indices: List of validator indices to set up as fully withdrawable
        partial_withdrawal_indices: List of validator indices to set up as partially withdrawable
        builder_withdrawal_amounts: Single amount or dict[ValidatorIndex, Gwei] for builder withdrawals
                                    (default: MIN_ACTIVATION_BALANCE for each)
        pending_partial_amounts: Single amount or dict[ValidatorIndex, Gwei] for pending partial withdrawals
                                 (default: 1_000_000_000 for each)
        partial_excess_balances: Single amount or dict[ValidatorIndex, Gwei] for partial withdrawals
                                 (default: 1_000_000_000 for each)
        builder_withdrawable_offsets: Single offset or dict[ValidatorIndex, int] for builder withdrawals
                                      (default: 0, i.e., withdrawable immediately)
        pending_partial_withdrawable_offsets: Single offset or dict[ValidatorIndex, int] for pending partial
                                             withdrawals (default: 0, i.e., withdrawable immediately)
        full_withdrawable_offsets: Single offset or dict[ValidatorIndex, int] for full withdrawals
                                  (default: 0, i.e., withdrawable immediately)
        builder_credentials: List of validator indices to set builder withdrawal credentials on
                            (default: None, which uses builder_indices)
        parent_block_full: If True, set state to indicate parent block was full (default: True)
        parent_block_empty: If True, set state to indicate parent block was empty (default: False)
                           Takes precedence over parent_block_full if both are True
    """
    # Set parent block state (Gloas+)
    if is_post_gloas(spec):
        if parent_block_empty:
            set_parent_block_empty(spec, state)
        elif parent_block_full:
            set_parent_block_full(spec, state)

    # Import here to avoid circular imports
    from tests.core.pyspec.eth2spec.test.helpers.withdrawals import (  # noqa: PLC0415
        prepare_pending_withdrawal,
        set_builder_withdrawal_credential,
        set_validator_fully_withdrawable,
        set_validator_partially_withdrawable,
    )

    current_epoch = spec.get_current_epoch(state)

    # Helper to get parameter value from single value, dict, or None
    def get_param_value(param, validator_index, default):
        """
        Extract a value from a parameter that can be:
        - None: returns the default value
        - A single value (int/Gwei): returns that value for all validator indices
        - A dict: returns the value for the given validator_index (or default if not present)
        """
        if param is None:
            return default
        if isinstance(param, (int, type(spec.Gwei(0)))):
            return param
        return param.get(validator_index, default)

    # Set builder withdrawal credentials (Gloas+)
    if is_post_gloas(spec):
        credentials_indices = (
            builder_credentials if builder_credentials is not None else builder_indices
        )
        for validator_index in credentials_indices:
            set_builder_withdrawal_credential(spec, state, validator_index)

    # Set up builder pending withdrawals (Gloas+)
    if is_post_gloas(spec) and builder_indices:
        for validator_index in builder_indices:
            amount = get_param_value(
                builder_withdrawal_amounts, validator_index, spec.MIN_ACTIVATION_BALANCE
            )
            epoch_offset = get_param_value(builder_withdrawable_offsets, validator_index, 0)

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

    # Set up pending partial withdrawals (Electra+)
    if is_post_electra(spec) and pending_partial_indices:
        for validator_index in pending_partial_indices:
            amount = get_param_value(pending_partial_amounts, validator_index, 1_000_000_000)
            epoch_offset = get_param_value(pending_partial_withdrawable_offsets, validator_index, 0)

            prepare_pending_withdrawal(
                spec,
                state,
                validator_index,
                amount=amount,
                withdrawable_epoch=current_epoch + epoch_offset,  # Can be in the future
            )

    # Set up full withdrawals
    for validator_index in full_withdrawal_indices:
        epoch_offset = get_param_value(full_withdrawable_offsets, validator_index, 0)
        set_validator_fully_withdrawable(
            spec,
            state,
            validator_index,
            withdrawable_epoch=current_epoch + epoch_offset,  # Can be in the future
        )

    # Set up partial withdrawals
    for validator_index in partial_withdrawal_indices:
        excess_balance = get_param_value(partial_excess_balances, validator_index, 1_000_000_000)

        set_validator_partially_withdrawable(
            spec,
            state,
            validator_index,
            excess_balance=excess_balance,
        )


def assert_process_withdrawals(
    spec,
    state,
    pre_state,
    withdrawal_count=None,
    balances=None,
    balance_deltas=None,
    builder_pending_delta=None,
    pending_partial_delta=None,
    withdrawal_index_delta=None,
    validator_index_delta=None,
    withdrawal_order=None,
    withdrawal_amounts=None,
    withdrawal_addresses=None,
    no_withdrawal_indices=None,
    all_state_unchanged=None,
):
    """
    Assert expected outcomes from process_withdrawals.

    INVARIANT CHECKS (always run automatically):
    - Balance decreases match withdrawal amounts for ALL withdrawals
    - state.payload_expected_withdrawals matches spec.get_expected_withdrawals()
    - Queue lengths never increase inappropriately

    TEST-SPECIFIC CHECKS (controlled by parameters):
    - withdrawal_count: Exact number of withdrawals
    - balances/balance_deltas: Specific validator balance checks
    - builder_pending_delta/pending_partial_delta: Exact queue changes
    - withdrawal_index_delta/validator_index_delta: Index advancement
    - withdrawal_order/amounts/addresses: Withdrawal content verification

    Naming convention:
    - No prefix: explicit values (balances, withdrawal_count, withdrawal_order, etc.)
    - *_delta suffix: changes from pre_state (builder_pending_delta, balance_deltas, etc.)
    """
    # Early exit check (skip all invariant checks)
    if all_state_unchanged:
        assert state.balances == pre_state.balances
        assert state.next_withdrawal_index == pre_state.next_withdrawal_index
        assert state.next_withdrawal_validator_index == pre_state.next_withdrawal_validator_index
        assert len(state.builder_pending_withdrawals) == len(pre_state.builder_pending_withdrawals)
        assert len(state.pending_partial_withdrawals) == len(pre_state.pending_partial_withdrawals)
        return

    # Get expected withdrawals for invariant checks
    expected_withdrawals, _, _ = spec.get_expected_withdrawals(pre_state)
    withdrawals = list(state.payload_expected_withdrawals)

    # INVARIANT: Verify payload_expected_withdrawals matches expected
    expected_list = spec.List[spec.Withdrawal, spec.MAX_WITHDRAWALS_PER_PAYLOAD](expected_withdrawals)
    assert list(withdrawals) == list(expected_list), \
        "state.payload_expected_withdrawals must match spec.get_expected_withdrawals()"

    # INVARIANT: Balance decreases for all withdrawals
    for withdrawal in expected_withdrawals:
        validator_index = withdrawal.validator_index
        pre_balance = pre_state.balances[validator_index]
        post_balance = state.balances[validator_index]
        assert post_balance == pre_balance - withdrawal.amount, \
            f"Validator {validator_index} balance must decrease by withdrawal amount"

    # INVARIANT: Queue lengths never increase
    assert len(state.pending_partial_withdrawals) <= len(pre_state.pending_partial_withdrawals), \
        "pending_partial_withdrawals queue must not grow"
    assert len(state.builder_pending_withdrawals) <= len(pre_state.builder_pending_withdrawals), \
        "builder_pending_withdrawals queue must not grow"

    # Withdrawal count verification
    if withdrawal_count is not None:
        assert len(withdrawals) == withdrawal_count

    # Balance verification - explicit values
    if balances is not None:
        for validator_idx, expected_balance in balances.items():
            assert state.balances[validator_idx] == expected_balance, \
                f"Validator {validator_idx}: expected balance {expected_balance}, got {state.balances[validator_idx]}"

    # Balance verification - deltas
    if balance_deltas is not None:
        for validator_idx, delta in balance_deltas.items():
            expected = pre_state.balances[validator_idx] + delta
            assert state.balances[validator_idx] == expected, \
                f"Validator {validator_idx}: expected balance {expected}, got {state.balances[validator_idx]}"

    # Queue state - deltas from pre_state
    if builder_pending_delta is not None:
        expected = len(pre_state.builder_pending_withdrawals) + builder_pending_delta
        assert len(state.builder_pending_withdrawals) == expected

    if pending_partial_delta is not None:
        expected = len(pre_state.pending_partial_withdrawals) + pending_partial_delta
        assert len(state.pending_partial_withdrawals) == expected

    # Index state - deltas from pre_state
    if withdrawal_index_delta is not None:
        expected = pre_state.next_withdrawal_index + withdrawal_index_delta
        assert state.next_withdrawal_index == expected

    if validator_index_delta is not None:
        num_validators = len(pre_state.validators)
        expected = (pre_state.next_withdrawal_validator_index + validator_index_delta) % num_validators
        assert state.next_withdrawal_validator_index == expected

    # Withdrawal ordering
    if withdrawal_order is not None:
        actual_order = [w.validator_index for w in withdrawals]
        assert actual_order == withdrawal_order

    # Withdrawal content
    if withdrawal_amounts is not None:
        for validator_idx, expected_amount in withdrawal_amounts.items():
            matching = [w for w in withdrawals if w.validator_index == validator_idx]
            assert len(matching) == 1, f"Expected exactly 1 withdrawal for validator {validator_idx}"
            assert matching[0].amount == expected_amount

    if withdrawal_addresses is not None:
        for validator_idx, expected_address in withdrawal_addresses.items():
            matching = [w for w in withdrawals if w.validator_index == validator_idx]
            assert len(matching) == 1
            assert matching[0].address == expected_address

    # No withdrawal verification
    if no_withdrawal_indices is not None:
        for idx in no_withdrawal_indices:
            assert not any(w.validator_index == idx for w in withdrawals), \
                f"Validator {idx} should not have a withdrawal"


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
