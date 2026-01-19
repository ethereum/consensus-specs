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
    builder_indices=None,
    builder_sweep_indices=None,
    pending_partial_indices=None,
    full_withdrawal_indices=None,
    partial_withdrawal_indices=None,
    compounding_indices=None,
    builder_withdrawal_amounts=None,
    builder_balances=None,
    builder_execution_addresses=None,
    builder_sweep_withdrawable_offsets=None,
    pending_partial_amounts=None,
    partial_excess_balances=None,
    compounding_excess_balances=None,
    pending_partial_withdrawable_offsets=None,
    full_withdrawable_offsets=None,
    validator_balances=None,
    validator_effective_balances=None,
    validator_activation_epoch_offsets=None,
    validator_exit_epoch_offsets=None,
    next_withdrawal_validator_index=None,
    next_withdrawal_builder_index=None,
    parent_block_full=True,
    parent_block_empty=False,
    validate_builder_indices=True,
    validate_validator_indices=True,
):
    """
    Populate the state with all three types of withdrawals based on configuration.

    Args:
        spec: The spec object
        state: The beacon state to modify
        builder_indices: List of builder indices (BuilderIndex) to add builder pending withdrawals for.
                        Builders must already exist in state.builders registry.
        builder_sweep_indices: List of builder indices to set up for sweep withdrawals.
                              Sets withdrawable_epoch <= current_epoch to make builders eligible.
        pending_partial_indices: List of validator indices to set up with pending partial withdrawals
        full_withdrawal_indices: List of validator indices to set up as fully withdrawable
        partial_withdrawal_indices: List of validator indices to set up as partially withdrawable
        compounding_indices: List of validator indices to set up with compounding credentials (0x02).
                            By default, balance is set to MAX_EFFECTIVE_BALANCE_ELECTRA + 1_000_000_000
                            unless compounding_excess_balances is specified.
        builder_withdrawal_amounts: Single amount or dict[BuilderIndex, Gwei] for builder pending withdrawals
                                    (default: 1 ETH for each)
        builder_balances: Single balance or dict[BuilderIndex, Gwei] to set builder balances.
                         Applied to both pending and sweep builders.
        builder_execution_addresses: dict[BuilderIndex, ExecutionAddress] to set builder execution addresses.
                                    Applied to both pending and sweep builders.
        builder_sweep_withdrawable_offsets: Single offset or dict[BuilderIndex, int] for builder sweep
                                           withdrawable_epoch = current_epoch + offset (default: 0)
        pending_partial_amounts: Single amount or dict[ValidatorIndex, Gwei] for pending partial withdrawals
                                 (default: 1_000_000_000 for each)
        partial_excess_balances: Single amount or dict[ValidatorIndex, Gwei] for partial withdrawals
                                 (default: 1_000_000_000 for each)
        compounding_excess_balances: Single amount or dict[ValidatorIndex, Gwei] for compounding validators
                                     excess above MAX_EFFECTIVE_BALANCE_ELECTRA (default: 1_000_000_000)
        pending_partial_withdrawable_offsets: Single offset or dict[ValidatorIndex, int] for pending partial
                                             withdrawals (default: 0, i.e., withdrawable immediately)
        full_withdrawable_offsets: Single offset or dict[ValidatorIndex, int] for full withdrawals
                                  (default: 0, i.e., withdrawable immediately)
        validator_balances: dict[ValidatorIndex, Gwei] to set validator balances.
                           Applied AFTER withdrawal setup (allows overriding for edge case tests).
        validator_effective_balances: dict[ValidatorIndex, Gwei] to set validator effective balances.
                                     Applied AFTER withdrawal setup (allows overriding for edge case tests).
        validator_activation_epoch_offsets: dict[ValidatorIndex, int] to set activation_epoch = current_epoch + offset.
                                           Applied at the start before any withdrawal setup.
        validator_exit_epoch_offsets: dict[ValidatorIndex, int] to set exit_epoch = current_epoch + offset.
                                     Applied at the start before any withdrawal setup.
        next_withdrawal_validator_index: ValidatorIndex to set state.next_withdrawal_validator_index.
                                        Applied at the start before any withdrawal setup.
        next_withdrawal_builder_index: BuilderIndex to set state.next_withdrawal_builder_index.
                                      Applied at the start before any withdrawal setup.
        parent_block_full: If True, set state to indicate parent block was full (default: True)
        parent_block_empty: If True, set state to indicate parent block was empty (default: False)
                           Takes precedence over parent_block_full if both are True
        validate_builder_indices: If True, assert all builder indices exist in registry (default: True)
        validate_validator_indices: If True, assert all validator indices exist in registry (default: True)
    """
    # Initialize mutable default arguments
    if builder_indices is None:
        builder_indices = []
    if builder_sweep_indices is None:
        builder_sweep_indices = []
    if pending_partial_indices is None:
        pending_partial_indices = []
    if full_withdrawal_indices is None:
        full_withdrawal_indices = []
    if partial_withdrawal_indices is None:
        partial_withdrawal_indices = []
    if compounding_indices is None:
        compounding_indices = []

    # Set parent block state (Gloas+)
    if is_post_gloas(spec):
        if parent_block_empty:
            set_parent_block_empty(spec, state)
        elif parent_block_full:
            set_parent_block_full(spec, state)

    # Set next_withdrawal_validator_index if provided
    if next_withdrawal_validator_index is not None:
        state.next_withdrawal_validator_index = next_withdrawal_validator_index

    # Set next_withdrawal_builder_index if provided (Gloas+)
    if is_post_gloas(spec) and next_withdrawal_builder_index is not None:
        state.next_withdrawal_builder_index = spec.BuilderIndex(next_withdrawal_builder_index)

    # Validate all builder indices exist in registry (Gloas+)
    all_builder_indices = set(builder_indices) | set(builder_sweep_indices)
    if validate_builder_indices and is_post_gloas(spec) and all_builder_indices:
        max_builder_index = max(all_builder_indices)
        assert max_builder_index < len(state.builders), (
            f"Builder {max_builder_index} does not exist in state.builders registry"
        )

    # Validate all validator indices exist in registry
    all_validator_indices = (
        set(pending_partial_indices)
        | set(full_withdrawal_indices)
        | set(partial_withdrawal_indices)
        | set(compounding_indices)
    )
    if validate_validator_indices and all_validator_indices:
        max_validator_index = max(all_validator_indices)
        assert max_validator_index < len(state.validators), (
            f"Validator {max_validator_index} does not exist in state.validators registry"
        )

    # Set validator activation epoch offsets if provided (before withdrawal setup)
    if validator_activation_epoch_offsets is not None:
        current_epoch = spec.get_current_epoch(state)
        for validator_index, offset in validator_activation_epoch_offsets.items():
            state.validators[validator_index].activation_epoch = current_epoch + offset

    # Set validator exit epoch offsets if provided (before withdrawal setup)
    if validator_exit_epoch_offsets is not None:
        current_epoch = spec.get_current_epoch(state)
        for validator_index, offset in validator_exit_epoch_offsets.items():
            state.validators[validator_index].exit_epoch = current_epoch + offset

    # Import here to avoid circular imports
    from tests.core.pyspec.eth2spec.test.helpers.withdrawals import (  # noqa: PLC0415
        prepare_pending_withdrawal,
        set_compounding_withdrawal_credential_with_balance,
        set_validator_fully_withdrawable,
        set_validator_partially_withdrawable,
    )

    current_epoch = spec.get_current_epoch(state)

    # Set up compounding validators (Electra+)
    if is_post_electra(spec) and compounding_indices:
        for validator_index in compounding_indices:
            excess_balance = (
                compounding_excess_balances.get(validator_index, 1_000_000_000)
                if isinstance(compounding_excess_balances, dict)
                else (
                    compounding_excess_balances
                    if compounding_excess_balances is not None
                    else 1_000_000_000
                )
            )
            set_compounding_withdrawal_credential_with_balance(
                spec,
                state,
                validator_index,
                balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA + excess_balance,
            )

    # Helper to get parameter value from single value, dict, or None
    def get_param_value(param, index, default):
        """
        Extract a value from a parameter that can be:
        - None: returns the default value
        - A single value (int/Gwei): returns that value for all indices
        - A dict: returns the value for the given index (or default if not present)
        """
        if param is None:
            return default
        if isinstance(param, (int, type(spec.Gwei(0)))):
            return param
        return param.get(index, default)

    # Set up builder pending withdrawals (Gloas+)
    if is_post_gloas(spec) and builder_indices:
        for builder_index in builder_indices:
            amount = get_param_value(
                builder_withdrawal_amounts, builder_index, spec.Gwei(1_000_000_000)
            )

            # Check if builder index is valid
            is_valid_builder = builder_index < len(state.builders)

            if is_valid_builder:
                builder = state.builders[builder_index]

                # Set builder balance if provided
                if builder_balances is not None:
                    balance = get_param_value(builder_balances, builder_index, None)
                    if balance is not None:
                        builder.balance = balance

                # Set builder execution address if provided
                if builder_execution_addresses is not None:
                    address = builder_execution_addresses.get(builder_index)
                    if address is not None:
                        builder.execution_address = spec.ExecutionAddress(address)

                fee_recipient = builder.execution_address
            # Invalid builder index - use provided address or default
            elif builder_execution_addresses is not None:
                address = builder_execution_addresses.get(builder_index)
                fee_recipient = (
                    spec.ExecutionAddress(address)
                    if address
                    else spec.ExecutionAddress(b"\x00" * 20)
                )
            else:
                fee_recipient = spec.ExecutionAddress(b"\x00" * 20)

            # Add builder pending withdrawal
            state.builder_pending_withdrawals.append(
                spec.BuilderPendingWithdrawal(
                    fee_recipient=fee_recipient,
                    amount=amount,
                    builder_index=builder_index,
                )
            )

    # Set up builder sweep withdrawals (Gloas+)
    # Builder sweep occurs when builder.withdrawable_epoch <= current_epoch and balance > 0
    if is_post_gloas(spec) and builder_sweep_indices:
        for builder_index in builder_sweep_indices:
            builder = state.builders[builder_index]

            # Set builder balance if provided
            if builder_balances is not None:
                balance = get_param_value(builder_balances, builder_index, None)
                if balance is not None:
                    builder.balance = balance

            # Set builder execution address if provided
            if builder_execution_addresses is not None:
                address = builder_execution_addresses.get(builder_index)
                if address is not None:
                    builder.execution_address = spec.ExecutionAddress(address)

            # Set withdrawable_epoch to make builder eligible for sweep
            epoch_offset = get_param_value(builder_sweep_withdrawable_offsets, builder_index, 0)
            builder.withdrawable_epoch = current_epoch + epoch_offset

    # Set up pending partial withdrawals (Electra+)
    if is_post_electra(spec) and pending_partial_indices:
        for validator_index in pending_partial_indices:
            amount = get_param_value(pending_partial_amounts, validator_index, 1_000_000_000)
            epoch_offset = get_param_value(pending_partial_withdrawable_offsets, validator_index, 0)

            # Check if validator index is valid
            is_valid_validator = validator_index < len(state.validators)

            if is_valid_validator:
                prepare_pending_withdrawal(
                    spec,
                    state,
                    validator_index,
                    amount=amount,
                    withdrawable_epoch=current_epoch + epoch_offset,
                )
            else:
                # Invalid validator index - create pending withdrawal directly
                state.pending_partial_withdrawals.append(
                    spec.PendingPartialWithdrawal(
                        validator_index=spec.ValidatorIndex(validator_index),
                        amount=spec.Gwei(amount),
                        withdrawable_epoch=current_epoch + epoch_offset,
                    )
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

    # Apply validator balance overrides AFTER withdrawal setup (allows tests to set edge cases)
    if validator_balances is not None:
        for validator_index, balance in validator_balances.items():
            state.balances[validator_index] = balance

    # Apply validator effective balance overrides AFTER withdrawal setup
    if validator_effective_balances is not None:
        for validator_index, effective_balance in validator_effective_balances.items():
            state.validators[validator_index].effective_balance = effective_balance


def assert_process_withdrawals(
    spec,
    state,
    pre_state,
    withdrawal_count=None,
    balances=None,
    balance_deltas=None,
    builder_balances=None,
    builder_balance_deltas=None,
    builder_pending_delta=None,
    pending_partial_delta=None,
    withdrawal_index_delta=None,
    validator_index_delta=None,
    withdrawal_order=None,
    withdrawal_amounts=None,
    withdrawal_amounts_builders=None,
    withdrawal_addresses=None,
    withdrawal_addresses_builders=None,
    no_withdrawal_indices=None,
    all_state_unchanged=None,
):
    """
    Assert expected outcomes from process_withdrawals.

    INVARIANT CHECKS (always run automatically):
    - Balance decreases match withdrawal amounts for ALL withdrawals
    - state.payload_expected_withdrawals matches spec.get_expected_withdrawals()
    - Queue lengths never increase inappropriately
    - Withdrawal indices are sequential from pre_state.next_withdrawal_index
    - next_withdrawal_validator_index advances per spec rules (conditional on full/partial payload)
    - Post-state expected withdrawals differ from pre-state (when withdrawals > 0)
    - Post-state expected withdrawals count is bounded

    TEST-SPECIFIC CHECKS (controlled by parameters):
    - withdrawal_count: Exact number of withdrawals
    - balances/balance_deltas: Specific validator balance checks
    - builder_balances/builder_balance_deltas: Specific builder balance checks
    - builder_pending_delta/pending_partial_delta: Exact queue changes
    - withdrawal_index_delta/validator_index_delta: Index advancement (note: validator_index_delta
      is now redundant with invariant check but kept for backward compatibility)
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
    expected_result = spec.get_expected_withdrawals(pre_state)
    expected_withdrawals = expected_result.withdrawals
    withdrawals = list(state.payload_expected_withdrawals)

    # INVARIANT: Verify payload_expected_withdrawals matches expected
    expected_list = spec.List[spec.Withdrawal, spec.MAX_WITHDRAWALS_PER_PAYLOAD](
        expected_withdrawals
    )
    assert list(withdrawals) == list(expected_list), (
        "state.payload_expected_withdrawals must match spec.get_expected_withdrawals()"
    )

    # INVARIANT: Balance decreases for all withdrawals
    for withdrawal in expected_withdrawals:
        validator_index = withdrawal.validator_index
        if is_post_gloas(spec) and spec.is_builder_index(validator_index):
            builder_index = spec.convert_validator_index_to_builder_index(validator_index)
            pre_balance = pre_state.builders[builder_index].balance
            post_balance = state.builders[builder_index].balance
            # Builder withdrawals cap at available balance (spec uses min())
            expected_deduction = min(withdrawal.amount, pre_balance)
        else:
            pre_balance = pre_state.balances[validator_index]
            post_balance = state.balances[validator_index]
            expected_deduction = withdrawal.amount
        assert post_balance == pre_balance - expected_deduction, (
            f"Index {validator_index} balance must decrease by withdrawal amount"
        )

    # INVARIANT: Queue lengths never increase
    assert len(state.pending_partial_withdrawals) <= len(pre_state.pending_partial_withdrawals), (
        "pending_partial_withdrawals queue must not grow"
    )
    assert len(state.builder_pending_withdrawals) <= len(pre_state.builder_pending_withdrawals), (
        "builder_pending_withdrawals queue must not grow"
    )

    # INVARIANT: Withdrawal indices are sequential from pre_state.next_withdrawal_index
    for i, withdrawal in enumerate(expected_withdrawals):
        expected_index = pre_state.next_withdrawal_index + i
        assert withdrawal.index == expected_index, (
            f"Withdrawal {i}: expected index {expected_index}, got {withdrawal.index}"
        )

    # INVARIANT: next_withdrawal_validator_index advancement per spec
    num_validators = len(pre_state.validators)
    if len(expected_withdrawals) == spec.MAX_WITHDRAWALS_PER_PAYLOAD:
        # Full payload: next validator is after last withdrawal's validator index
        last_validator_index = expected_withdrawals[-1].validator_index
        expected_next = (last_validator_index + 1) % num_validators
    else:
        # Partial payload: advance by sweep size
        expected_next = (
            pre_state.next_withdrawal_validator_index + spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP
        ) % num_validators
    assert state.next_withdrawal_validator_index == expected_next, (
        f"next_withdrawal_validator_index: expected {expected_next}, "
        f"got {state.next_withdrawal_validator_index}"
    )

    # INVARIANT: Post-state expected withdrawals differ and are bounded (when withdrawals > 0)
    if len(expected_withdrawals) > 0:
        post_expected = spec.get_expected_withdrawals(state).withdrawals
        assert list(post_expected) != list(expected_withdrawals), (
            "Post-state expected withdrawals must differ from pre-state"
        )
        bound = min(spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP, spec.MAX_WITHDRAWALS_PER_PAYLOAD)
        assert len(post_expected) <= bound, (
            f"Post-state expected withdrawals ({len(post_expected)}) exceeds bound ({bound})"
        )

    # Withdrawal count verification
    if withdrawal_count is not None:
        assert len(withdrawals) == withdrawal_count

    # Balance verification - explicit values
    if balances is not None:
        for validator_idx, expected_balance in balances.items():
            assert state.balances[validator_idx] == expected_balance, (
                f"Validator {validator_idx}: expected balance {expected_balance}, got {state.balances[validator_idx]}"
            )

    # Balance verification - deltas
    if balance_deltas is not None:
        for validator_idx, delta in balance_deltas.items():
            expected = pre_state.balances[validator_idx] + delta
            assert state.balances[validator_idx] == expected, (
                f"Validator {validator_idx}: expected balance {expected}, got {state.balances[validator_idx]}"
            )

    # Builder balance verification - explicit values
    if builder_balances is not None:
        for builder_idx, expected_balance in builder_balances.items():
            assert state.builders[builder_idx].balance == expected_balance, (
                f"Builder {builder_idx}: expected balance {expected_balance}, got {state.builders[builder_idx].balance}"
            )

    # Builder balance verification - deltas
    if builder_balance_deltas is not None:
        for builder_idx, delta in builder_balance_deltas.items():
            expected = int(pre_state.builders[builder_idx].balance) + delta
            assert int(state.builders[builder_idx].balance) == expected, (
                f"Builder {builder_idx}: expected balance {expected}, got {state.builders[builder_idx].balance}"
            )

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
        expected = (
            pre_state.next_withdrawal_validator_index + validator_index_delta
        ) % num_validators
        assert state.next_withdrawal_validator_index == expected

    # Withdrawal ordering
    if withdrawal_order is not None:
        actual_order = [w.validator_index for w in withdrawals]
        assert actual_order == withdrawal_order

    # Withdrawal content
    if withdrawal_amounts is not None:
        for validator_idx, expected_amount in withdrawal_amounts.items():
            matching = [w for w in withdrawals if w.validator_index == validator_idx]
            assert len(matching) == 1, (
                f"Expected exactly 1 withdrawal for validator {validator_idx}"
            )
            assert matching[0].amount == expected_amount

    if withdrawal_amounts_builders is not None:
        for builder_idx, expected_amount in withdrawal_amounts_builders.items():
            # Convert builder index to validator index (with BUILDER_INDEX_FLAG)
            builder_validator_idx = spec.convert_builder_index_to_validator_index(builder_idx)
            matching = [w for w in withdrawals if w.validator_index == builder_validator_idx]
            assert len(matching) == 1, f"Expected exactly 1 withdrawal for builder {builder_idx}"
            assert matching[0].amount == expected_amount

    if withdrawal_addresses is not None:
        for validator_idx, expected_address in withdrawal_addresses.items():
            matching = [w for w in withdrawals if w.validator_index == validator_idx]
            assert len(matching) == 1
            assert matching[0].address == expected_address

    if withdrawal_addresses_builders is not None:
        for builder_idx, expected_address in withdrawal_addresses_builders.items():
            # Convert builder index to validator index (with BUILDER_INDEX_FLAG)
            builder_validator_idx = spec.convert_builder_index_to_validator_index(builder_idx)
            matching = [w for w in withdrawals if w.validator_index == builder_validator_idx]
            assert len(matching) == 1, f"Expected exactly 1 withdrawal for builder {builder_idx}"
            assert matching[0].address == expected_address

    # No withdrawal verification
    if no_withdrawal_indices is not None:
        for idx in no_withdrawal_indices:
            assert not any(w.validator_index == idx for w in withdrawals), (
                f"Validator {idx} should not have a withdrawal"
            )


def get_expected_withdrawals(spec, state):
    return spec.get_expected_withdrawals(state).withdrawals


def assert_process_withdrawals_pre_gloas(
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
        if is_post_gloas(spec):
            if spec.is_builder_index(index):
                continue
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
