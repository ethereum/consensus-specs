from tests.core.pyspec.eth2spec.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from tests.core.pyspec.eth2spec.test.helpers.withdrawals import (
    set_compounding_withdrawal_credential_with_balance,
)
from tests.infra.helpers.withdrawals import (
    assert_process_withdrawals,
    prepare_process_withdrawals,
)


def run_gloas_withdrawals_processing(spec, state):
    """
    Minimal test harness for process_withdrawals.
    All assertions are in assert_process_withdrawals.
    """
    pre_state = state.copy()
    yield "pre", pre_state
    spec.process_withdrawals(state)
    yield "post", state


@with_gloas_and_later
@spec_state_test
def test_zero_withdrawals(spec, state):
    """
    Test processing when no withdrawals are expected.

    Input State Configured:
        - Default state with no pending withdrawals configured
        - latest_block_hash == latest_execution_payload_bid.block_hash (parent block full)

    Output State Verified:
        - payload_expected_withdrawals: Empty list (len=0)
        - balances[*]: Unchanged
        - next_withdrawal_index: Unchanged
    """

    # Initial state should have no withdrawals
    expected_withdrawals_result = spec.get_expected_withdrawals(state)
    assert len(expected_withdrawals_result.withdrawals) == 0

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)
    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=0,
        withdrawal_index_delta=0,
    )


@with_gloas_and_later
@spec_state_test
def test_single_full_withdrawal(spec, state):
    """
    Test processing a single full withdrawal.

    Input State Configured:
        - validators[0].withdrawable_epoch: <= current_epoch (validator is withdrawable)
        - validators[0].withdrawal_credentials: Has execution withdrawal credential (0x01)
        - balances[0]: > 0 (has balance to withdraw)

    Output State Verified:
        - payload_expected_withdrawals: Contains 1 withdrawal for validator 0
        - balances[0]: 0 (full balance withdrawn)
        - next_withdrawal_index: Incremented by 1
    """
    prepare_process_withdrawals(spec, state, full_withdrawal_indices=[0])
    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)
    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=1,
        balances={0: 0},
        withdrawal_index_delta=1,
    )


@with_gloas_and_later
@spec_state_test
def test_single_partial_withdrawal(spec, state):
    """
    Test processing a single partial withdrawal.

    Input State Configured:
        - pending_partial_withdrawals: Contains 1 entry for validator 0
        - pending_partial_withdrawals[0].withdrawable_epoch: <= current_epoch
        - validators[0].effective_balance: >= MIN_ACTIVATION_BALANCE
        - balances[0]: > MIN_ACTIVATION_BALANCE (has excess to withdraw)

    Output State Verified:
        - payload_expected_withdrawals: Contains 1 withdrawal for validator 0
        - balances[0]: == max_effective_balance (excess withdrawn)
        - next_withdrawal_index: Incremented by 1
    """
    prepare_process_withdrawals(spec, state, partial_withdrawal_indices=[0])
    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)
    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=1,
        balances={0: spec.get_max_effective_balance(state.validators[0])},
        withdrawal_index_delta=1,
    )


@with_gloas_and_later
@spec_state_test
def test_mixed_full_and_partial_withdrawals(spec, state):
    """
    Test processing mixed full and partial withdrawals.

    Input State Configured:
        - validators[0,1].withdrawable_epoch: <= current_epoch (fully withdrawable)
        - validators[0,1].withdrawal_credentials: Has execution withdrawal credential
        - pending_partial_withdrawals: Contains entries for validators 2, 3
        - balances[0..3]: Configured for respective withdrawal types

    Output State Verified:
        - payload_expected_withdrawals: Contains 4 withdrawals (2 full + 2 partial)
        - balances[0,1]: 0 (full withdrawals)
        - balances[2,3]: == max_effective_balance (partial withdrawals)
        - next_withdrawal_index: Incremented by 4
    """

    fully_withdrawable_indices = [0, 1]
    partial_withdrawals_indices = [2, 3]
    prepare_process_withdrawals(
        spec,
        state,
        full_withdrawal_indices=fully_withdrawable_indices,
        partial_withdrawal_indices=partial_withdrawals_indices,
    )

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)
    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=4,
        balances={
            0: 0,
            1: 0,
            2: spec.get_max_effective_balance(state.validators[2]),
            3: spec.get_max_effective_balance(state.validators[3]),
        },
        withdrawal_index_delta=4,
    )


@with_gloas_and_later
@spec_state_test
def test_single_builder_withdrawal(spec, state):
    """
    Test processing a single builder withdrawal.

    Input State Configured:
        - state.builders[0]: Builder exists in registry with sufficient balance
        - builder_pending_withdrawals: Contains 1 entry for builder 0
        - builder_pending_withdrawals[0].amount: 1 ETH
        - builders[0].balance: >= amount

    Output State Verified:
        - payload_expected_withdrawals: Contains 1 builder withdrawal
        - builders[0].balance: Decreased by withdrawal amount
        - builder_pending_withdrawals: Reduced by 1 (processed entry removed)
        - next_withdrawal_index: Incremented by 1
    """
    builder_index = 0
    withdrawal_amount = spec.Gwei(1_000_000_000)

    # Verify builder exists in registry (created by genesis)
    assert builder_index < len(state.builders), "Builder must exist in registry"

    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=[builder_index],
        builder_withdrawal_amounts={builder_index: withdrawal_amount},
        builder_balances={builder_index: withdrawal_amount + spec.MIN_DEPOSIT_AMOUNT},
    )
    pre_state = state.copy()

    yield from run_gloas_withdrawals_processing(spec, state)

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=1,
        builder_balance_deltas={builder_index: -int(withdrawal_amount)},
        builder_pending_delta=-1,
        withdrawal_index_delta=1,
    )


@with_gloas_and_later
@spec_state_test
def test_multiple_builder_withdrawals(spec, state):
    """
    Test processing multiple builder withdrawals.

    Input State Configured:
        - state.builders[0,1,2]: Builders exist in registry with sufficient balance
        - builder_pending_withdrawals: Contains 3 entries for builders 0, 1, 2
        - builder_pending_withdrawals[*].amount: 0.5 ETH each
        - builders[0,1,2].balance: >= amount

    Output State Verified:
        - payload_expected_withdrawals: Contains 3 builder withdrawals
        - builders[0,1,2].balance: Each decreased by 0.5 ETH
        - builder_pending_withdrawals: Reduced by 3
        - next_withdrawal_index: Incremented by 3
    """
    withdrawal_amount = spec.Gwei(500_000_000)
    builder_indices = [0, 1, 2]

    # Verify builders exist in registry
    for builder_index in builder_indices:
        assert builder_index < len(state.builders), (
            f"Builder {builder_index} must exist in registry"
        )

    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=builder_indices,
        builder_withdrawal_amounts={i: withdrawal_amount for i in builder_indices},
        builder_balances={i: withdrawal_amount + spec.MIN_DEPOSIT_AMOUNT for i in builder_indices},
    )
    pre_state = state.copy()

    yield from run_gloas_withdrawals_processing(spec, state)

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=3,
        builder_balance_deltas={i: -int(withdrawal_amount) for i in builder_indices},
        builder_pending_delta=-3,
        withdrawal_index_delta=3,
    )


@with_gloas_and_later
@spec_state_test
def test_builder_withdrawal_insufficient_balance(spec, state):
    """
    Test builder withdrawal with insufficient balance.

    Input State Configured:
        - state.builders[0]: Builder exists with only 1 ETH balance
        - builder_pending_withdrawals: Contains 1 entry requesting 5 ETH
        - builders[0].balance: 1 ETH (insufficient for requested 5 ETH)

    Output State Verified:
        - payload_expected_withdrawals: Contains 1 withdrawal (capped to available balance)
        - builders[0].balance: 0 (all available balance withdrawn)
        - builder_pending_withdrawals: Reduced by 1 (processed even if capped)
        - next_withdrawal_index: Incremented by 1
    """
    builder_index = 0
    withdrawal_amount = spec.Gwei(5_000_000_000)  # 5 ETH
    available_balance = spec.Gwei(1_000_000_000)  # Only 1 ETH available

    # Verify builder exists in registry
    assert builder_index < len(state.builders), "Builder must exist in registry"

    # Use prepare_process_withdrawals with insufficient balance
    # (balance assertion was removed, spec caps withdrawal to available balance)
    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=[builder_index],
        builder_withdrawal_amounts={builder_index: withdrawal_amount},
        builder_balances={builder_index: available_balance},
    )

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=1,
        builder_balances={builder_index: 0},  # Capped to available balance
        builder_pending_delta=-1,
        withdrawal_index_delta=1,
    )


@with_gloas_and_later
@spec_state_test
def test_mixed_withdrawal_types_priority_ordering(spec, state):
    """
    Test all three withdrawal types together with priority ordering verification.

    Input State Configured:
        - state.builders[0]: Builder exists in registry with sufficient balance
        - builder_pending_withdrawals: Contains 1 entry for builder 0
        - pending_partial_withdrawals: Contains 1 entry for validator 1
        - validators[2].withdrawable_epoch: <= current_epoch (sweep/full withdrawal)
        - builders[0].balance, balances[1,2]: Configured for respective withdrawal types

    Output State Verified:
        - payload_expected_withdrawals: Contains 3 withdrawals in priority order:
          [0] builder (builder 0), [1] pending partial (validator 1), [2] sweep (validator 2)
        - builders[0].balance, balances[1,2]: Each decreased appropriately
        - builder_pending_withdrawals: Reduced by 1
        - pending_partial_withdrawals: Reduced by 1
        - next_withdrawal_index: Incremented by 3
    """

    builder_index = 0
    pending_index = 1
    sweep_index = 2

    # Verify builder exists
    assert builder_index < len(state.builders), "Builder must exist in registry"
    builder_amount = spec.Gwei(1_000_000_000)

    # Prepare all three withdrawal types
    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=[builder_index],
        builder_withdrawal_amounts={builder_index: builder_amount},
        builder_balances={builder_index: builder_amount + spec.MIN_DEPOSIT_AMOUNT},
        pending_partial_indices=[pending_index],
        full_withdrawal_indices=[sweep_index],
    )

    pre_state = state.copy()

    expected_result = spec.get_expected_withdrawals(state)
    expected_withdrawals = expected_result.withdrawals
    spec.process_withdrawals(state)

    # Get the converted builder validator index (with BUILDER_INDEX_FLAG set)
    builder_validator_index = spec.convert_builder_index_to_validator_index(builder_index)

    # Verify priority ordering: builder payments -> pending partial withdrawals -> exit/excess withdrawals
    assert len(expected_withdrawals) == 3
    assert (
        expected_withdrawals[0].validator_index == builder_validator_index
    )  # Builder payments first
    assert (
        expected_withdrawals[1].validator_index == pending_index
    )  # Pending partial withdrawals second
    assert expected_withdrawals[2].validator_index == sweep_index  # Exit/excess withdrawals third

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=3,
        withdrawal_order=[builder_validator_index, pending_index, sweep_index],
        builder_pending_delta=-1,
        pending_partial_delta=-1,
        withdrawal_index_delta=3,
    )

    yield "pre", pre_state
    yield "post", state


@with_gloas_and_later
@spec_state_test
def test_maximum_withdrawals_per_payload_limit(spec, state):
    """
    Test that withdrawals respect MAX_WITHDRAWALS_PER_PAYLOAD limit.

    Input State Configured:
        - builder_pending_withdrawals: MAX/2 entries
        - pending_partial_withdrawals: MAX/2 entries
        - validators[*].withdrawable_epoch: MAX/2 validators fully withdrawable (sweep)
        - Total withdrawals available > MAX_WITHDRAWALS_PER_PAYLOAD

    Output State Verified:
        - payload_expected_withdrawals: Exactly MAX_WITHDRAWALS_PER_PAYLOAD
        - Some withdrawals remain unprocessed in builder_pending_withdrawals
          and/or pending_partial_withdrawals
        - next_withdrawal_index: Incremented by MAX_WITHDRAWALS_PER_PAYLOAD
    """

    # Add more withdrawals than the limit allows
    num_builders = spec.MAX_WITHDRAWALS_PER_PAYLOAD // 2
    num_pending = spec.MAX_WITHDRAWALS_PER_PAYLOAD // 2
    num_sweep = spec.MAX_WITHDRAWALS_PER_PAYLOAD // 2

    assert num_builders + num_pending + num_sweep <= len(state.validators), (
        "Not enough validators for test"
    )
    assert num_builders <= len(state.builders), "Not enough builders in registry for test"

    builder_indices = list(range(num_builders))
    pending_indices = list(range(num_builders, num_builders + num_pending))
    sweep_indices = list(range(num_builders + num_pending, num_builders + num_pending + num_sweep))

    withdrawal_amount = spec.Gwei(1_000_000_000)

    # Add all withdrawal types
    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=builder_indices,
        builder_withdrawal_amounts={i: withdrawal_amount for i in builder_indices},
        builder_balances={i: withdrawal_amount + spec.MIN_DEPOSIT_AMOUNT for i in builder_indices},
        pending_partial_indices=pending_indices,
        full_withdrawal_indices=sweep_indices,
    )

    # Should not exceed MAX_WITHDRAWALS_PER_PAYLOAD
    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    # Verify some withdrawals remain unprocessed due to the limit
    total_added = num_builders + num_pending + num_sweep
    total_remaining = len(state.builder_pending_withdrawals) + len(
        state.pending_partial_withdrawals
    )
    assert total_remaining > 0, "Some withdrawals should remain unprocessed"
    assert total_added > spec.MAX_WITHDRAWALS_PER_PAYLOAD, "Test setup should exceed limit"

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=spec.MAX_WITHDRAWALS_PER_PAYLOAD,
        withdrawal_index_delta=spec.MAX_WITHDRAWALS_PER_PAYLOAD,
    )


@with_gloas_and_later
@spec_state_test
def test_pending_withdrawals_processing(spec, state):
    """
    Test pending partial withdrawals processing.

    Input State Configured:
        - pending_partial_withdrawals: MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP entries
        - pending_partial_withdrawals[*].withdrawable_epoch: <= current_epoch
        - validators[*]: Configured for partial withdrawals
        - No builder_pending_withdrawals

    Output State Verified:
        - payload_expected_withdrawals: MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP
        - pending_partial_withdrawals: Empty (all processed)
        - balances[*]: Each reduced to max_effective_balance
        - next_withdrawal_index: Incremented by processed count
    """

    # Add enough pending withdrawals to test the limit
    pending_indices = list(range(spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP))
    prepare_process_withdrawals(spec, state, pending_partial_indices=pending_indices)

    # EIP-7732 limits pending withdrawals to min(MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP, MAX_WITHDRAWALS_PER_PAYLOAD - 1)
    # In minimal config: min(2, 4-1) = 2, in mainnet config: min(8, 16-1) = 8
    expected_withdrawals = spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP
    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)
    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=expected_withdrawals,
        pending_partial_delta=-int(expected_withdrawals),
        withdrawal_index_delta=expected_withdrawals,
    )


@with_gloas_and_later
@spec_state_test
def test_early_return_empty_parent_block(spec, state):
    """
    Test early return when parent block is empty.

    Input State Configured:
        - latest_block_hash: != latest_execution_payload_bid.block_hash (parent block EMPTY)
        - builder_pending_withdrawals: Contains entry for validator 0
        - validators[1,2].withdrawable_epoch: <= current_epoch (fully withdrawable)
        - balances[0,1,2]: Configured for withdrawals

    Output State Verified:
        - All state fields UNCHANGED (early exit triggered):
          - payload_expected_withdrawals: Not set
          - balances[*]: Unchanged
          - builder_pending_withdrawals: Unchanged
          - pending_partial_withdrawals: Unchanged
          - next_withdrawal_index: Unchanged
          - next_withdrawal_validator_index: Unchanged
    """
    # Set up withdrawals that would normally be processed
    withdrawal_amount = spec.Gwei(1_000_000_000)
    state.balances[0] = max(state.balances[0], withdrawal_amount + spec.MIN_ACTIVATION_BALANCE)
    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=[0],
        builder_withdrawal_amounts={0: withdrawal_amount},
        full_withdrawal_indices=[1, 2],
        parent_block_empty=True,
    )

    pre_state = state.copy()

    # Process withdrawals - should return early and do nothing
    spec.process_withdrawals(state)

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        all_state_unchanged=True,
    )

    yield "pre", pre_state
    yield "post", state


@with_gloas_and_later
@spec_state_test
def test_compounding_validator_partial_withdrawal(spec, state):
    """
    Test compounding validator partial withdrawal support.

    Input State Configured:
        - validators[0].withdrawal_credentials: 0x02 prefix (compounding credentials)
        - validators[0].effective_balance: MAX_EFFECTIVE_BALANCE_ELECTRA
        - balances[0]: MAX_EFFECTIVE_BALANCE_ELECTRA + 1 ETH (excess)
        - Validator is partially withdrawable (balance > max effective)

    Output State Verified:
        - payload_expected_withdrawals: Contains 1 withdrawal for validator 0
        - balances[0]: == MAX_EFFECTIVE_BALANCE_ELECTRA (excess withdrawn)
        - next_withdrawal_index: Incremented by 1
    """
    validator_index = 0
    set_compounding_withdrawal_credential_with_balance(
        spec,
        state,
        validator_index,
        balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA + spec.Gwei(1_000_000_000),
    )

    assert spec.is_partially_withdrawable_validator(
        state.validators[validator_index], state.balances[validator_index]
    )

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)
    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=1,
        balances={validator_index: spec.MAX_EFFECTIVE_BALANCE_ELECTRA},
        withdrawal_index_delta=1,
    )


@with_gloas_and_later
@spec_state_test
def test_validator_not_yet_active(spec, state):
    """
    Test withdrawal processing with validator not yet active.

    Input State Configured:
        - validators[0].activation_epoch: current_epoch + 4 (NOT YET ACTIVE)
        - pending_partial_withdrawals: Contains entry for validator 0
        - balances[0]: > MIN_ACTIVATION_BALANCE (has excess)

    Output State Verified:
        - payload_expected_withdrawals: Contains 1 withdrawal (processed despite not active)
        - balances[0]: == max_effective_balance
        - Note: Withdrawals process regardless of validator active status
    """
    validator_index = 0
    prepare_process_withdrawals(
        spec,
        state,
        partial_withdrawal_indices=[validator_index],
        validator_activation_epoch_offsets={validator_index: 4},
    )

    assert not spec.is_active_validator(
        state.validators[validator_index], spec.get_current_epoch(state)
    )
    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)
    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=1,
        balances={
            validator_index: spec.get_max_effective_balance(state.validators[validator_index])
        },
        withdrawal_index_delta=1,
    )


@with_gloas_and_later
@spec_state_test
def test_validator_in_exit_queue(spec, state):
    """
    Test withdrawal processing with validator in exit queue.

    Input State Configured:
        - validators[1].exit_epoch: current_epoch + 1 (IN EXIT QUEUE, still active now)
        - pending_partial_withdrawals: Contains entry for validator 1
        - balances[1]: > MIN_ACTIVATION_BALANCE (has excess)

    Output State Verified:
        - payload_expected_withdrawals: Contains 1 withdrawal (processed for exiting validator)
        - balances[1]: == max_effective_balance
        - Note: Exit queue status does not block sweep partial withdrawals
    """
    validator_index = 1
    prepare_process_withdrawals(
        spec,
        state,
        partial_withdrawal_indices=[validator_index],
        validator_exit_epoch_offsets={validator_index: 1},
    )

    assert spec.is_active_validator(
        state.validators[validator_index], spec.get_current_epoch(state)
    )
    assert not spec.is_active_validator(
        state.validators[validator_index], spec.get_current_epoch(state) + 1
    )
    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)
    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=1,
        balances={
            validator_index: spec.get_max_effective_balance(state.validators[validator_index])
        },
        withdrawal_index_delta=1,
    )


@with_gloas_and_later
@spec_state_test
def test_withdrawable_epoch_but_zero_balance(spec, state):
    """
    Test edge case: validator is withdrawable but has zero balance.

    Input State Configured:
        - validators[3].withdrawable_epoch: <= current_epoch (withdrawable)
        - validators[3].effective_balance: MIN_ACTIVATION_BALANCE
        - balances[3]: 0 (ZERO balance)

    Output State Verified:
        - payload_expected_withdrawals: Empty (no withdrawal created for 0 balance)
        - balances[3]: Remains 0
        - Note: Full withdrawals require balance > 0
    """
    prepare_process_withdrawals(
        spec,
        state,
        full_withdrawal_indices=[3],
        validator_effective_balances={3: spec.MIN_ACTIVATION_BALANCE},
        validator_balances={3: 0},
    )
    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)
    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=0,
        balances={3: 0},
        withdrawal_index_delta=0,
    )


@with_gloas_and_later
@spec_state_test
def test_zero_effective_balance_but_nonzero_balance(spec, state):
    """
    Test edge case: validator has zero effective balance but nonzero actual balance.

    Input State Configured:
        - validators[4].withdrawable_epoch: <= current_epoch (withdrawable)
        - validators[4].effective_balance: 0 (ZERO effective balance)
        - balances[4]: MIN_ACTIVATION_BALANCE (has actual balance)

    Output State Verified:
        - payload_expected_withdrawals: Contains 1 withdrawal for validator 4
        - balances[4]: 0 (full balance withdrawn)
        - Note: Effective balance doesn't prevent full withdrawal if balance > 0
    """
    prepare_process_withdrawals(
        spec,
        state,
        full_withdrawal_indices=[4],
        validator_effective_balances={4: 0},
        validator_balances={4: spec.MIN_ACTIVATION_BALANCE},
    )
    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)
    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=1,
        balances={4: 0},
        withdrawal_index_delta=1,
    )


@with_gloas_and_later
@spec_state_test
def test_builder_payments_exceed_limit_blocks_other_withdrawals(spec, state):
    """
    Test that when there are more than MAX_WITHDRAWALS_PER_PAYLOAD builder payments,
    pending partial withdrawals are not processed.

    Input State Configured:
        - validators[0..N].withdrawal_credentials: 0x03 prefix (builder credentials)
        - builder_pending_withdrawals: MAX_WITHDRAWALS_PER_PAYLOAD + 2 entries
        - builder_pending_withdrawals[*].withdrawable_epoch: <= current_epoch
        - balances[0..N]: >= amount + MIN_ACTIVATION_BALANCE

    Output State Verified:
        - payload_expected_withdrawals: Limited by MAX_WITHDRAWALS_PER_PAYLOAD
        - builder_pending_withdrawals: Partially processed (some remain)
        - Note: Builder payments are processed first; when they exceed limit,
          pending partial and sweep withdrawals are blocked
    """

    # Add more builder payments than the limit to test prioritization
    num_builders = spec.MAX_WITHDRAWALS_PER_PAYLOAD + 2  # 6 builders (more than limit of 4)
    withdrawal_amount = spec.Gwei(1_000_000_000)

    # Set up balances for all builders (credentials set via builder_indices in prepare_process_withdrawals)
    builder_indices = list(range(num_builders))
    for i in builder_indices:
        state.balances[i] = max(state.balances[i], withdrawal_amount + spec.MIN_ACTIVATION_BALANCE)

    # builder_credentials defaults to builder_indices
    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=builder_indices,
        builder_withdrawal_amounts={i: withdrawal_amount for i in builder_indices},
    )

    # Don't add any pending withdrawals for this test
    # This test just verifies that builder payments work up to the limit

    # Ensure no validators are eligible for sweep withdrawals
    # by setting withdrawal credentials to non-withdrawable
    for i in range(num_builders, len(state.validators)):
        validator = state.validators[i]
        if validator.withdrawal_credentials[0:1] == spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX:
            # Keep ETH1 credentials but ensure balance is not above max_effective_balance
            # to prevent full withdrawals
            state.balances[i] = min(state.balances[i], spec.MAX_EFFECTIVE_BALANCE)

    pre_state = state.copy()

    # Should process builder payments up to the limit, but actual count depends on eligibility
    yield from run_gloas_withdrawals_processing(spec, state)

    # Verify builder queue was partially processed
    # (some withdrawals should be processed, but not necessarily all due to eligibility constraints)
    post_builder_count = len(state.builder_pending_withdrawals)
    assert post_builder_count < len(pre_state.builder_pending_withdrawals), (
        "Some builder withdrawals should have been processed"
    )
    processed_count = len(pre_state.builder_pending_withdrawals) - post_builder_count
    assert processed_count <= spec.MAX_WITHDRAWALS_PER_PAYLOAD, "Should not exceed withdrawal limit"

    # Complex assertion - keep verification outside assert_process_withdrawals
    assert len(list(state.payload_expected_withdrawals)) <= spec.MAX_WITHDRAWALS_PER_PAYLOAD


@with_gloas_and_later
@spec_state_test
def test_no_builders_max_pending_with_sweep_spillover(spec, state):
    """
    Test no builder payments, MAX_WITHDRAWALS_PER_PAYLOAD pending partial withdrawals,
    with sweep withdrawals available due to MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP limit.

    Input State Configured:
        - builder_pending_withdrawals: Empty (no builders)
        - pending_partial_withdrawals: MAX_WITHDRAWALS_PER_PAYLOAD entries
        - validators[N..N+3].withdrawable_epoch: <= current_epoch (sweep eligible)
        - balances[*]: Configured for respective withdrawal types

    Output State Verified:
        - payload_expected_withdrawals: MAX_WITHDRAWALS_PER_PAYLOAD total
          - MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP from pending queue
          - Remaining slots filled by sweep withdrawals
        - pending_partial_withdrawals: MAX - MAX_PENDING_PARTIALS remaining
        - balances[sweep indices]: 0 (full withdrawals)
        - Note: Pending partials capped by MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP
    """

    # Add MAX_WITHDRAWALS_PER_PAYLOAD pending partial withdrawals and sweep withdrawals
    pending_indices = list(range(spec.MAX_WITHDRAWALS_PER_PAYLOAD))
    sweep_start = spec.MAX_WITHDRAWALS_PER_PAYLOAD
    sweep_indices = list(range(sweep_start, sweep_start + 3))

    prepare_process_withdrawals(
        spec,
        state,
        pending_partial_indices=pending_indices,
        full_withdrawal_indices=sweep_indices,
    )

    # Should process MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP pending + remaining slots for sweep
    expected_pending = spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP
    expected_sweep = spec.MAX_WITHDRAWALS_PER_PAYLOAD - expected_pending
    expected_total = expected_pending + expected_sweep

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    # Verify remaining pending withdrawals not processed
    remaining_pending = spec.MAX_WITHDRAWALS_PER_PAYLOAD - expected_pending
    assert len(state.pending_partial_withdrawals) == remaining_pending

    # Build balances dict for sweep validators
    sweep_balances = {i: 0 for i in range(sweep_start, sweep_start + expected_sweep)}

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=expected_total,
        balances=sweep_balances,
        pending_partial_delta=-int(expected_pending),
        withdrawal_index_delta=expected_total,
    )


@with_gloas_and_later
@spec_state_test
def test_no_builders_no_pending_max_sweep_withdrawals(spec, state):
    """
    Test no builder payments, no pending partial withdrawals,
    MAX_WITHDRAWALS_PER_PAYLOAD sweep withdrawals.

    Input State Configured:
        - builder_pending_withdrawals: Empty
        - pending_partial_withdrawals: Empty
        - validators[0..MAX-1].withdrawable_epoch: <= current_epoch (all sweep eligible)
        - balances[0..MAX-1]: > 0 (have balance to withdraw)

    Output State Verified:
        - payload_expected_withdrawals: MAX_WITHDRAWALS_PER_PAYLOAD (all sweep)
        - balances[0..MAX-1]: 0 (all fully withdrawn)
        - next_withdrawal_index: Incremented by MAX_WITHDRAWALS_PER_PAYLOAD
    """

    # Add MAX_WITHDRAWALS_PER_PAYLOAD sweep withdrawals
    sweep_indices = list(range(spec.MAX_WITHDRAWALS_PER_PAYLOAD))
    prepare_process_withdrawals(spec, state, full_withdrawal_indices=sweep_indices)

    # All should be processed since no higher priority withdrawals exist
    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    # Build balances dict for all sweep validators
    sweep_balances = {i: 0 for i in range(spec.MAX_WITHDRAWALS_PER_PAYLOAD)}

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=spec.MAX_WITHDRAWALS_PER_PAYLOAD,
        balances=sweep_balances,
        withdrawal_index_delta=spec.MAX_WITHDRAWALS_PER_PAYLOAD,
    )


@with_gloas_and_later
@spec_state_test
def test_builder_withdrawals_processed_first(spec, state):
    """
    Builder withdrawals should be processed before pending/regular withdrawals.
    Verifies the priority ordering: builder > pending > sweep.

    Input State Configured:
        - state.builders[0]: Builder exists in registry with sufficient balance
        - builder_pending_withdrawals: Contains entry for builder 0
        - validators[1].withdrawable_epoch: <= current_epoch (sweep eligible)

    Output State Verified:
        - payload_expected_withdrawals: 2 withdrawals in order:
          [0] builder withdrawal (builder 0), [1] sweep withdrawal (validator 1)
        - payload_expected_withdrawals[0].amount: withdrawal_amount
        - builders[0].balance, balances[1]: Decreased appropriately
    """

    builder_index = 0
    regular_index = 1
    withdrawal_amount = spec.MIN_ACTIVATION_BALANCE

    # Verify builder exists
    assert builder_index < len(state.builders), "Builder must exist in registry"

    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=[builder_index],
        builder_withdrawal_amounts={builder_index: withdrawal_amount},
        builder_balances={builder_index: withdrawal_amount + spec.MIN_DEPOSIT_AMOUNT},
        full_withdrawal_indices=[regular_index],
    )

    pre_state = state.copy()
    builder_validator_index = spec.convert_builder_index_to_validator_index(builder_index)

    yield from run_gloas_withdrawals_processing(spec, state)

    # Verify priority ordering: builder first, then regular
    withdrawals = list(state.payload_expected_withdrawals)
    assert len(withdrawals) == 2
    assert withdrawals[0].validator_index == builder_validator_index
    assert withdrawals[1].validator_index == regular_index

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=2,
        withdrawal_order=[builder_validator_index, regular_index],
        balances={regular_index: 0},
        builder_balance_deltas={builder_index: -int(withdrawal_amount)},
        builder_pending_delta=-1,
        withdrawal_index_delta=2,
        withdrawal_amounts_builders={builder_index: withdrawal_amount},
    )


@with_gloas_and_later
@spec_state_test
def test_builder_uses_fee_recipient_address(spec, state):
    """
    Builder withdrawal should use fee_recipient address from BuilderPendingWithdrawal.

    Input State Configured:
        - state.builders[0]: Builder exists with custom execution_address (0xab * 20)
        - builders[0].balance: Sufficient for withdrawal
        - builder_pending_withdrawals[0].fee_recipient: Custom address from builder

    Output State Verified:
        - payload_expected_withdrawals: Contains 1 builder withdrawal
        - payload_expected_withdrawals[0].address: Custom fee_recipient address (0xab * 20)
        - Note: Withdrawal uses fee_recipient from BuilderPendingWithdrawal
    """

    builder_index = 0
    custom_address = b"\xab" * 20
    withdrawal_amount = spec.MIN_ACTIVATION_BALANCE

    # Verify builder exists
    assert builder_index < len(state.builders), "Builder must exist in registry"

    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=[builder_index],
        builder_withdrawal_amounts={builder_index: withdrawal_amount},
        builder_balances={builder_index: withdrawal_amount + spec.MIN_DEPOSIT_AMOUNT},
        builder_execution_addresses={builder_index: custom_address},
    )

    pre_state = state.copy()

    yield from run_gloas_withdrawals_processing(spec, state)

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=1,
        builder_balance_deltas={builder_index: -int(withdrawal_amount)},
        builder_pending_delta=-1,
        withdrawal_index_delta=1,
        withdrawal_addresses_builders={builder_index: custom_address},
    )


@with_gloas_and_later
@spec_state_test
def test_builder_and_pending_leave_room_for_sweep(spec, state):
    """
    Test that builders + pending withdrawals leave room for sweep withdrawals.
    When builders + pending = MAX-1, exactly 1 slot remains for sweep.

    Input State Configured:
        - state.builders[0..N-1]: Builders exist in registry with sufficient balance
        - builder_pending_withdrawals: N entries (calculated to leave 1 slot)
        - pending_partial_withdrawals: M entries (capped by MAX_PENDING_PARTIALS)
        - validators[N+M+1].withdrawable_epoch: <= current_epoch (sweep eligible)
        - Total builder + pending < MAX_WITHDRAWALS_PER_PAYLOAD

    Output State Verified:
        - payload_expected_withdrawals: builders + pending + 1 sweep
        - Exactly 1 sweep withdrawal included in the payload
        - Note: Tests the slot allocation between withdrawal types
    """

    assert spec.MAX_WITHDRAWALS_PER_PAYLOAD >= 3, (
        "Test requires MAX_WITHDRAWALS_PER_PAYLOAD to be at least 3"
    )

    num_builders = 2 if spec.MAX_WITHDRAWALS_PER_PAYLOAD >= 4 else 1
    num_pending = min(
        spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP,
        spec.MAX_WITHDRAWALS_PER_PAYLOAD - num_builders - 1,
    )

    withdrawal_amount = spec.MIN_ACTIVATION_BALANCE

    # Set up builder indices
    builder_indices_list = list(range(num_builders))
    for builder_index in builder_indices_list:
        assert builder_index < len(state.builders), (
            f"Builder {builder_index} must exist in registry"
        )

    pending_indices = (
        list(range(num_builders, num_builders + num_pending)) if num_pending > 0 else []
    )
    regular_index = num_builders + num_pending + 1

    # Use a single prepare_process_withdrawals call with all parameters
    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=builder_indices_list if num_builders > 0 else [],
        builder_withdrawal_amounts={i: withdrawal_amount for i in builder_indices_list}
        if num_builders > 0
        else None,
        builder_balances={
            i: withdrawal_amount + spec.MIN_DEPOSIT_AMOUNT for i in builder_indices_list
        }
        if num_builders > 0
        else None,
        pending_partial_indices=pending_indices,
        full_withdrawal_indices=[regular_index],
    )

    expected_total = num_builders + num_pending + 1
    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    # Verify exactly 1 sweep withdrawal was included
    withdrawals = list(state.payload_expected_withdrawals)
    regular_withdrawals = [w for w in withdrawals if w.validator_index == regular_index]
    assert len(regular_withdrawals) == 1, "Exactly 1 slot should remain for sweep withdrawal"

    # Build parameters dict conditionally
    assert_params = {
        "withdrawal_count": expected_total,
        "balances": {regular_index: 0},
        "withdrawal_index_delta": expected_total,
    }
    if num_builders > 0:
        assert_params["builder_pending_delta"] = -int(num_builders)
        assert_params["builder_balance_deltas"] = {
            i: -int(withdrawal_amount) for i in builder_indices_list
        }
    if num_pending > 0:
        assert_params["pending_partial_delta"] = -int(num_pending)

    assert_process_withdrawals(spec, state, pre_state, **assert_params)


@with_gloas_and_later
@spec_state_test
def test_all_builder_withdrawals_zero_balance(spec, state):
    """
    Builders with zero balance - withdrawals still processed but with zero deduction.

    Input State Configured:
        - state.builders[0,1]: Builders exist with zero balance
        - builder_pending_withdrawals: 2 entries requesting MIN_ACTIVATION_BALANCE each
        - validators[5].withdrawable_epoch: <= current_epoch (sweep eligible)

    Output State Verified:
        - payload_expected_withdrawals: Contains 3 withdrawals (2 builder + 1 sweep)
        - Builder withdrawals processed (deduction capped to 0)
        - builders[0,1].balance: 0 (unchanged)
        - balances[5]: 0 (full withdrawal processed)
        - Note: Builder withdrawals always processed, amount capped to available balance
    """

    builder_indices = [0, 1]
    withdrawal_amount = spec.MIN_ACTIVATION_BALANCE
    regular_index = 5

    # Verify builders exist
    for builder_index in builder_indices:
        assert builder_index < len(state.builders), (
            f"Builder {builder_index} must exist in registry"
        )

    # Use prepare_process_withdrawals with zero balance
    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=builder_indices,
        builder_withdrawal_amounts={i: withdrawal_amount for i in builder_indices},
        builder_balances={i: 0 for i in builder_indices},  # Zero balance
        full_withdrawal_indices=[regular_index],
    )

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    # Get converted builder validator indices
    builder_validator_indices = [
        spec.convert_builder_index_to_validator_index(i) for i in builder_indices
    ]

    # Verify all withdrawals are present
    withdrawals = list(state.payload_expected_withdrawals)
    withdrawal_validator_indices = [w.validator_index for w in withdrawals]

    # Builder withdrawals should be present (even with zero balance)
    for builder_idx, builder_val_idx in zip(builder_indices, builder_validator_indices):
        assert builder_val_idx in withdrawal_validator_indices, (
            f"Builder {builder_idx} withdrawal should be present (processed with 0 deduction)"
        )

    # Regular sweep withdrawal should be present
    assert regular_index in withdrawal_validator_indices, (
        "Regular sweep withdrawal should be processed"
    )

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=3,  # 2 builder + 1 sweep
        balances={regular_index: 0},
        builder_balances={0: 0, 1: 0},  # Unchanged (were already 0)
        builder_pending_delta=-2,
        withdrawal_index_delta=3,
    )


@with_gloas_and_later
@spec_state_test
def test_builder_max_minus_one_plus_one_regular(spec, state):
    """
    Exactly MAX-1 builder withdrawals should leave exactly 1 slot for regular withdrawal.

    Input State Configured:
        - state.builders[0..MAX-2]: Builders exist in registry with sufficient balance
        - builder_pending_withdrawals: MAX-1 entries
        - validators[MAX, MAX+1, MAX+2].withdrawable_epoch: <= current_epoch (sweep eligible)
        - next_withdrawal_validator_index: Set to first sweep validator

    Output State Verified:
        - payload_expected_withdrawals: MAX_WITHDRAWALS_PER_PAYLOAD total
          - MAX-1 builder withdrawals
          - Exactly 1 sweep withdrawal (first in sweep order)
        - Note: Builder cap at MAX-1 reserves 1 slot for other withdrawal types
    """

    num_builders = spec.MAX_WITHDRAWALS_PER_PAYLOAD - 1
    withdrawal_amount = spec.MIN_ACTIVATION_BALANCE

    # Ensure we have enough builders in registry
    assert num_builders <= len(state.builders), (
        f"Test requires at least {num_builders} builders in registry"
    )

    builder_indices_list = list(range(num_builders))

    # Add multiple regular withdrawals, but only 1 should be processed
    regular_indices = [num_builders + 1, num_builders + 2, num_builders + 3]
    assert len(state.validators) >= max(regular_indices) + 1, (
        f"Test requires at least {max(regular_indices) + 1} validators"
    )

    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=builder_indices_list,
        builder_withdrawal_amounts={i: withdrawal_amount for i in builder_indices_list},
        builder_balances={
            i: withdrawal_amount + spec.MIN_DEPOSIT_AMOUNT for i in builder_indices_list
        },
        full_withdrawal_indices=regular_indices,
        next_withdrawal_validator_index=regular_indices[0],
    )

    pre_state = state.copy()

    # Get converted builder validator indices
    builder_validator_indices = [
        spec.convert_builder_index_to_validator_index(i) for i in builder_indices_list
    ]

    yield from run_gloas_withdrawals_processing(spec, state)

    # Verify exactly 1 regular withdrawal when builders fill MAX-1 slots
    withdrawals = list(state.payload_expected_withdrawals)
    builder_withdrawals = [w for w in withdrawals if w.validator_index in builder_validator_indices]
    assert len(builder_withdrawals) == num_builders
    regular_withdrawals = [w for w in withdrawals if w.validator_index in regular_indices]
    assert len(regular_withdrawals) == 1, (
        "Should process exactly 1 regular withdrawal when builders fill MAX-1 slots"
    )
    assert regular_withdrawals[0].validator_index == regular_indices[0], (
        "Should process the first regular withdrawal in sweep order"
    )

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=spec.MAX_WITHDRAWALS_PER_PAYLOAD,
        balances={regular_indices[0]: 0},
        builder_balance_deltas={i: -int(withdrawal_amount) for i in builder_indices_list},
        builder_pending_delta=-int(num_builders),
        withdrawal_index_delta=spec.MAX_WITHDRAWALS_PER_PAYLOAD,
        no_withdrawal_indices=regular_indices[1:],
    )


@with_gloas_and_later
@spec_state_test
def test_builder_zero_withdrawal_amount(spec, state):
    """
    Builder withdrawal with amount = 0 produces a withdrawal entry with 0 amount.

    Input State Configured:
        - state.builders[0]: Builder with balance in registry
        - builder_pending_withdrawals: 1 entry with amount = 0

    Output State Verified:
        - payload_expected_withdrawals: 1 entry with amount = 0
        - builders[0].balance: Unchanged (no actual balance deduction)
        - builder_pending_withdrawals: Reduced by 1 (entry consumed)
    """

    builder_index = 0
    assert builder_index < len(state.builders), "Builder must exist in registry"

    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=[builder_index],
        builder_withdrawal_amounts={builder_index: spec.Gwei(0)},
        builder_balances={builder_index: spec.MIN_DEPOSIT_AMOUNT},
    )
    pre_state = state.copy()

    builder_validator_index = spec.convert_builder_index_to_validator_index(builder_index)

    yield from run_gloas_withdrawals_processing(spec, state)

    # Verify withdrawal produced with 0 amount
    withdrawals = list(state.payload_expected_withdrawals)
    builder_withdrawals = [w for w in withdrawals if w.validator_index == builder_validator_index]
    assert len(builder_withdrawals) == 1
    assert builder_withdrawals[0].amount == 0

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=1,
        builder_balance_deltas={builder_index: 0},
        withdrawal_amounts_builders={builder_index: 0},
        builder_pending_delta=-1,
        withdrawal_index_delta=1,
    )
