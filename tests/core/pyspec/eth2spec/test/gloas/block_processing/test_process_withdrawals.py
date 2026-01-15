import pytest

from tests.core.pyspec.eth2spec.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
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

    assert max(builder_indices) < len(state.builders), (
        f"Max builder index {max(builder_indices)} must exist in registry (builders: {len(state.builders)})"
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
    withdrawal_amount = spec.Gwei(5_000_000_000)
    available_balance = spec.Gwei(1_000_000_000)

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
        builder_balances={builder_index: 0},
        builder_pending_delta=-1,
        withdrawal_index_delta=1,
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

    assert max(builder_indices) < len(state.builders), (
        f"Max builder index {max(builder_indices)} must exist in registry "
        f"(builders: {len(state.builders)})"
    )
    assert max(sweep_indices) < len(state.validators), (
        f"Max validator index {max(sweep_indices)} must exist in registry "
        f"(validators: {len(state.validators)})"
    )

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
        - validators[*]: Configured for partial withdrawals
        - No builder_pending_withdrawals

    Output State Verified:
        - payload_expected_withdrawals: MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP
        - pending_partial_withdrawals: Empty (all processed)
        - balances[*]: Each reduced to max_effective_balance
        - next_withdrawal_index: Incremented by processed count
    """

    pending_indices = list(range(spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP))
    assert max(pending_indices) < len(state.validators), (
        f"Max validator index {max(pending_indices)} must exist in registry "
        f"(validators: {len(state.validators)})"
    )

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
    assert builder_index < len(state.builders), "Builder must exist in registry"
    assert max(validator_indices) < len(state.validators), (
        f"Max validator index {max(validator_indices)} must exist in registry "
        f"(validators: {len(state.validators)})"
    )

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
    assert validator_index < len(state.validators), "Validator must exist in registry"

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
    Test builder payments at MAX_WITHDRAWALS_PER_PAYLOAD limit (documents known spec bug).

    Input State Configured:
        - state.builders[0..N]: Builders exist in registry with sufficient balance
        - builder_pending_withdrawals: MAX_WITHDRAWALS_PER_PAYLOAD + 2 entries
        - validators[*].balances: Capped to prevent sweep withdrawals

    Output State Verified:
        - payload_expected_withdrawals: Limited to MAX_WITHDRAWALS_PER_PAYLOAD
        - builder_pending_withdrawals: 2 entries remain unprocessed
        - next_withdrawal_validator_index: KNOWN BUG - wraps incorrectly due to BUILDER_INDEX_FLAG
        - See: https://github.com/ethereum/consensus-specs/pull/4835
    """
    num_builders = spec.MAX_WITHDRAWALS_PER_PAYLOAD + 2
    withdrawal_amount = spec.Gwei(1_000_000_000)

    assert num_builders <= len(state.builders), "Not enough builders in registry for test"

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

    # Verify builder queue was partially processed (exactly MAX withdrawals)
    assert len(state.builder_pending_withdrawals) == 2, (
        "Exactly 2 builder withdrawals should remain unprocessed"
    )
    assert len(list(state.payload_expected_withdrawals)) == spec.MAX_WITHDRAWALS_PER_PAYLOAD
    assert state.next_withdrawal_index == (
        pre_state.next_withdrawal_index + spec.MAX_WITHDRAWALS_PER_PAYLOAD
    )

    # Verify that assert_process_withdrawals raises error for this bug scenario
    # See https://github.com/ethereum/consensus-specs/pull/4835
    with pytest.raises(ValueError, match="BUILDER_INDEX_FLAG"):
        assert_process_withdrawals(
            spec,
            state,
            pre_state,
            withdrawal_count=spec.MAX_WITHDRAWALS_PER_PAYLOAD,
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
    assert max(sweep_indices) < len(state.validators), (
        f"Max validator index {max(sweep_indices)} must exist in registry "
        f"(validators: {len(state.validators)})"
    )

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
    assert max(sweep_indices) < len(state.validators), (
        f"Max validator index {max(sweep_indices)} must exist in registry "
        f"(validators: {len(state.validators)})"
    )

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

    assert builder_index < len(state.builders), "Builder must exist in registry"
    assert max(pending_index, sweep_index) < len(state.validators), (
        f"Max validator index {max(pending_index, sweep_index)} must exist in registry "
        f"(validators: {len(state.validators)})"
    )

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
        - state.builders[0..N-1]: Builders exist in registry with sufficient balance, N = 2 or 1
        - builder_pending_withdrawals: N entries (calculated to leave 1 slot)
        - pending_partial_withdrawals: M entries (capped by MAX_PENDING_PARTIALS)
        - validators[0].withdrawable_epoch: <= current_epoch (sweep eligible)
        - Total builder + pending < MAX_WITHDRAWALS_PER_PAYLOAD

    Note: Builder indices and validator indices intentionally overlap to demonstrate
    that they are separate namespaces.

    Output State Verified:
        - payload_expected_withdrawals: builders + pending + 1 sweep
        - Exactly 1 sweep withdrawal included in the payload
        - Note: Tests the slot allocation between withdrawal types
    """

    assert spec.MAX_WITHDRAWALS_PER_PAYLOAD >= 3, (
        "Test requires MAX_WITHDRAWALS_PER_PAYLOAD to be at least 3"
    )

    num_builders = 2 if spec.MAX_WITHDRAWALS_PER_PAYLOAD >= 4 else 1
    num_pending = spec.MAX_WITHDRAWALS_PER_PAYLOAD - num_builders - 1

    assert num_builders > 0, "Test requires at least 1 builder withdrawal"
    assert num_pending > 0, "Test requires at least 1 pending partial withdrawal"
    assert spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP >= num_pending, (
        "Test requires MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP >= num_pending"
    )

    withdrawal_amount = spec.MIN_ACTIVATION_BALANCE

    builder_indices_list = list(range(num_builders))
    assert max(builder_indices_list) < len(state.builders), (
        f"Max builder index {max(builder_indices_list)} must exist in registry "
        f"(builders: {len(state.builders)})"
    )

    # Validator indices intentionally overlap with builder indices to test separate namespaces
    # pending_indices start from 1 to avoid overlap with regular_index (same validator can't be both)
    pending_indices = list(range(1, 1 + num_pending))
    regular_index = (
        0  # Same numeric index as builder 0, but different entity (validator vs builder)
    )
    all_validator_indices = pending_indices + [regular_index]
    assert max(all_validator_indices) < len(state.validators), (
        f"Max validator index {max(all_validator_indices)} must exist in registry "
        f"(validators: {len(state.validators)})"
    )

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

    expected_total = num_builders + num_pending + 1
    pre_state = state.copy()
    yield from run_gloas_withdrawals_processing(spec, state)

    withdrawals = list(state.payload_expected_withdrawals)
    regular_withdrawals = [w for w in withdrawals if w.validator_index == regular_index]
    assert len(regular_withdrawals) == 1, "Exactly 1 slot should remain for sweep withdrawal"

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=expected_total,
        balances={regular_index: 0},
        withdrawal_index_delta=expected_total,
        builder_pending_delta=-int(num_builders),
        builder_balance_deltas={i: -int(withdrawal_amount) for i in builder_indices_list},
        pending_partial_delta=-int(num_pending),
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

    assert max(builder_indices) < len(state.builders), (
        f"Max builder index {max(builder_indices)} must exist in registry "
        f"(builders: {len(state.builders)})"
    )
    assert regular_index < len(state.validators), "Validator must exist in registry"

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

    assert num_builders <= len(state.builders), (
        f"Test requires at least {num_builders} builders in registry"
    )

    builder_indices_list = list(range(num_builders))

    # Validator indices intentionally overlap with builder indices to test separate namespaces
    # Add multiple regular withdrawals, but only 1 should be processed
    regular_indices = [0, 1, 2]  # Same numeric indices as builders, but different entities
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
    assert builder_index < len(state.builders), "Builder must exist in registry"

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
        assert spec.is_builder_index(w.validator_index), (
            "All withdrawals must be builder withdrawals"
        )

    # Execute
    pre_state = state.copy()
    yield "pre", pre_state
    spec.process_withdrawals(state)
    yield "post", state

    # Calculate what spec actually produces in update_next_withdrawal_validator_index (CAPELLA)
    # expected_result.withdrawals[-1].validator_index has BUILDER_INDEX_FLAG set !!
    assert spec.is_builder_index(expected_result.withdrawals[-1].validator_index), (
        "Last withdrawal must be a builder withdrawal"
    )
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

    # Verify that assert_process_withdrawals raises error for this bug scenario
    # See https://github.com/ethereum/consensus-specs/pull/4835
    with pytest.raises(ValueError, match="BUILDER_INDEX_FLAG"):
        assert_process_withdrawals(
            spec,
            state,
            pre_state,
            withdrawal_count=spec.MAX_WITHDRAWALS_PER_PAYLOAD,
        )
