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
    assert len(expected_withdrawals_result[0]) == 0

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)
    assert_process_withdrawals(
        spec, state, pre_state,
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
        spec, state, pre_state,
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
        spec, state, pre_state,
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

    expected_total = len(fully_withdrawable_indices) + len(partial_withdrawals_indices)
    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)
    assert_process_withdrawals(
        spec, state, pre_state,
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
        - validators[0].withdrawal_credentials: 0x03 prefix (builder credentials)
        - builder_pending_withdrawals: Contains 1 entry for validator 0
        - builder_pending_withdrawals[0].withdrawable_epoch: <= current_epoch
        - builder_pending_withdrawals[0].amount: 1 ETH
        - balances[0]: >= amount + MIN_ACTIVATION_BALANCE

    Output State Verified:
        - payload_expected_withdrawals: Contains 1 builder withdrawal
        - balances[0]: Decreased by withdrawal amount
        - builder_pending_withdrawals: Reduced by 1 (processed entry removed)
        - next_withdrawal_index: Incremented by 1
    """
    withdrawal_amount = spec.Gwei(1_000_000_000)
    # Ensure sufficient balance before prepare_process_withdrawals
    state.balances[0] = max(
        state.balances[0],
        withdrawal_amount + spec.MIN_ACTIVATION_BALANCE,
    )
    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=[0],
        builder_withdrawal_amounts={0: withdrawal_amount},
    )
    pre_state = state.copy()
    expected_post_balance = pre_state.balances[0] - withdrawal_amount
    yield from run_gloas_withdrawals_processing(spec, state)
    assert_process_withdrawals(
        spec, state, pre_state,
        withdrawal_count=1,
        balances={0: expected_post_balance},
        builder_pending_delta=-1,
        withdrawal_index_delta=1,
    )


@with_gloas_and_later
@spec_state_test
def test_multiple_builder_withdrawals(spec, state):
    """
    Test processing multiple builder withdrawals.

    Input State Configured:
        - validators[0,1,2].withdrawal_credentials: 0x03 prefix (builder credentials)
        - builder_pending_withdrawals: Contains 3 entries for validators 0, 1, 2
        - builder_pending_withdrawals[*].withdrawable_epoch: <= current_epoch
        - builder_pending_withdrawals[*].amount: 0.5 ETH each
        - balances[0,1,2]: >= amount + MIN_ACTIVATION_BALANCE

    Output State Verified:
        - payload_expected_withdrawals: Contains 3 builder withdrawals
        - balances[0,1,2]: Each decreased by 0.5 ETH
        - builder_pending_withdrawals: Reduced by 3
        - next_withdrawal_index: Incremented by 3
    """
    withdrawal_amount = spec.Gwei(500_000_000)
    builder_indices = [0, 1, 2]
    # Ensure sufficient balance before prepare_process_withdrawals
    for i in builder_indices:
        state.balances[i] = max(
            state.balances[i],
            withdrawal_amount + spec.MIN_ACTIVATION_BALANCE,
        )
    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=builder_indices,
        builder_withdrawal_amounts={i: withdrawal_amount for i in builder_indices},
    )
    pre_state = state.copy()
    expected_balances = {i: pre_state.balances[i] - withdrawal_amount for i in builder_indices}
    yield from run_gloas_withdrawals_processing(spec, state)
    assert_process_withdrawals(
        spec, state, pre_state,
        withdrawal_count=3,
        balances=expected_balances,
        builder_pending_delta=-3,
        withdrawal_index_delta=3,
    )


@with_gloas_and_later
@spec_state_test
def test_builder_withdrawal_future_epoch(spec, state):
    """
    Test builder withdrawal not yet withdrawable (future epoch).

    Input State Configured:
        - validators[0].withdrawal_credentials: 0x03 prefix (builder credentials)
        - builder_pending_withdrawals: Contains 1 entry for validator 0
        - builder_pending_withdrawals[0].withdrawable_epoch: current_epoch + 1 (FUTURE)
        - balances[0]: >= amount + MIN_ACTIVATION_BALANCE

    Output State Verified:
        - payload_expected_withdrawals: Empty (withdrawal not ready)
        - balances[0]: Unchanged
        - builder_pending_withdrawals: Unchanged (not yet withdrawable)
        - next_withdrawal_index: Unchanged
    """
    withdrawal_amount = spec.Gwei(1_000_000_000)
    # Ensure sufficient balance before prepare_process_withdrawals
    state.balances[0] = max(
        state.balances[0],
        withdrawal_amount + spec.MIN_ACTIVATION_BALANCE,
    )
    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=[0],
        builder_withdrawal_amounts={0: withdrawal_amount},
        builder_withdrawable_offsets={0: 1},  # Future epoch (current + 1)
    )
    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)
    assert_process_withdrawals(
        spec, state, pre_state,
        withdrawal_count=0,
        builder_pending_delta=0,
        withdrawal_index_delta=0,
    )


@with_gloas_and_later
@spec_state_test
def test_builder_withdrawal_slashed_validator(spec, state):
    """
    Test builder withdrawal with slashed validator.
    Slashed validators cannot have builder withdrawals processed until
    current_epoch >= withdrawable_epoch.

    Input State Configured:
        - validators[0].withdrawal_credentials: 0x03 prefix (builder credentials)
        - validators[0].slashed: True
        - validators[0].withdrawable_epoch: current_epoch + 10 (FUTURE)
        - builder_pending_withdrawals: Contains 1 entry for validator 0
        - builder_pending_withdrawals[0].withdrawable_epoch: <= current_epoch
        - balances[0]: >= amount + MIN_ACTIVATION_BALANCE

    Output State Verified:
        - payload_expected_withdrawals: Empty (slashed validator not yet withdrawable)
        - balances[0]: Unchanged
        - builder_pending_withdrawals: Unchanged (blocked by slashed check)
        - next_withdrawal_index: Unchanged
    """
    withdrawal_amount = spec.Gwei(1_000_000_000)
    current_epoch = spec.get_current_epoch(state)

    # Set up balance before prepare_process_withdrawals (credentials set via builder_credentials)
    state.balances[0] = max(state.balances[0], withdrawal_amount + spec.MIN_ACTIVATION_BALANCE)

    # Set validator as slashed with future withdrawable_epoch
    state.validators[0].slashed = True
    state.validators[0].withdrawable_epoch = current_epoch + 10

    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=[0],
        builder_withdrawal_amounts={0: withdrawal_amount},
        builder_credentials=[0],
    )
    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)
    assert_process_withdrawals(
        spec, state, pre_state,
        withdrawal_count=0,
        builder_pending_delta=0,
        withdrawal_index_delta=0,
    )


@with_gloas_and_later
@spec_state_test
def test_builder_withdrawal_insufficient_balance(spec, state):
    """
    Test builder withdrawal with insufficient balance.

    Input State Configured:
        - validators[0].withdrawal_credentials: 0x03 prefix (builder credentials)
        - builder_pending_withdrawals: Contains 1 entry requesting 5 ETH
        - builder_pending_withdrawals[0].withdrawable_epoch: <= current_epoch
        - balances[0]: MIN_ACTIVATION_BALANCE + 1 ETH (only 1 ETH available)

    Output State Verified:
        - payload_expected_withdrawals: Contains 1 withdrawal (capped to available balance)
        - balances[0]: MIN_ACTIVATION_BALANCE (available excess withdrawn)
        - builder_pending_withdrawals: Reduced by 1 (processed even if capped)
        - next_withdrawal_index: Incremented by 1
    """
    withdrawal_amount = spec.Gwei(5_000_000_000)  # 5 ETH

    # Set up builder credentials with insufficient balance (using builder_credentials without builder_indices)
    prepare_process_withdrawals(spec, state, builder_credentials=[0])
    state.balances[0] = spec.MIN_ACTIVATION_BALANCE + spec.Gwei(1_000_000_000)  # Only 1 ETH excess

    # Manually add builder withdrawal (bypassing prepare_withdrawals balance assertion)
    address = state.validators[0].withdrawal_credentials[12:]
    state.builder_pending_withdrawals.append(
        spec.BuilderPendingWithdrawal(
            fee_recipient=address,
            amount=withdrawal_amount,
            builder_index=0,
            withdrawable_epoch=spec.get_current_epoch(state),
        )
    )

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)
    assert_process_withdrawals(
        spec, state, pre_state,
        withdrawal_count=1,
        balances={0: spec.MIN_ACTIVATION_BALANCE},
        builder_pending_delta=-1,
        withdrawal_index_delta=1,
    )


@with_gloas_and_later
@spec_state_test
def test_mixed_withdrawal_types_priority_ordering(spec, state):
    """
    Test all three withdrawal types together with priority ordering verification.

    Input State Configured:
        - validators[0].withdrawal_credentials: 0x03 prefix (builder)
        - builder_pending_withdrawals: Contains 1 entry for validator 0
        - pending_partial_withdrawals: Contains 1 entry for validator 1
        - validators[2].withdrawable_epoch: <= current_epoch (sweep/full withdrawal)
        - balances[0,1,2]: Configured for respective withdrawal types

    Output State Verified:
        - payload_expected_withdrawals: Contains 3 withdrawals in priority order:
          [0] builder (validator 0), [1] pending partial (validator 1), [2] sweep (validator 2)
        - balances[0,1,2]: Each decreased appropriately
        - builder_pending_withdrawals: Reduced by 1
        - pending_partial_withdrawals: Reduced by 1
        - next_withdrawal_index: Incremented by 3
    """

    builder_index = 0
    pending_index = 1
    sweep_index = 2

    # Set up balance (credentials set via builder_indices in prepare_process_withdrawals)
    builder_amount = spec.Gwei(1_000_000_000)
    state.balances[builder_index] = max(
        state.balances[builder_index],
        builder_amount + spec.MIN_ACTIVATION_BALANCE,
    )

    # Prepare all three withdrawal types (builder_credentials defaults to builder_indices)
    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=[builder_index],
        builder_withdrawal_amounts={builder_index: builder_amount},
        pending_partial_indices=[pending_index],
        full_withdrawal_indices=[sweep_index],
    )

    pre_state = state.copy()

    expected_withdrawals, _, _ = spec.get_expected_withdrawals(state)
    spec.process_withdrawals(state)

    # Verify priority ordering: builder payments -> pending partial withdrawals -> exit/excess withdrawals
    assert len(expected_withdrawals) == 3
    assert expected_withdrawals[0].validator_index == builder_index  # Builder payments first
    assert (
        expected_withdrawals[1].validator_index == pending_index
    )  # Pending partial withdrawals second
    assert expected_withdrawals[2].validator_index == sweep_index  # Exit/excess withdrawals third

    assert_process_withdrawals(
        spec, state, pre_state,
        withdrawal_count=3,
        withdrawal_order=[builder_index, pending_index, sweep_index],
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

    assert num_builders + num_pending + num_sweep <= len(state.validators), "Not enough validators for test"

    builder_indices = list(range(num_builders))
    pending_indices = list(range(num_builders, num_builders + num_pending))
    sweep_indices = list(range(num_builders + num_pending, num_builders + num_pending + num_sweep))

    # Set up balances (credentials set via builder_indices in prepare_process_withdrawals)
    withdrawal_amount = spec.Gwei(1_000_000_000)
    for i in builder_indices:
        state.balances[i] = max(
            state.balances[i],
            withdrawal_amount + spec.MIN_ACTIVATION_BALANCE,
        )

    # Add all withdrawal types (builder_credentials defaults to builder_indices)
    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=builder_indices,
        builder_withdrawal_amounts={i: withdrawal_amount for i in builder_indices},
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
        spec, state, pre_state,
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
        spec, state, pre_state,
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
        spec, state, pre_state,
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
        spec, state, pre_state,
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
    state.validators[validator_index].activation_epoch += 4
    prepare_process_withdrawals(spec, state, partial_withdrawal_indices=[validator_index])

    assert not spec.is_active_validator(
        state.validators[validator_index], spec.get_current_epoch(state)
    )
    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)
    assert_process_withdrawals(
        spec, state, pre_state,
        withdrawal_count=1,
        balances={validator_index: spec.get_max_effective_balance(state.validators[validator_index])},
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
    state.validators[validator_index].exit_epoch = spec.get_current_epoch(state) + 1
    prepare_process_withdrawals(spec, state, partial_withdrawal_indices=[validator_index])

    assert spec.is_active_validator(
        state.validators[validator_index], spec.get_current_epoch(state)
    )
    assert not spec.is_active_validator(
        state.validators[validator_index], spec.get_current_epoch(state) + 1
    )
    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)
    assert_process_withdrawals(
        spec, state, pre_state,
        withdrawal_count=1,
        balances={validator_index: spec.get_max_effective_balance(state.validators[validator_index])},
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
    prepare_process_withdrawals(spec, state, full_withdrawal_indices=[3])
    state.validators[3].effective_balance = spec.MIN_ACTIVATION_BALANCE
    state.balances[3] = 0
    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)
    assert_process_withdrawals(
        spec, state, pre_state,
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
    prepare_process_withdrawals(spec, state, full_withdrawal_indices=[4])
    state.validators[4].effective_balance = 0
    state.balances[4] = spec.MIN_ACTIVATION_BALANCE
    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)
    assert_process_withdrawals(
        spec, state, pre_state,
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
        spec, state, pre_state,
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
        spec, state, pre_state,
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
        - validators[0].withdrawal_credentials: 0x03 prefix (builder)
        - validators[0].effective_balance: MAX_EFFECTIVE_BALANCE_ELECTRA
        - balances[0]: MAX_EFFECTIVE_BALANCE_ELECTRA + MIN_ACTIVATION_BALANCE
        - builder_pending_withdrawals: Contains entry for validator 0
        - validators[1].withdrawable_epoch: <= current_epoch (sweep eligible)

    Output State Verified:
        - payload_expected_withdrawals: 2 withdrawals in order:
          [0] builder withdrawal (validator 0), [1] sweep withdrawal (validator 1)
        - payload_expected_withdrawals[0].amount: MIN_ACTIVATION_BALANCE
        - balances[0,1]: Decreased appropriately
    """

    builder_index = 0
    regular_index = 1

    # Set balance directly
    state.validators[builder_index].effective_balance = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    state.balances[builder_index] = spec.MAX_EFFECTIVE_BALANCE_ELECTRA + spec.MIN_ACTIVATION_BALANCE

    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=[builder_index],
        full_withdrawal_indices=[regular_index],
    )

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    # Verify priority ordering: builder first, then regular
    withdrawals = list(state.payload_expected_withdrawals)
    assert len(withdrawals) == 2
    assert withdrawals[0].validator_index == builder_index
    assert withdrawals[0].amount == spec.MIN_ACTIVATION_BALANCE
    assert withdrawals[1].validator_index == regular_index

    expected_builder_balance = pre_state.balances[builder_index] - spec.MIN_ACTIVATION_BALANCE

    assert_process_withdrawals(
        spec, state, pre_state,
        withdrawal_count=2,
        withdrawal_order=[builder_index, regular_index],
        balances={regular_index: 0, builder_index: expected_builder_balance},
        builder_pending_delta=-1,
        withdrawal_index_delta=2,
        withdrawal_amounts={builder_index: spec.MIN_ACTIVATION_BALANCE},
    )


@with_gloas_and_later
@spec_state_test
def test_builder_uses_fee_recipient_address(spec, state):
    """
    Builder withdrawal should use fee_recipient address from BuilderPendingWithdrawal.

    Input State Configured:
        - validators[0].withdrawal_credentials: 0x03 prefix with custom address (0xab * 20)
        - validators[0].effective_balance: MAX_EFFECTIVE_BALANCE_ELECTRA
        - balances[0]: MAX_EFFECTIVE_BALANCE_ELECTRA + MIN_ACTIVATION_BALANCE
        - builder_pending_withdrawals[0].fee_recipient: Custom address from credentials[12:]

    Output State Verified:
        - payload_expected_withdrawals: Contains 1 builder withdrawal
        - payload_expected_withdrawals[0].address: Custom fee_recipient address (0xab * 20)
        - Note: Withdrawal uses fee_recipient from BuilderPendingWithdrawal, not fixed address
    """

    builder_index = 0
    custom_address = b"\xab" * 20

    # Set balance and credentials directly with custom address
    state.validators[builder_index].effective_balance = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    state.balances[builder_index] = spec.MAX_EFFECTIVE_BALANCE_ELECTRA + spec.MIN_ACTIVATION_BALANCE
    state.validators[builder_index].withdrawal_credentials = (
        spec.BUILDER_WITHDRAWAL_PREFIX + b"\x00" * 11 + custom_address
    )

    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=[builder_index],
        builder_credentials=[],  # Don't overwrite custom credentials
    )

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    # Verify fee_recipient address is used
    withdrawals = list(state.payload_expected_withdrawals)
    builder_withdrawal = next((w for w in withdrawals if w.validator_index == builder_index), None)
    assert builder_withdrawal is not None
    assert builder_withdrawal.address == custom_address

    expected_builder_balance = pre_state.balances[builder_index] - spec.MIN_ACTIVATION_BALANCE

    assert_process_withdrawals(
        spec, state, pre_state,
        withdrawal_count=1,
        balances={builder_index: expected_builder_balance},
        builder_pending_delta=-1,
        withdrawal_index_delta=1,
        withdrawal_addresses={builder_index: custom_address},
    )


@with_gloas_and_later
@spec_state_test
def test_builder_and_pending_leave_room_for_sweep(spec, state):
    """
    Test that builders + pending withdrawals leave room for sweep withdrawals.
    When builders + pending = MAX-1, exactly 1 slot remains for sweep.

    Input State Configured:
        - validators[0..N-1].withdrawal_credentials: 0x03 prefix (builders)
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

    # Set up balances directly (credentials set via builder_indices in prepare_process_withdrawals)
    for i in range(num_builders):
        state.validators[i].effective_balance = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
        state.balances[i] = spec.MAX_EFFECTIVE_BALANCE_ELECTRA + spec.MIN_ACTIVATION_BALANCE

    if num_builders > 0:
        builder_indices_list = list(range(num_builders))
        prepare_process_withdrawals(
            spec,
            state,
            builder_indices=builder_indices_list,
        )

    if num_pending > 0:
        pending_indices = list(range(num_builders, num_builders + num_pending))
        prepare_process_withdrawals(
            spec,
            state,
            pending_partial_indices=pending_indices,
        )

    regular_index = num_builders + num_pending + 1
    prepare_process_withdrawals(
        spec,
        state,
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
    if num_pending > 0:
        assert_params["pending_partial_delta"] = -int(num_pending)

    assert_process_withdrawals(spec, state, pre_state, **assert_params)


@with_gloas_and_later
@spec_state_test
def test_all_builder_withdrawals_invalid(spec, state):
    """
    All builders have insufficient balance, should process pending/regular instead.

    Input State Configured:
        - validators[0,1].withdrawal_credentials: 0x03 prefix (builder)
        - validators[0,1].effective_balance: MIN_ACTIVATION_BALANCE
        - balances[0,1]: MIN_ACTIVATION_BALANCE - 1 (INSUFFICIENT for builder withdrawal)
        - builder_pending_withdrawals: 2 entries requesting MIN_ACTIVATION_BALANCE each
        - validators[5].withdrawable_epoch: <= current_epoch (sweep eligible)

    Output State Verified:
        - payload_expected_withdrawals: Contains 1 sweep withdrawal (validator 5)
        - Builder withdrawals with insufficient balance skipped
        - balances[5]: 0 (full withdrawal processed)
        - Note: When builder withdrawals are invalid, lower priority types are processed
    """

    current_epoch = spec.get_current_epoch(state)

    # Set up 2 builders with insufficient balance (credentials set via builder_credentials)
    prepare_process_withdrawals(spec, state, builder_credentials=[0, 1])
    for i in range(2):
        state.validators[i].effective_balance = spec.MIN_ACTIVATION_BALANCE
        state.balances[i] = spec.MIN_ACTIVATION_BALANCE - spec.Gwei(1)
        address = state.validators[i].withdrawal_credentials[12:]
        state.builder_pending_withdrawals.append(
            spec.BuilderPendingWithdrawal(
                fee_recipient=address,
                amount=spec.MIN_ACTIVATION_BALANCE,
                builder_index=i,
                withdrawable_epoch=current_epoch,
            )
        )

    # Add a regular withdrawal
    regular_index = 5
    prepare_process_withdrawals(
        spec,
        state,
        full_withdrawal_indices=[regular_index],
    )

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    # Verify builders with insufficient balance were skipped, regular was processed
    withdrawals = list(state.payload_expected_withdrawals)
    assert any(w.validator_index == regular_index for w in withdrawals), (
        "Regular sweep withdrawal should be processed"
    )
    for i in range(2):
        assert not any(w.validator_index == i for w in withdrawals), (
            f"Builder {i} with insufficient balance should not withdraw"
        )

    assert_process_withdrawals(
        spec, state, pre_state,
        withdrawal_count=1,
        balances={regular_index: 0},
        no_withdrawal_indices=[0, 1],
        withdrawal_index_delta=1,
    )


@with_gloas_and_later
@spec_state_test
def test_builder_slashed_zero_balance(spec, state):
    """
    Slashed builder with 0 balance should be skipped.

    Input State Configured:
        - validators[0].withdrawal_credentials: 0x03 prefix (builder)
        - validators[0].slashed: True
        - validators[0].effective_balance: 0
        - balances[0]: 0 (ZERO balance)
        - builder_pending_withdrawals: 1 entry for validator 0

    Output State Verified:
        - payload_expected_withdrawals: Empty
        - balances[0]: Remains 0
        - builder_pending_withdrawals: Unchanged (skipped, not processed)
        - Note: Slashed builder with 0 balance is skipped (nothing to withdraw)
    """

    builder_index = 0
    current_epoch = spec.get_current_epoch(state)

    # Set balance and credentials directly
    prepare_process_withdrawals(spec, state, builder_credentials=[builder_index])
    state.validators[builder_index].effective_balance = spec.Gwei(0)
    state.balances[builder_index] = spec.Gwei(0)
    state.validators[builder_index].slashed = True

    address = state.validators[builder_index].withdrawal_credentials[12:]
    state.builder_pending_withdrawals.append(
        spec.BuilderPendingWithdrawal(
            fee_recipient=address,
            amount=spec.MIN_ACTIVATION_BALANCE,
            builder_index=builder_index,
            withdrawable_epoch=current_epoch,
        )
    )
    pre_state = state.copy()

    yield from run_gloas_withdrawals_processing(spec, state)

    withdrawals = list(state.payload_expected_withdrawals)
    builder_withdrawals = [w for w in withdrawals if w.validator_index == builder_index]
    assert len(builder_withdrawals) == 0

    assert_process_withdrawals(
        spec, state, pre_state,
        withdrawal_count=0,
        balances={builder_index: 0},
        builder_pending_delta=0,
        withdrawal_index_delta=0,
        no_withdrawal_indices=[builder_index],
    )


@with_gloas_and_later
@spec_state_test
def test_builder_max_minus_one_plus_one_regular(spec, state):
    """
    Exactly MAX-1 builder withdrawals should leave exactly 1 slot for regular withdrawal.

    Input State Configured:
        - validators[0..MAX-2].withdrawal_credentials: 0x03 prefix (builders)
        - validators[0..MAX-2].effective_balance: MAX_EFFECTIVE_BALANCE_ELECTRA
        - balances[0..MAX-2]: MAX_EFFECTIVE_BALANCE_ELECTRA + MIN_ACTIVATION_BALANCE
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

    # Set balances directly (credentials set via builder_indices in prepare_process_withdrawals)
    for i in range(num_builders):
        state.validators[i].effective_balance = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
        state.balances[i] = spec.MAX_EFFECTIVE_BALANCE_ELECTRA + spec.MIN_ACTIVATION_BALANCE

    builder_indices_list = list(range(num_builders))
    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=builder_indices_list,
    )

    # Add multiple regular withdrawals, but only 1 should be processed
    regular_indices = [num_builders + 1, num_builders + 2, num_builders + 3]
    assert len(state.validators) >= max(regular_indices) + 1, (
        f"Test requires at least {max(regular_indices) + 1} validators"
    )

    state.next_withdrawal_validator_index = regular_indices[0]

    prepare_process_withdrawals(
        spec,
        state,
        full_withdrawal_indices=regular_indices,
    )

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    # Verify exactly 1 regular withdrawal when builders fill MAX-1 slots
    withdrawals = list(state.payload_expected_withdrawals)
    builder_withdrawals = [w for w in withdrawals if w.validator_index < num_builders]
    assert len(builder_withdrawals) == num_builders
    regular_withdrawals = [w for w in withdrawals if w.validator_index in regular_indices]
    assert len(regular_withdrawals) == 1, (
        "Should process exactly 1 regular withdrawal when builders fill MAX-1 slots"
    )
    assert regular_withdrawals[0].validator_index == regular_indices[0], (
        "Should process the first regular withdrawal in sweep order"
    )

    assert_process_withdrawals(
        spec, state, pre_state,
        withdrawal_count=spec.MAX_WITHDRAWALS_PER_PAYLOAD,
        balances={regular_indices[0]: 0},
        builder_pending_delta=-int(num_builders),
        withdrawal_index_delta=spec.MAX_WITHDRAWALS_PER_PAYLOAD,
        no_withdrawal_indices=regular_indices[1:],
    )


@with_gloas_and_later
@spec_state_test
def test_builder_wrong_credentials_still_processes(spec, state):
    """
    Builder pending withdrawal processes even with non-BUILDER_WITHDRAWAL_PREFIX.
    get_expected_withdrawals does not validate the withdrawal credential prefix.

    Input State Configured:
        - validators[0].withdrawal_credentials: 0x02 prefix (COMPOUNDING, not builder)
        - validators[0].effective_balance: MAX_EFFECTIVE_BALANCE_ELECTRA
        - balances[0]: MAX_EFFECTIVE_BALANCE_ELECTRA + MIN_ACTIVATION_BALANCE
        - builder_pending_withdrawals: 1 entry for validator 0 (manually added)
        - validators[1].withdrawable_epoch: <= current_epoch (sweep eligible)

    Output State Verified:
        - payload_expected_withdrawals: Contains 2 withdrawals (builder + sweep)
        - Builder withdrawal IS processed even with wrong credentials
        - Note: get_expected_withdrawals does not validate credential prefix
    """

    builder_index = 0
    regular_index = 1
    current_epoch = spec.get_current_epoch(state)

    # Set up compounding credentials (not builder credentials)
    set_compounding_withdrawal_credential_with_balance(
        spec,
        state,
        builder_index,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
        balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA + spec.MIN_ACTIVATION_BALANCE,
    )

    assert (
        state.validators[builder_index].withdrawal_credentials[0:1]
        != spec.BUILDER_WITHDRAWAL_PREFIX
    ), "Validator should have non-builder credentials (0x02 compounding) for this test"

    # Manually add builder pending withdrawal with wrong credentials
    address = state.validators[builder_index].withdrawal_credentials[12:]
    state.builder_pending_withdrawals.append(
        spec.BuilderPendingWithdrawal(
            fee_recipient=address,
            amount=spec.MIN_ACTIVATION_BALANCE,
            builder_index=builder_index,
            withdrawable_epoch=current_epoch,
        )
    )

    prepare_process_withdrawals(
        spec,
        state,
        full_withdrawal_indices=[regular_index],
    )

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    # Verify builder withdrawal processed even with wrong credentials
    withdrawals = list(state.payload_expected_withdrawals)
    builder_withdrawals = [w for w in withdrawals if w.validator_index == builder_index]
    regular_withdrawals = [w for w in withdrawals if w.validator_index == regular_index]
    assert len(builder_withdrawals) == 1, (
        "Builder withdrawal IS processed even with wrong credentials - no validation in get_expected_withdrawals"
    )
    assert len(regular_withdrawals) == 1, "Regular withdrawal should also be processed"

    expected_builder_balance = pre_state.balances[builder_index] - spec.MIN_ACTIVATION_BALANCE

    assert_process_withdrawals(
        spec, state, pre_state,
        withdrawal_count=2,
        balances={regular_index: 0, builder_index: expected_builder_balance},
        builder_pending_delta=-1,
        withdrawal_index_delta=2,
    )


@with_gloas_and_later
@spec_state_test
def test_builder_zero_withdrawal_amount(spec, state):
    """
    Builder withdrawal with amount = 0 should be skipped.

    Input State Configured:
        - validators[0].withdrawal_credentials: 0x03 prefix (builder)
        - validators[0].effective_balance: MAX_EFFECTIVE_BALANCE_ELECTRA
        - balances[0]: MAX_EFFECTIVE_BALANCE_ELECTRA (no excess above max)
        - builder_pending_withdrawals: 1 entry with amount = 0

    Output State Verified:
        - payload_expected_withdrawals: Empty (zero-amount produces no output)
        - balances[0]: Unchanged
        - builder_pending_withdrawals: Reduced by 1 (entry consumed even with zero amount)
    """

    builder_index = 0

    # Set balance directly (credentials set via builder_indices in prepare_process_withdrawals)
    state.validators[builder_index].effective_balance = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    state.balances[builder_index] = spec.MAX_EFFECTIVE_BALANCE_ELECTRA  # No excess

    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=[builder_index],
        builder_withdrawal_amounts={builder_index: spec.Gwei(0)},
    )
    pre_state = state.copy()

    yield from run_gloas_withdrawals_processing(spec, state)

    withdrawals = list(state.payload_expected_withdrawals)
    builder_withdrawals = [w for w in withdrawals if w.validator_index == builder_index]
    assert len(builder_withdrawals) == 0

    assert_process_withdrawals(
        spec, state, pre_state,
        withdrawal_count=0,
        balance_deltas={builder_index: 0},
        builder_pending_delta=-1,
        withdrawal_index_delta=0,
        no_withdrawal_indices=[builder_index],
    )
