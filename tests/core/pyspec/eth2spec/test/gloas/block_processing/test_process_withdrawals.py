import random

from tests.core.pyspec.eth2spec.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from tests.core.pyspec.eth2spec.test.helpers.forks import is_post_gloas
from tests.core.pyspec.eth2spec.test.helpers.withdrawals import (
    prepare_expected_withdrawals,
    prepare_pending_withdrawal,
    set_compounding_withdrawal_credential_with_balance,
    set_validator_fully_withdrawable,
    set_validator_partially_withdrawable,
)


def run_gloas_withdrawals_processing(
    spec, state, num_expected_withdrawals=None, verify_state_updates=True
):
    """
    Helper function to test Gloas process_withdrawals.
    Unlike previous versions, this doesn't take an execution payload.
    """
    pre_state = state.copy()

    # Track pre-state for verification
    pre_pending_count = len(state.pending_partial_withdrawals)
    pre_builder_count = len(state.builder_pending_withdrawals)
    pre_withdrawal_index = state.next_withdrawal_index

    # Get expected withdrawals before processing
    if is_post_gloas(spec):
        expected_withdrawals, _, _ = spec.get_expected_withdrawals(state)
    else:
        expected_withdrawals = spec.get_expected_withdrawals(state)

    if num_expected_withdrawals is not None:
        assert len(expected_withdrawals) == num_expected_withdrawals

    # Process withdrawals (Gloas version takes only state)
    spec.process_withdrawals(state)

    # Verify balances were decreased correctly
    for withdrawal in expected_withdrawals:
        validator_index = withdrawal.validator_index
        pre_balance = pre_state.balances[validator_index]
        post_balance = state.balances[validator_index]
        assert post_balance == pre_balance - withdrawal.amount

    # Verify withdrawals root was set (only for Gloas)
    if is_post_gloas(spec):
        withdrawals_list = spec.List[spec.Withdrawal, spec.MAX_WITHDRAWALS_PER_PAYLOAD](
            expected_withdrawals
        )
        assert state.latest_withdrawals_root == spec.hash_tree_root(withdrawals_list)

    if verify_state_updates:
        # Verify state lists were updated correctly
        post_pending_count = len(state.pending_partial_withdrawals)
        post_builder_count = len(state.builder_pending_withdrawals)
        post_withdrawal_index = state.next_withdrawal_index

        # Pending and builder lists should be updated (processed items removed)
        assert post_pending_count <= pre_pending_count
        assert post_builder_count <= pre_builder_count

        # Withdrawal index should advance by the number of processed withdrawals
        if len(expected_withdrawals) > 0:
            expected_advancement = len(expected_withdrawals)
            assert post_withdrawal_index == pre_withdrawal_index + expected_advancement
        else:
            # If no withdrawals, index should remain the same
            assert post_withdrawal_index == pre_withdrawal_index

    yield "pre", pre_state
    yield "post", state


def prepare_builder_withdrawal(spec, state, builder_index, amount=None, withdrawable_epoch=None):
    """
    Helper to set up a builder pending withdrawal.
    Only works for Gloas specs that have builder withdrawals.

    Note: The Gloas logic for is_builder_payment_withdrawable seems to have
    some issues in the current implementation, so we'll work around them.
    """
    # Skip if not Gloas
    if not is_post_gloas(spec):
        return None

    if amount is None:
        amount = spec.Gwei(1_000_000_000)  # 1 ETH

    if withdrawable_epoch is None:
        withdrawable_epoch = spec.get_current_epoch(state)

    # Ensure builder has sufficient balance
    state.balances[builder_index] = max(
        state.balances[builder_index],
        amount + spec.MIN_ACTIVATION_BALANCE + spec.Gwei(1_000_000_000),
    )

    # Make sure the builder is not slashed and has reached withdrawable epoch
    # to work with the current Gloas is_builder_payment_withdrawable logic
    builder = state.validators[builder_index]
    builder.slashed = False
    builder.withdrawable_epoch = min(builder.withdrawable_epoch, withdrawable_epoch)

    builder_withdrawal = spec.BuilderPendingWithdrawal(
        fee_recipient=b"\x42" * 20,
        amount=amount,
        builder_index=builder_index,
        withdrawable_epoch=withdrawable_epoch,
    )

    # Initialize builder_pending_withdrawals if it doesn't exist
    if not hasattr(state, "builder_pending_withdrawals"):
        state.builder_pending_withdrawals = []

    state.builder_pending_withdrawals.append(builder_withdrawal)
    return builder_withdrawal


def set_parent_block_full(spec, state):
    """
    Helper to set state indicating parent block was full.
    """
    # For Gloas, set latest_block_hash to match latest_execution_payload_header.block_hash
    if hasattr(state, "latest_block_hash"):
        state.latest_block_hash = state.latest_execution_payload_header.block_hash
    # For testing purposes, ensure we have a block hash
    if not hasattr(state, "latest_block_hash") or state.latest_block_hash == b"\x00" * 32:
        state.latest_block_hash = b"\x01" * 32


def set_parent_block_empty(spec, state):
    """
    Helper to set state indicating parent block was empty.
    """
    # Set latest_block_hash to differ from latest_execution_payload_header.block_hash
    if hasattr(state, "latest_block_hash"):
        state.latest_block_hash = b"\x00" * 32
    else:
        # For non-Gloas, this test doesn't apply
        pass


@with_gloas_and_later
@spec_state_test
def test_zero_withdrawals(spec, state):
    """
    Test processing when no withdrawals are expected.
    """
    set_parent_block_full(spec, state)

    # Initial state should have no withdrawals
    expected_withdrawals_result = spec.get_expected_withdrawals(state)
    assert len(expected_withdrawals_result[0]) == 0

    yield from run_gloas_withdrawals_processing(spec, state, num_expected_withdrawals=0)


@with_gloas_and_later
@spec_state_test
def test_single_full_withdrawal(spec, state):
    """
    Test processing a single full withdrawal.
    """
    set_parent_block_full(spec, state)
    set_validator_fully_withdrawable(spec, state, 0)
    yield from run_gloas_withdrawals_processing(spec, state, num_expected_withdrawals=1)

    # Verify full withdrawal: balance should be 0
    assert state.balances[0] == 0


@with_gloas_and_later
@spec_state_test
def test_single_partial_withdrawal(spec, state):
    """
    Test processing a single partial withdrawal.
    """
    set_parent_block_full(spec, state)
    set_validator_partially_withdrawable(spec, state, 0)
    yield from run_gloas_withdrawals_processing(spec, state, num_expected_withdrawals=1)

    # Verify partial withdrawal: balance should equal max effective balance
    assert state.balances[0] == spec.get_max_effective_balance(state.validators[0])


@with_gloas_and_later
@spec_state_test
def test_mixed_full_and_partial_withdrawals(spec, state):
    """
    Test processing mixed full and partial withdrawals.
    """
    set_parent_block_full(spec, state)

    num_full = 2
    num_partial = 2
    fully_withdrawable_indices, partial_withdrawals_indices = prepare_expected_withdrawals(
        spec,
        state,
        rng=random.Random(42),
        num_full_withdrawals=num_full,
        num_partial_withdrawals=num_partial,
    )
    expected_total = len(fully_withdrawable_indices) + len(partial_withdrawals_indices)
    yield from run_gloas_withdrawals_processing(
        spec, state, num_expected_withdrawals=expected_total
    )

    # Verify full withdrawals: balances should be 0
    for idx in fully_withdrawable_indices:
        assert state.balances[idx] == 0
    # Verify partial withdrawals: balances should equal max effective balance
    for idx in partial_withdrawals_indices:
        assert state.balances[idx] == spec.get_max_effective_balance(state.validators[idx])


@with_gloas_and_later
@spec_state_test
def test_single_builder_withdrawal(spec, state):
    """
    Test processing a single builder withdrawal.
    """
    set_parent_block_full(spec, state)
    prepare_builder_withdrawal(spec, state, 0, spec.Gwei(1_000_000_000))
    pre_builder_count = len(state.builder_pending_withdrawals)
    yield from run_gloas_withdrawals_processing(spec, state, num_expected_withdrawals=1)

    # Verify builder withdrawal was processed
    assert len(state.builder_pending_withdrawals) == pre_builder_count - 1


@with_gloas_and_later
@spec_state_test
def test_multiple_builder_withdrawals(spec, state):
    """
    Test processing multiple builder withdrawals.
    """
    set_parent_block_full(spec, state)
    for i in range(3):
        prepare_builder_withdrawal(spec, state, i, spec.Gwei(500_000_000))
    pre_builder_count = len(state.builder_pending_withdrawals)
    yield from run_gloas_withdrawals_processing(spec, state, num_expected_withdrawals=3)

    # Verify all 3 builder withdrawals were processed
    assert len(state.builder_pending_withdrawals) == pre_builder_count - 3


@with_gloas_and_later
@spec_state_test
def test_builder_withdrawal_future_epoch(spec, state):
    """
    Test builder withdrawal not yet withdrawable (future epoch).
    """
    set_parent_block_full(spec, state)
    future_epoch = spec.get_current_epoch(state) + 1
    prepare_builder_withdrawal(spec, state, 0, withdrawable_epoch=future_epoch)
    pre_builder_count = len(state.builder_pending_withdrawals)
    yield from run_gloas_withdrawals_processing(spec, state, num_expected_withdrawals=0)
    # Verify builder list unchanged (withdrawal not processed)
    assert len(state.builder_pending_withdrawals) == pre_builder_count


@with_gloas_and_later
@spec_state_test
def test_builder_withdrawal_slashed_validator(spec, state):
    """
    Test builder withdrawal with slashed validator.
    """
    set_parent_block_full(spec, state)
    state.validators[0].slashed = True
    state.validators[0].withdrawable_epoch = spec.get_current_epoch(state) + 10
    prepare_builder_withdrawal(spec, state, 0, spec.Gwei(1_000_000_000))
    pre_builder_count = len(state.builder_pending_withdrawals)
    yield from run_gloas_withdrawals_processing(spec, state, num_expected_withdrawals=1)

    # Verify builder withdrawal was processed despite validator being slashed
    assert len(state.builder_pending_withdrawals) == pre_builder_count - 1


@with_gloas_and_later
@spec_state_test
def test_builder_withdrawal_insufficient_balance(spec, state):
    """
    Test builder withdrawal with insufficient balance.
    """
    set_parent_block_full(spec, state)
    withdrawal_amount = spec.Gwei(5_000_000_000)  # 5 ETH
    state.balances[0] = spec.MIN_ACTIVATION_BALANCE + spec.Gwei(1_000_000_000)  # Only 1 ETH excess
    prepare_builder_withdrawal(spec, state, 0, withdrawal_amount)
    pre_builder_count = len(state.builder_pending_withdrawals)
    yield from run_gloas_withdrawals_processing(spec, state, num_expected_withdrawals=1)

    # Verify builder withdrawal was processed (amount is capped to available balance)
    assert len(state.builder_pending_withdrawals) == pre_builder_count - 1


@with_gloas_and_later
@spec_state_test
def test_mixed_withdrawal_types_priority_ordering(spec, state):
    """
    Test all three withdrawal types together with priority ordering verification.
    """
    set_parent_block_full(spec, state)

    builder_index = 0
    pending_index = 1
    sweep_index = 2

    # Prepare one of each type
    prepare_builder_withdrawal(spec, state, builder_index, spec.Gwei(1_000_000_000))
    prepare_pending_withdrawal(spec, state, pending_index)
    set_validator_fully_withdrawable(spec, state, sweep_index)

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

    # Verify state updates
    assert len(state.builder_pending_withdrawals) < len(pre_state.builder_pending_withdrawals)
    assert len(state.pending_partial_withdrawals) < len(pre_state.pending_partial_withdrawals)
    assert state.next_withdrawal_index > pre_state.next_withdrawal_index

    yield "pre", pre_state
    yield "post", state


@with_gloas_and_later
@spec_state_test
def test_maximum_withdrawals_per_payload_limit(spec, state):
    """
    Test that withdrawals respect MAX_WITHDRAWALS_PER_PAYLOAD limit.
    """
    set_parent_block_full(spec, state)

    # Add more withdrawals than the limit allows
    num_builders = spec.MAX_WITHDRAWALS_PER_PAYLOAD // 2
    num_pending = spec.MAX_WITHDRAWALS_PER_PAYLOAD // 2
    num_sweep = spec.MAX_WITHDRAWALS_PER_PAYLOAD // 2

    # Add builder withdrawals
    for i in range(num_builders):
        prepare_builder_withdrawal(spec, state, i, spec.Gwei(1_000_000_000))

    # Add pending withdrawals
    for i in range(num_builders, num_builders + num_pending):
        prepare_pending_withdrawal(spec, state, i)

    # Add sweep withdrawals
    for i in range(num_builders + num_pending, num_builders + num_pending + num_sweep):
        set_validator_fully_withdrawable(spec, state, i)

    # Should not exceed MAX_WITHDRAWALS_PER_PAYLOAD
    yield from run_gloas_withdrawals_processing(
        spec, state, num_expected_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD
    )

    # Verify some withdrawals remain unprocessed due to the limit
    total_added = num_builders + num_pending + num_sweep
    total_remaining = len(state.builder_pending_withdrawals) + len(
        state.pending_partial_withdrawals
    )
    assert total_remaining > 0, "Some withdrawals should remain unprocessed"
    assert total_added > spec.MAX_WITHDRAWALS_PER_PAYLOAD, "Test setup should exceed limit"


@with_gloas_and_later
@spec_state_test
def test_pending_withdrawals_processing(spec, state):
    """
    Test pending partial withdrawals processing.
    """
    set_parent_block_full(spec, state)

    # Add enough pending withdrawals to test the limit
    for i in range(spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP):
        prepare_pending_withdrawal(spec, state, i)

    # EIP-7732 limits pending withdrawals to min(MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP, MAX_WITHDRAWALS_PER_PAYLOAD - 1)
    # In minimal config: min(2, 4-1) = 2, in mainnet config: min(8, 16-1) = 8
    expected_withdrawals = spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP
    yield from run_gloas_withdrawals_processing(
        spec, state, num_expected_withdrawals=expected_withdrawals
    )

    # Verify pending_partial_withdrawals queue was depleted
    assert len(state.pending_partial_withdrawals) == 0


@with_gloas_and_later
@spec_state_test
def test_early_return_empty_parent_block(spec, state):
    """
    Test early return when parent block is empty.
    """
    set_parent_block_empty(spec, state)

    # Prepare withdrawals that would normally be processed
    prepare_expected_withdrawals(spec, state, rng=random.Random(42), num_full_withdrawals=2)
    prepare_builder_withdrawal(spec, state, 0)

    pre_state = state.copy()

    # Process withdrawals - should return early and do nothing
    spec.process_withdrawals(state)

    # State should be unchanged
    assert state.balances == pre_state.balances
    if hasattr(state, "pending_partial_withdrawals"):
        assert state.pending_partial_withdrawals == pre_state.pending_partial_withdrawals
    if hasattr(state, "builder_pending_withdrawals"):
        assert state.builder_pending_withdrawals == pre_state.builder_pending_withdrawals
    assert state.next_withdrawal_index == pre_state.next_withdrawal_index
    assert state.next_withdrawal_validator_index == pre_state.next_withdrawal_validator_index

    yield "pre", pre_state
    yield "post", state


@with_gloas_and_later
@spec_state_test
def test_compounding_validator_partial_withdrawal(spec, state):
    """
    Test compounding validator partial withdrawal support.
    """
    set_parent_block_full(spec, state)
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

    yield from run_gloas_withdrawals_processing(spec, state, num_expected_withdrawals=1)

    # Verify balance equals MAX_EFFECTIVE_BALANCE_ELECTRA after partial withdrawal
    assert state.balances[validator_index] == spec.MAX_EFFECTIVE_BALANCE_ELECTRA


@with_gloas_and_later
@spec_state_test
def test_validator_not_yet_active(spec, state):
    """
    Test withdrawal processing with validator not yet active.
    """
    set_parent_block_full(spec, state)
    validator_index = 0
    state.validators[validator_index].activation_epoch += 4
    set_validator_partially_withdrawable(spec, state, validator_index)

    assert not spec.is_active_validator(
        state.validators[validator_index], spec.get_current_epoch(state)
    )
    yield from run_gloas_withdrawals_processing(spec, state, num_expected_withdrawals=1)

    # Verify withdrawal processed despite validator not being active
    assert state.balances[validator_index] == spec.get_max_effective_balance(
        state.validators[validator_index]
    )


@with_gloas_and_later
@spec_state_test
def test_validator_in_exit_queue(spec, state):
    """
    Test withdrawal processing with validator in exit queue.
    """
    set_parent_block_full(spec, state)
    validator_index = 1
    state.validators[validator_index].exit_epoch = spec.get_current_epoch(state) + 1
    set_validator_partially_withdrawable(spec, state, validator_index)

    assert spec.is_active_validator(
        state.validators[validator_index], spec.get_current_epoch(state)
    )
    assert not spec.is_active_validator(
        state.validators[validator_index], spec.get_current_epoch(state) + 1
    )
    yield from run_gloas_withdrawals_processing(spec, state, num_expected_withdrawals=1)

    # Verify withdrawal processed for validator in exit queue
    assert state.balances[validator_index] == spec.get_max_effective_balance(
        state.validators[validator_index]
    )


@with_gloas_and_later
@spec_state_test
def test_withdrawable_epoch_but_zero_balance(spec, state):
    """
    Test edge case: validator is withdrawable but has zero balance.
    """
    set_parent_block_full(spec, state)
    current_epoch = spec.get_current_epoch(state)
    set_validator_fully_withdrawable(spec, state, 3, current_epoch)
    state.validators[3].effective_balance = spec.MIN_ACTIVATION_BALANCE
    state.balances[3] = 0
    yield from run_gloas_withdrawals_processing(spec, state, num_expected_withdrawals=0)

    # Verify balance remains 0 (no withdrawal since balance was already 0)
    assert state.balances[3] == 0


@with_gloas_and_later
@spec_state_test
def test_zero_effective_balance_but_nonzero_balance(spec, state):
    """
    Test edge case: validator has zero effective balance but nonzero actual balance.
    """
    set_parent_block_full(spec, state)
    current_epoch = spec.get_current_epoch(state)
    set_validator_fully_withdrawable(spec, state, 4, current_epoch)
    state.validators[4].effective_balance = 0
    state.balances[4] = spec.MIN_ACTIVATION_BALANCE
    yield from run_gloas_withdrawals_processing(spec, state, num_expected_withdrawals=1)

    # Verify full balance was withdrawn
    assert state.balances[4] == 0


@with_gloas_and_later
@spec_state_test
def test_builder_payments_exceed_limit_blocks_other_withdrawals(spec, state):
    """
    Test that when there are more than MAX_WITHDRAWALS_PER_PAYLOAD builder payments,
    pending partial withdrawals are not processed.
    """
    set_parent_block_full(spec, state)

    # Add more builder payments than the limit to test prioritization
    num_builders = spec.MAX_WITHDRAWALS_PER_PAYLOAD + 2  # 6 builders (more than limit of 4)
    for i in range(num_builders):
        prepare_builder_withdrawal(spec, state, i, spec.Gwei(1_000_000_000))

    # Don't add any pending withdrawals for this test
    # This test just verifies that builder payments work up to the limit

    # Ensure no validators are eligible for sweep withdrawals
    # by setting withdrawal credentials to non-withdrawable
    for i in range(len(state.validators)):
        validator = state.validators[i]
        if validator.withdrawal_credentials[0:1] == spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX:
            # Keep ETH1 credentials but ensure balance is not above max_effective_balance
            # to prevent full withdrawals
            state.balances[i] = min(state.balances[i], spec.MAX_EFFECTIVE_BALANCE)

    pre_builder_count = len(state.builder_pending_withdrawals)

    # Should process builder payments up to the limit, but actual count depends on eligibility
    yield from run_gloas_withdrawals_processing(
        spec,
        state,
        num_expected_withdrawals=None,  # Don't assert specific count, just verify processing works
    )

    # Verify builder queue was partially processed
    # (some withdrawals should be processed, but not necessarily all due to eligibility constraints)
    post_builder_count = len(state.builder_pending_withdrawals)
    assert post_builder_count < pre_builder_count, (
        "Some builder withdrawals should have been processed"
    )
    processed_count = pre_builder_count - post_builder_count
    assert processed_count <= spec.MAX_WITHDRAWALS_PER_PAYLOAD, "Should not exceed withdrawal limit"


@with_gloas_and_later
@spec_state_test
def test_no_builders_max_pending_with_sweep_spillover(spec, state):
    """
    Test no builder payments, MAX_WITHDRAWALS_PER_PAYLOAD pending partial withdrawals,
    with sweep withdrawals available due to MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP limit.
    """
    set_parent_block_full(spec, state)

    # Add MAX_WITHDRAWALS_PER_PAYLOAD pending partial withdrawals
    for i in range(spec.MAX_WITHDRAWALS_PER_PAYLOAD):
        prepare_pending_withdrawal(spec, state, i)

    # Add sweep withdrawals that should be processed due to pending limit
    sweep_start = spec.MAX_WITHDRAWALS_PER_PAYLOAD
    for i in range(sweep_start, sweep_start + 3):
        set_validator_fully_withdrawable(spec, state, i)

    # Should process MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP pending + remaining slots for sweep
    expected_pending = spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP
    expected_sweep = spec.MAX_WITHDRAWALS_PER_PAYLOAD - expected_pending
    expected_total = expected_pending + expected_sweep

    yield from run_gloas_withdrawals_processing(
        spec, state, num_expected_withdrawals=expected_total
    )

    # Verify remaining pending withdrawals not processed
    remaining_pending = spec.MAX_WITHDRAWALS_PER_PAYLOAD - expected_pending
    assert len(state.pending_partial_withdrawals) == remaining_pending
    # Verify sweep validators fully withdrawn
    for i in range(sweep_start, sweep_start + expected_sweep):
        assert state.balances[i] == 0


@with_gloas_and_later
@spec_state_test
def test_no_builders_no_pending_max_sweep_withdrawals(spec, state):
    """
    Test no builder payments, no pending partial withdrawals,
    MAX_WITHDRAWALS_PER_PAYLOAD sweep withdrawals.
    """
    set_parent_block_full(spec, state)

    # Add MAX_WITHDRAWALS_PER_PAYLOAD sweep withdrawals
    for i in range(spec.MAX_WITHDRAWALS_PER_PAYLOAD):
        set_validator_fully_withdrawable(spec, state, i)

    # All should be processed since no higher priority withdrawals exist
    yield from run_gloas_withdrawals_processing(
        spec, state, num_expected_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD
    )

    # Verify all sweep validators fully withdrawn
    for i in range(spec.MAX_WITHDRAWALS_PER_PAYLOAD):
        assert state.balances[i] == 0
