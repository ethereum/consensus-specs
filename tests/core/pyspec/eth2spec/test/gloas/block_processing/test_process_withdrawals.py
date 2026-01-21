import pytest

from eth2spec.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from tests.infra.helpers.builders import add_builder_to_registry
from tests.infra.helpers.withdrawals import (
    assert_process_withdrawals,
    prepare_process_withdrawals,
)


def run_gloas_withdrawals_processing(spec, state):
    """
    Minimal test harness for process_withdrawals that generates vectors.
    """

    yield "pre", state
    spec.process_withdrawals(state)
    yield "post", state


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
        - payload_expected_withdrawals: Contains 1 withdrawal
        - withdrawal.amount: 5 ETH (requested amount)
        - builders[0].balance: 0 (deduction capped to available balance)
        - builder_pending_withdrawals: Reduced by 1 (processed even if capped)
        - next_withdrawal_index: Incremented by 1
    """
    builder_index = 0
    withdrawal_amount = spec.Gwei(5_000_000_000)
    available_balance = spec.Gwei(1_000_000_000)

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
        builder_balances={builder_index: 0},
        builder_pending_delta=-1,
        withdrawal_index_delta=1,
        withdrawal_amounts_builders={builder_index: withdrawal_amount},
    )


@with_gloas_and_later
@spec_state_test
def test_builder_withdrawal_insufficient_balance_realistic_bounds(spec, state):
    """
    Test builder withdrawal with insufficient balance using realistic bounds.

    This test uses MIN_DEPOSIT_AMOUNT-based values to test edge cases with
    realistic builder balances (builders need MIN_DEPOSIT_AMOUNT to be active).

    Input State Configured:
        - state.builders[0]: Builder with balance = MIN_DEPOSIT_AMOUNT + 122 Gwei
        - builder_pending_withdrawals: Contains 1 entry requesting MIN_DEPOSIT_AMOUNT + 123 Gwei
        - builders[0].balance: Insufficient by exactly 1 Gwei

    Output State Verified:
        - payload_expected_withdrawals: Contains 1 withdrawal
        - withdrawal.amount: MIN_DEPOSIT_AMOUNT + 123 Gwei (requested amount)
        - builders[0].balance: 0 (deduction capped to available balance)
        - builder_pending_withdrawals: Reduced by 1 (processed even if capped)
        - next_withdrawal_index: Incremented by 1
    """
    builder_index = 0
    withdrawal_amount = spec.MIN_DEPOSIT_AMOUNT + spec.Gwei(123)
    available_balance = spec.MIN_DEPOSIT_AMOUNT + spec.Gwei(122)

    assert withdrawal_amount > available_balance, "Test requires insufficient balance"

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
        builder_balances={builder_index: 0},
        builder_pending_delta=-1,
        withdrawal_index_delta=1,
        withdrawal_amounts_builders={builder_index: withdrawal_amount},
    )


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

    num_builders = spec.MAX_WITHDRAWALS_PER_PAYLOAD // 2
    num_pending = spec.MAX_WITHDRAWALS_PER_PAYLOAD // 2
    num_sweep = spec.MAX_WITHDRAWALS_PER_PAYLOAD // 2

    builder_indices = list(range(num_builders))
    pending_indices = list(range(num_pending))
    sweep_indices = list(range(num_pending, num_pending + num_sweep))

    withdrawal_amount = spec.Gwei(1_000_000_000)

    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=builder_indices,
        builder_withdrawal_amounts={i: withdrawal_amount for i in builder_indices},
        builder_balances={i: withdrawal_amount + spec.MIN_DEPOSIT_AMOUNT for i in builder_indices},
        pending_partial_indices=pending_indices,
        full_withdrawal_indices=sweep_indices,
    )

    total_added = num_builders + num_pending + num_sweep
    assert total_added > spec.MAX_WITHDRAWALS_PER_PAYLOAD, "Test setup should exceed limit"

    # Calculate expected pending partial withdrawals to be consumed
    # From get_pending_partial_withdrawals (specs/electra/beacon-chain.md):
    #   withdrawals_limit = min(prior + MAX_PENDING_PARTIALS, MAX - 1)
    # The -1 reserves at least one slot for sweep withdrawals
    withdrawals_limit = min(
        num_builders + spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP,
        spec.MAX_WITHDRAWALS_PER_PAYLOAD - 1,
    )
    num_partial_withdrawals_consumed = min(num_pending, withdrawals_limit - num_builders)

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=spec.MAX_WITHDRAWALS_PER_PAYLOAD,
        withdrawal_index_delta=spec.MAX_WITHDRAWALS_PER_PAYLOAD,
        builder_pending_delta=-int(num_builders),
        pending_partial_delta=-int(num_partial_withdrawals_consumed),
    )


@with_gloas_and_later
@spec_state_test
def test_pending_withdrawals_processing(spec, state):
    """
    Test pending partial withdrawals processing.

    Input State Configured:
        - pending_partial_withdrawals: MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP entries
        - pending_partial_withdrawals[*].withdrawable_epoch: = current_epoch
        - balances[*]: MAX_EFFECTIVE_BALANCE + 1 ETH (excess to withdraw)
        - builder_pending_withdrawals: Empty

    Output State Verified:
        - payload_expected_withdrawals: MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP
        - pending_partial_withdrawals: Empty (all processed)
        - pending_partial_delta: -MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP
        - balances[*]: MAX_EFFECTIVE_BALANCE (excess withdrawn)
        - next_withdrawal_index: Incremented by MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP
    """

    pending_indices = list(range(spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP))

    excess_balance = spec.Gwei(1_000_000_000)
    initial_balance = spec.MAX_EFFECTIVE_BALANCE + excess_balance

    prepare_process_withdrawals(
        spec,
        state,
        pending_partial_indices=pending_indices,
        validator_balances={i: initial_balance for i in pending_indices},
    )

    expected_withdrawals = spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    expected_balances = {i: spec.MAX_EFFECTIVE_BALANCE for i in pending_indices}

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=expected_withdrawals,
        pending_partial_delta=-int(expected_withdrawals),
        withdrawal_index_delta=expected_withdrawals,
        balances=expected_balances,
    )


@with_gloas_and_later
@spec_state_test
def test_pending_withdrawals_processing_exceeds_limit(spec, state):
    """
    Test pending partial withdrawals processing with more than the limit.

    Input State Configured:
        - pending_partial_withdrawals: MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP + 2 entries
        - pending_partial_withdrawals[*].withdrawable_epoch: = current_epoch
        - balances[*]: MAX_EFFECTIVE_BALANCE + 1 ETH (excess to withdraw)
        - builder_pending_withdrawals: Empty

    Output State Verified:
        - payload_expected_withdrawals: MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP
        - pending_partial_withdrawals: 2 entries remain (limit enforced)
        - pending_partial_delta: -MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP
        - balances[0..MAX-1]: MAX_EFFECTIVE_BALANCE (processed)
        - balances[MAX..MAX+1]: MAX_EFFECTIVE_BALANCE + 1 ETH (unchanged)
        - next_withdrawal_index: Incremented by MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP
    """
    num_pending = spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP + 2
    pending_indices = list(range(num_pending))

    excess_balance = spec.Gwei(1_000_000_000)
    initial_balance = spec.MAX_EFFECTIVE_BALANCE + excess_balance

    prepare_process_withdrawals(
        spec,
        state,
        pending_partial_indices=pending_indices,
        validator_balances={i: initial_balance for i in pending_indices},
    )

    expected_processed = spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP
    processed_indices = pending_indices[:expected_processed]
    unprocessed_indices = pending_indices[expected_processed:]

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    expected_balances = {i: spec.MAX_EFFECTIVE_BALANCE for i in processed_indices}
    expected_balances.update({i: initial_balance for i in unprocessed_indices})

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=expected_processed,
        pending_partial_delta=-int(expected_processed),
        withdrawal_index_delta=expected_processed,
        balances=expected_balances,
    )


@with_gloas_and_later
@spec_state_test
def test_early_return_empty_parent_block(spec, state):
    """
    Test early return when parent block is empty.

    Input State Configured:
        - latest_block_hash: != latest_execution_payload_bid.block_hash (parent block EMPTY)
        - builder_pending_withdrawals: Contains entry for builder 0
        - validators[1,2].withdrawable_epoch: = current_epoch (fully withdrawable)
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
    builder_index = 0
    validator_indices = [1, 2]

    withdrawal_amount = spec.Gwei(1_000_000_000)
    state.balances[0] = max(state.balances[0], withdrawal_amount + spec.MIN_ACTIVATION_BALANCE)
    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=[builder_index],
        builder_withdrawal_amounts={builder_index: withdrawal_amount},
        full_withdrawal_indices=validator_indices,
        parent_block_empty=True,
    )

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        all_state_unchanged=True,
    )


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

    prepare_process_withdrawals(
        spec,
        state,
        compounding_indices=[validator_index],
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
def test_builder_payments_exceed_limit_blocks_other_withdrawals(spec, state):
    """
    Test builder payments exceeding MAX_WITHDRAWALS_PER_PAYLOAD limit.

    This test verifies that when builder pending withdrawals exceed the maximum,
    only MAX_WITHDRAWALS_PER_PAYLOAD - 1 are processed, reserving one slot for
    validator sweep withdrawals.

    Input State Configured:
        - state.builders[0..N]: Builders exist in registry with sufficient balance
        - builder_pending_withdrawals: MAX_WITHDRAWALS_PER_PAYLOAD + 2 entries
        - validators[*].balances: Capped to prevent sweep withdrawals

    Output State Verified:
        - payload_expected_withdrawals: Limited to MAX_WITHDRAWALS_PER_PAYLOAD - 1
          (one slot reserved for validator sweep)
        - builder_pending_withdrawals: 3 entries remain unprocessed
    """
    num_builders = spec.MAX_WITHDRAWALS_PER_PAYLOAD + 2
    withdrawal_amount = spec.Gwei(1_000_000_000)

    builder_indices = list(range(num_builders))

    # Cap validator balances to prevent sweep withdrawals
    capped_validator_balances = {
        i: min(state.balances[i], spec.MAX_EFFECTIVE_BALANCE)
        for i in range(len(state.validators))
        if state.validators[i].withdrawal_credentials[0:1] == spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
    }

    # Builder balances, ensure at least enough for withdrawal
    builder_balance_values = {
        i: max(state.builders[i].balance, withdrawal_amount + spec.MIN_ACTIVATION_BALANCE)
        for i in builder_indices
    }

    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=builder_indices,
        builder_withdrawal_amounts={i: withdrawal_amount for i in builder_indices},
        builder_balances=builder_balance_values,
        validator_balances=capped_validator_balances,
    )

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    # One slot is reserved for validator sweep, so only MAX - 1 builder withdrawals processed
    expected_builder_withdrawals = spec.MAX_WITHDRAWALS_PER_PAYLOAD - 1

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=expected_builder_withdrawals,
        builder_pending_delta=-int(expected_builder_withdrawals),
        withdrawal_index_delta=expected_builder_withdrawals,
    )


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

    remaining_pending = spec.MAX_WITHDRAWALS_PER_PAYLOAD - expected_pending
    assert len(state.pending_partial_withdrawals) == remaining_pending

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

    sweep_indices = list(range(spec.MAX_WITHDRAWALS_PER_PAYLOAD))

    prepare_process_withdrawals(spec, state, full_withdrawal_indices=sweep_indices)

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

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
def test_builder_withdrawals_processed_order(spec, state):
    """
    Verifies the priority ordering: builder > pending partial > sweep.

    Input State Configured:
        - builders[0].balance: MIN_ACTIVATION_BALANCE + MIN_DEPOSIT_AMOUNT
        - builder_pending_withdrawals: entry for builder 0, amount = MIN_ACTIVATION_BALANCE
        - pending_partial_withdrawals: entry for validator 1, amount = 1 Gwei
        - validators[0].withdrawable_epoch: == current_epoch (fully withdrawable)

    Output State Verified:
        - payload_expected_withdrawals: 3 withdrawals in order:
          [0] builder 0, [1] validator 1 (pending), [2] validator 0 (sweep)
        - withdrawal_amounts: builder = MIN_ACTIVATION_BALANCE, pending = 1 Gwei, sweep = full balance
        - balances[0]: 0 (full withdrawal)
        - balances[1]: pre_balance - 1 Gwei
        - builders[0].balance: decreased by MIN_ACTIVATION_BALANCE
    """

    builder_index = 0
    pending_index = 1
    sweep_index = 0
    withdrawal_amount = spec.MIN_ACTIVATION_BALANCE

    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=[builder_index],
        builder_withdrawal_amounts={builder_index: withdrawal_amount},
        builder_balances={builder_index: withdrawal_amount + spec.MIN_DEPOSIT_AMOUNT},
        pending_partial_indices=[pending_index],
        full_withdrawal_indices=[sweep_index],
    )

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    builder_validator_index = spec.convert_builder_index_to_validator_index(builder_index)

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=3,
        withdrawal_order=[builder_validator_index, pending_index, sweep_index],
        balances={
            sweep_index: 0,
            pending_index: pre_state.balances[pending_index] - 1_000_000_000,
        },
        builder_balance_deltas={builder_index: -int(withdrawal_amount)},
        builder_pending_delta=-1,
        pending_partial_delta=-1,
        withdrawal_index_delta=3,
        withdrawal_amounts_builders={builder_index: withdrawal_amount},
        withdrawal_amounts={
            pending_index: 1_000_000_000,  # default pending partial amount
            sweep_index: pre_state.balances[sweep_index],  # full withdrawal
        },
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
    Test that the spec reserves at least 1 slot for sweep withdrawals.

    This test verifies that when builders + pending partials exceed
    MAX_WITHDRAWALS_PER_PAYLOAD - 1, the spec caps pending partials to ensure
    at least 1 slot remains for sweep withdrawals.

    Input State Configured:
        - builder_pending_withdrawals: (MAX - PENDING_LIMIT + 1) entries
        - pending_partial_withdrawals: PENDING_LIMIT entries
        - Total requested: builders + pending = MAX + 1 (overfill attempt)
        - validators[0]: sweep eligible (withdrawable_epoch <= current_epoch)

    Expected Behavior:
        - All builders are processed (they fit within MAX - 1)
        - Pending partials are capped to (MAX - 1 - builders) to reserve sweep slot
        - Exactly 1 sweep withdrawal is included
        - Total withdrawals = MAX (payload fully filled)
    """

    assert spec.MAX_WITHDRAWALS_PER_PAYLOAD >= 3, (
        "Test requires MAX_WITHDRAWALS_PER_PAYLOAD to be at least 3"
    )

    # Try to overfill: set up builders + pending > MAX_WITHDRAWALS_PER_PAYLOAD
    # The spec should cap builder + pending at MAX_WITHDRAWALS_PER_PAYLOAD - 1 to reserve sweep slot
    num_builders_requested = (
        spec.MAX_WITHDRAWALS_PER_PAYLOAD - spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP + 1
    )
    num_pending_requested = spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP

    # Verify we're actually trying to overfill
    assert num_builders_requested + num_pending_requested > spec.MAX_WITHDRAWALS_PER_PAYLOAD, (
        f"Test requires overfill attempt: {num_builders_requested} + {num_pending_requested} "
        f"> {spec.MAX_WITHDRAWALS_PER_PAYLOAD}"
    )

    withdrawal_amount = spec.MIN_ACTIVATION_BALANCE

    builder_indices_list = list(range(num_builders_requested))

    for builder_index in builder_indices_list:
        if builder_index >= len(state.builders):
            add_builder_to_registry(spec, state, builder_index)

    # pending_indices start from 1 to avoid overlap with regular_index
    pending_indices = list(range(1, 1 + num_pending_requested))
    regular_index = 0  # Sweep-eligible validator

    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=builder_indices_list,
        builder_withdrawal_amounts={i: withdrawal_amount for i in builder_indices_list},
        builder_balances={
            i: withdrawal_amount + spec.MIN_DEPOSIT_AMOUNT for i in builder_indices_list
        },
        pending_partial_indices=pending_indices,
        full_withdrawal_indices=[regular_index],
    )

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    withdrawals = list(state.payload_expected_withdrawals)

    # The spec processes all builders (they fit within MAX - 1), then caps pending partials
    # to reserve space for sweep. The overfill is in the combination, not builders alone.
    expected_builders = num_builders_requested
    # Pending: capped at remaining space (MAX - 1 - builders) and MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP
    remaining_for_pending = spec.MAX_WITHDRAWALS_PER_PAYLOAD - 1 - expected_builders
    expected_pending = min(
        num_pending_requested,
        spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP,
        remaining_for_pending,
    )
    expected_sweep = 1
    expected_total = expected_builders + expected_pending + expected_sweep

    assert expected_total == spec.MAX_WITHDRAWALS_PER_PAYLOAD, (
        f"Expected total withdrawals to fill payload: {spec.MAX_WITHDRAWALS_PER_PAYLOAD}, "
        f"but got {expected_total}"
    )

    builder_validator_indices = [
        spec.convert_builder_index_to_validator_index(i)
        for i in builder_indices_list[:expected_builders]
    ]
    expected_order = (
        builder_validator_indices + pending_indices[:expected_pending] + [regular_index]
    )

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=expected_total,
        balances={regular_index: 0},
        withdrawal_index_delta=expected_total,
        builder_pending_delta=-int(expected_builders),
        builder_balance_deltas={
            i: -int(withdrawal_amount) for i in builder_indices_list[:expected_builders]
        },
        pending_partial_delta=-int(expected_pending),
        withdrawal_order=expected_order,
    )


@with_gloas_and_later
@spec_state_test
def test_all_builder_withdrawals_zero_balance(spec, state):
    """
    Builders with zero balance - withdrawals still processed but with zero deduction.

    Input State Configured:
        - state.builders[0,1]: Builders exist with zero balance
        - builder_pending_withdrawals: 2 entries requesting MIN_ACTIVATION_BALANCE each
        - validators[0].withdrawable_epoch: <= current_epoch (sweep eligible)

    Note: regular_index=0 intentionally overlaps with builder_index=0 to demonstrate
    that builder indices and validator indices are separate namespaces.

    Output State Verified:
        - payload_expected_withdrawals: Contains 3 withdrawals (2 builder + 1 sweep)
        - Builder withdrawals processed (deduction capped to 0)
        - builders[0,1].balance: 0 (unchanged)
        - balances[0]: 0 (full withdrawal processed)
        - Note: Builder withdrawals always processed, amount capped to available balance
    """

    builder_indices = [0, 1]
    withdrawal_amount = spec.MIN_ACTIVATION_BALANCE
    regular_index = (
        0  # Same numeric index as builder 0, but different entity (validator vs builder)
    )

    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=builder_indices,
        builder_withdrawal_amounts={i: withdrawal_amount for i in builder_indices},
        builder_balances={i: 0 for i in builder_indices},
        full_withdrawal_indices=[regular_index],
    )

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    builder_validator_indices = [
        spec.convert_builder_index_to_validator_index(i) for i in builder_indices
    ]

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=3,
        withdrawal_order=builder_validator_indices + [regular_index],
        balances={regular_index: 0},
        builder_balances={0: 0, 1: 0},
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
        - validators[0, 1, 2].withdrawable_epoch: <= current_epoch (sweep eligible)
        - next_withdrawal_validator_index: Set to first sweep validator

    Note: Validator indices intentionally overlap with builder indices to demonstrate
    that they are separate namespaces.

    Output State Verified:
        - payload_expected_withdrawals: MAX_WITHDRAWALS_PER_PAYLOAD total
          - MAX-1 builder withdrawals
          - Exactly 1 sweep withdrawal (first in sweep order)
        - Note: Builder cap at MAX-1 reserves 1 slot for other withdrawal types
    """

    num_builders = spec.MAX_WITHDRAWALS_PER_PAYLOAD - 1
    withdrawal_amount = spec.MIN_ACTIVATION_BALANCE

    builder_indices_list = list(range(num_builders))

    # Validator indices intentionally overlap with builder indices to test separate namespaces
    # Add multiple regular withdrawals, but only 1 should be processed
    regular_indices = [0, 1, 2]  # Same numeric indices as builders, but different entities

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
    yield from run_gloas_withdrawals_processing(spec, state)

    builder_validator_indices = [
        spec.convert_builder_index_to_validator_index(i) for i in builder_indices_list
    ]

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=spec.MAX_WITHDRAWALS_PER_PAYLOAD,
        withdrawal_order=builder_validator_indices + [regular_indices[0]],
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

    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=[builder_index],
        builder_withdrawal_amounts={builder_index: spec.Gwei(0)},
        builder_balances={builder_index: spec.MIN_DEPOSIT_AMOUNT},
    )

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

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


@with_gloas_and_later
@spec_state_test
def test_full_builder_payload_reserves_sweep_slot(spec, state):
    """
    Test that builder withdrawals reserve one slot for validator sweep.

    This test verifies the fix from https://github.com/ethereum/consensus-specs/pull/4832
    which reserves one slot in MAX_WITHDRAWALS_PER_PAYLOAD for validator sweep withdrawals.

    Previous Bug (before the fix):
        When all MAX_WITHDRAWALS_PER_PAYLOAD slots were filled by builder withdrawals,
        next_withdrawal_validator_index was calculated incorrectly. The spec used
        (withdrawals[-1].validator_index + 1) % num_validators, but builder withdrawals
        have BUILDER_INDEX_FLAG (2^40) set in validator_index, producing incorrect results.
        See also: https://github.com/ethereum/consensus-specs/pull/4835

    Input State:
        - builder_pending_withdrawals: MAX_WITHDRAWALS_PER_PAYLOAD entries
        - All validator balances capped (no validator withdrawals)
        - next_withdrawal_validator_index: Known starting value

    Output State Verified:
        - Only MAX_WITHDRAWALS_PER_PAYLOAD - 1 builder withdrawals processed
        - One slot reserved for validator sweep
        - next_withdrawal_validator_index: Correctly advanced by MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP
          (sweep runs even though no validator withdrawals are produced due to capped balances)
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

    # Verify setup: One slot reserved for sweep, so only MAX - 1 builder withdrawals
    expected_result = spec.get_expected_withdrawals(state)
    expected_builder_withdrawals = spec.MAX_WITHDRAWALS_PER_PAYLOAD - 1
    assert len(expected_result.withdrawals) == expected_builder_withdrawals, (
        f"Expected {expected_builder_withdrawals} builder withdrawals (one slot reserved for sweep)"
    )
    for w in expected_result.withdrawals:
        assert spec.is_builder_index(w.validator_index), (
            "All withdrawals must be builder withdrawals"
        )

    # Execute
    pre_state = state.copy()
    yield "pre", pre_state
    spec.process_withdrawals(state)
    yield "post", state

    # Calculate what the buggy spec would have produced (before the fix)
    # If all MAX slots were filled with builder withdrawals, the last withdrawal's
    # validator_index would have BUILDER_INDEX_FLAG set, producing wrong result
    last_builder_validator_index = expected_result.withdrawals[-1].validator_index
    buggy_result = (last_builder_validator_index + 1) % num_validators

    # Calculate what the correct result should be
    # The reserved slot allows validator sweep to run, advancing the index by MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP
    correct_result = (
        starting_validator_index + spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP
    ) % num_validators

    # Assert the fix: next_withdrawal_validator_index is correct
    # Before the fix, it would have been buggy_result (completely wrong due to BUILDER_INDEX_FLAG)
    assert state.next_withdrawal_validator_index == correct_result, (
        f"Spec produces {state.next_withdrawal_validator_index}, expected {correct_result}"
    )
    assert state.next_withdrawal_validator_index != buggy_result, (
        f"Bug fix verified: spec no longer produces buggy result {buggy_result}"
    )

    # Verify: One builder withdrawal remains unprocessed (slot was reserved for sweep)
    assert len(state.builder_pending_withdrawals) == 1, (
        "One builder withdrawal should remain (slot was reserved for sweep)"
    )


@with_gloas_and_later
@spec_state_test
def test_single_builder_sweep_withdrawal(spec, state):
    """
    Test processing a single builder sweep withdrawal.

    Builder sweep withdrawals occur when builder.withdrawable_epoch <= current_epoch.
    Unlike pending withdrawals, sweep uses builder.execution_address and full balance.

    Input State Configured:
        - builders[0].withdrawable_epoch: current_epoch (eligible for sweep)
        - builders[0].balance: 5 ETH
        - builders[0].execution_address: 0xab * 20
        - builder_pending_withdrawals: Empty
        - next_withdrawal_builder_index: 0

    Output State Verified:
        - payload_expected_withdrawals: 1 builder sweep withdrawal
        - withdrawal.address: builder.execution_address
        - withdrawal.amount: 5 ETH (full balance)
        - builders[0].balance: 0
    """
    builder_index = 0
    sweep_balance = spec.Gwei(5_000_000_000)
    custom_address = b"\xab" * 20

    prepare_process_withdrawals(
        spec,
        state,
        builder_sweep_indices=[builder_index],
        builder_balances={builder_index: sweep_balance},
        builder_execution_addresses={builder_index: custom_address},
        next_withdrawal_builder_index=builder_index,
    )

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=1,
        builder_balances={builder_index: 0},
        withdrawal_amounts_builders={builder_index: sweep_balance},
        withdrawal_addresses_builders={builder_index: spec.ExecutionAddress(custom_address)},
    )


@with_gloas_and_later
@spec_state_test
def test_multiple_builder_sweep_withdrawals(spec, state):
    """
    Test processing multiple builder sweep withdrawals.

    Input State Configured:
        - builders[0,1,2].withdrawable_epoch: current_epoch (all eligible)
        - builders[0,1,2].balance: 1, 2, 3 ETH respectively
        - builder_pending_withdrawals: Empty
        - next_withdrawal_builder_index: 0

    Output State Verified:
        - payload_expected_withdrawals: 3 builder sweep withdrawals
        - builders[0,1,2].balance: All 0
        - withdrawal amounts: 1, 2, 3 ETH respectively
    """
    builder_indices = [0, 1, 2]
    balances = {
        0: spec.Gwei(1_000_000_000),
        1: spec.Gwei(2_000_000_000),
        2: spec.Gwei(3_000_000_000),
    }

    prepare_process_withdrawals(
        spec,
        state,
        builder_sweep_indices=builder_indices,
        builder_balances=balances,
        next_withdrawal_builder_index=0,
    )

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=3,
        builder_balances={i: 0 for i in builder_indices},
        withdrawal_amounts_builders=balances,
    )


@with_gloas_and_later
@spec_state_test
def test_builder_sweep_zero_balance_skipped(spec, state):
    """
    Test that builder sweep skips builders with zero balance.

    Input State Configured:
        - builders[0].withdrawable_epoch: current_epoch (eligible)
        - builders[0].balance: 0 (should be skipped)
        - builders[1].withdrawable_epoch: current_epoch (eligible)
        - builders[1].balance: 2 ETH (should be processed)
        - next_withdrawal_builder_index: 0

    Output State Verified:
        - payload_expected_withdrawals: 1 withdrawal (only builder 1)
        - builders[0].balance: 0 (unchanged, was skipped)
        - builders[1].balance: 0 (withdrawn)
    """
    prepare_process_withdrawals(
        spec,
        state,
        builder_sweep_indices=[0, 1],
        builder_balances={0: spec.Gwei(0), 1: spec.Gwei(2_000_000_000)},
        next_withdrawal_builder_index=0,
    )

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=1,
        builder_balances={0: 0, 1: 0},
        withdrawal_amounts_builders={1: spec.Gwei(2_000_000_000)},
    )


@with_gloas_and_later
@spec_state_test
def test_builder_sweep_not_withdrawable_skipped(spec, state):
    """
    Test that builder sweep skips builders not yet withdrawable.

    Input State Configured:
        - builders[0].withdrawable_epoch: current_epoch + 1 (not yet eligible)
        - builders[0].balance: 5 ETH
        - builders[1].withdrawable_epoch: current_epoch (eligible)
        - builders[1].balance: 2 ETH
        - next_withdrawal_builder_index: 0

    Output State Verified:
        - payload_expected_withdrawals: 1 withdrawal (only builder 1)
        - builders[0].balance: 5 ETH (unchanged, not withdrawable yet)
        - builders[1].balance: 0 (withdrawn)
    """
    prepare_process_withdrawals(
        spec,
        state,
        builder_sweep_indices=[0, 1],
        builder_balances={0: spec.Gwei(5_000_000_000), 1: spec.Gwei(2_000_000_000)},
        builder_sweep_withdrawable_offsets={0: 1, 1: 0},  # Builder 0: future, Builder 1: now
        next_withdrawal_builder_index=0,
    )

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=1,
        builder_balances={0: spec.Gwei(5_000_000_000), 1: 0},
        withdrawal_amounts_builders={1: spec.Gwei(2_000_000_000)},
    )


@with_gloas_and_later
@spec_state_test
def test_invalid_builder_index_pending(spec, state):
    """
    Test that process_withdrawals raises IndexError for invalid builder index
    in builder_pending_withdrawals.

    Input State Configured:
        - builder_pending_withdrawals: Contains entry with builder_index >= len(state.builders)
        - validate_builder_indices: False (bypass helper validation)

    Expected:
        - IndexError raised when process_withdrawals tries to access invalid builder
    """
    invalid_builder_index = len(state.builders)
    withdrawal_amount = spec.Gwei(1_000_000_000)

    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=[invalid_builder_index],
        builder_withdrawal_amounts={invalid_builder_index: withdrawal_amount},
        validate_builder_indices=False,
    )

    yield "pre", state

    with pytest.raises(IndexError):
        spec.process_withdrawals(state)

    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_invalid_builder_index_sweep(spec, state):
    """
    Test that process_withdrawals raises IndexError for invalid builder index
    during builder sweep.

    Input State Configured:
        - next_withdrawal_builder_index: Set to len(state.builders) (invalid)
        - validate_builder_indices: False (bypass helper validation)

    Expected:
        - IndexError raised when process_withdrawals tries to sweep invalid builder
    """
    invalid_builder_index = len(state.builders)

    prepare_process_withdrawals(
        spec,
        state,
        next_withdrawal_builder_index=invalid_builder_index,
        validate_builder_indices=False,
    )

    yield "pre", state

    with pytest.raises(IndexError):
        spec.process_withdrawals(state)

    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_invalid_validator_index_pending_partial(spec, state):
    """
    Test that process_withdrawals raises IndexError for invalid validator index
    in pending_partial_withdrawals.

    Input State Configured:
        - pending_partial_withdrawals: Contains entry with validator_index >= len(state.validators)
        - validate_validator_indices: False (bypass helper validation)

    Expected:
        - IndexError raised when process_withdrawals tries to access invalid validator
    """
    invalid_validator_index = len(state.validators)

    prepare_process_withdrawals(
        spec,
        state,
        pending_partial_indices=[invalid_validator_index],
        validate_validator_indices=False,
    )

    yield "pre", state

    with pytest.raises(IndexError):
        spec.process_withdrawals(state)

    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_invalid_validator_index_sweep(spec, state):
    """
    Test that process_withdrawals raises IndexError for invalid validator index
    during validator sweep.

    Input State Configured:
        - next_withdrawal_validator_index: Set to len(state.validators) (invalid)
        - validate_validator_indices: False (bypass helper validation)

    Expected:
        - IndexError raised when process_withdrawals tries to sweep invalid validator
    """
    invalid_validator_index = len(state.validators)

    prepare_process_withdrawals(
        spec,
        state,
        next_withdrawal_validator_index=invalid_validator_index,
        validate_validator_indices=False,
    )

    yield "pre", state

    with pytest.raises(IndexError):
        spec.process_withdrawals(state)

    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_duplicate_builder_index_in_pending_withdrawals(spec, state):
    """
    Test processing multiple pending withdrawals for the same builder.

    Input State Configured:
        - builder_pending_withdrawals: 3 entries all for builder 0
        - builders[0].balance: Sufficient for all withdrawals

    Output State Verified:
        - All 3 withdrawals processed
        - builders[0].balance: Decreased by total of all withdrawal amounts
        - builder_pending_withdrawals: Reduced by 3
    """
    builder_index = 0
    withdrawal_amount = spec.Gwei(1_000_000_000)
    num_withdrawals = 3

    prepare_process_withdrawals(
        spec,
        state,
        builder_indices=[builder_index] * num_withdrawals,
        builder_withdrawal_amounts={builder_index: withdrawal_amount},
        builder_balances={
            builder_index: withdrawal_amount * num_withdrawals + spec.MIN_DEPOSIT_AMOUNT
        },
    )

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=num_withdrawals,
        builder_pending_delta=-num_withdrawals,
    )


@with_gloas_and_later
@spec_state_test
def test_builder_sweep_index_wrap_around(spec, state):
    """
    Test that next_withdrawal_builder_index wraps around the builder registry.

    Input State Configured:
        - next_withdrawal_builder_index: len(builders) - 2 (near end of registry)
        - builders at indices -2, -1, 0: Eligible for sweep with balance > 0

    Output State Verified:
        - Sweep starts near end and wraps to beginning
        - Builder at index 0 is swept (verifies wrap-around occurred)
    """
    num_builders = len(state.builders)
    start_index = num_builders - 2

    sweep_indices = [num_builders - 2, num_builders - 1, 0]

    prepare_process_withdrawals(
        spec,
        state,
        builder_sweep_indices=sweep_indices,
        next_withdrawal_builder_index=start_index,
    )

    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        builder_balances={0: 0},  # Builder 0 swept after wrap-around
    )
