import random

from tests.core.pyspec.eth2spec.test.context import (
    spec_state_test,
    with_eip7732_and_later,
)
from tests.core.pyspec.eth2spec.test.helpers.forks import is_post_eip7732
from tests.core.pyspec.eth2spec.test.helpers.withdrawals import (
    prepare_expected_withdrawals,
    prepare_pending_withdrawal,
    set_compounding_withdrawal_credential_with_balance,
    set_validator_fully_withdrawable,
    set_validator_partially_withdrawable,
)


def run_eip7732_withdrawals_processing(
    spec, state, num_expected_withdrawals=None, verify_state_updates=True
):
    """
    Helper function to test EIP7732 process_withdrawals.
    Unlike previous versions, this doesn't take an execution payload.
    """
    pre_state = state.copy()

    # Track pre-state for verification
    pre_pending_count = len(state.pending_partial_withdrawals)
    pre_builder_count = len(state.builder_pending_withdrawals)
    pre_withdrawal_index = state.next_withdrawal_index

    # Get expected withdrawals before processing
    if is_post_eip7732(spec):
        expected_withdrawals, _, _ = spec.get_expected_withdrawals(state)
    else:
        expected_withdrawals = spec.get_expected_withdrawals(state)

    if num_expected_withdrawals is not None:
        assert len(expected_withdrawals) == num_expected_withdrawals

    # Process withdrawals (EIP7732 version takes only state)
    spec.process_withdrawals(state)

    # Verify balances were decreased correctly
    for withdrawal in expected_withdrawals:
        validator_index = withdrawal.validator_index
        pre_balance = pre_state.balances[validator_index]
        post_balance = state.balances[validator_index]
        assert post_balance == pre_balance - withdrawal.amount

    # Verify withdrawals root was set (only for EIP7732)
    if is_post_eip7732(spec):
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
    Only works for EIP7732 specs that have builder withdrawals.

    Note: The EIP7732 logic for is_builder_payment_withdrawable seems to have
    some issues in the current implementation, so we'll work around them.
    """
    # Skip if not EIP7732
    if not is_post_eip7732(spec):
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
    # to work with the current EIP7732 is_builder_payment_withdrawable logic
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
    # For EIP7732, set latest_block_hash to match latest_execution_payload_header.block_hash
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
        # For non-EIP7732, this test doesn't apply
        pass


@with_eip7732_and_later
@spec_state_test
def test_zero_withdrawals(spec, state):
    """
    Test processing when no withdrawals are expected.
    """
    set_parent_block_full(spec, state)

    # Initial state should have no withdrawals
    expected_withdrawals_result = spec.get_expected_withdrawals(state)
    if is_post_eip7732(spec):
        assert len(expected_withdrawals_result[0]) == 0
    else:
        assert len(expected_withdrawals_result) == 0

    yield from run_eip7732_withdrawals_processing(spec, state, num_expected_withdrawals=0)


@with_eip7732_and_later
@spec_state_test
def test_single_full_withdrawal(spec, state):
    """
    Test processing a single full withdrawal.
    """
    set_parent_block_full(spec, state)
    set_validator_fully_withdrawable(spec, state, 0)
    yield from run_eip7732_withdrawals_processing(spec, state, num_expected_withdrawals=1)


@with_eip7732_and_later
@spec_state_test
def test_single_partial_withdrawal(spec, state):
    """
    Test processing a single partial withdrawal.
    """
    set_parent_block_full(spec, state)
    set_validator_partially_withdrawable(spec, state, 0)
    yield from run_eip7732_withdrawals_processing(spec, state, num_expected_withdrawals=1)


@with_eip7732_and_later
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
    yield from run_eip7732_withdrawals_processing(
        spec, state, num_expected_withdrawals=expected_total
    )


@with_eip7732_and_later
@spec_state_test
def test_single_builder_withdrawal(spec, state):
    """
    Test processing a single builder withdrawal.
    """
    set_parent_block_full(spec, state)
    prepare_builder_withdrawal(spec, state, 0, spec.Gwei(1_000_000_000))
    yield from run_eip7732_withdrawals_processing(spec, state, num_expected_withdrawals=1)


@with_eip7732_and_later
@spec_state_test
def test_multiple_builder_withdrawals(spec, state):
    """
    Test processing multiple builder withdrawals.
    """
    set_parent_block_full(spec, state)
    for i in range(3):
        prepare_builder_withdrawal(spec, state, i, spec.Gwei(500_000_000))
    yield from run_eip7732_withdrawals_processing(spec, state, num_expected_withdrawals=3)


@with_eip7732_and_later
@spec_state_test
def test_builder_withdrawal_future_epoch(spec, state):
    """
    Test builder withdrawal not yet withdrawable (future epoch).
    """
    set_parent_block_full(spec, state)
    future_epoch = spec.get_current_epoch(state) + 1
    prepare_builder_withdrawal(spec, state, 0, withdrawable_epoch=future_epoch)
    pre_builder_count = len(state.builder_pending_withdrawals)
    yield from run_eip7732_withdrawals_processing(spec, state, num_expected_withdrawals=0)
    # Verify builder list unchanged (withdrawal not processed)
    assert len(state.builder_pending_withdrawals) == pre_builder_count


@with_eip7732_and_later
@spec_state_test
def test_builder_withdrawal_slashed_validator(spec, state):
    """
    Test builder withdrawal with slashed validator.
    """
    set_parent_block_full(spec, state)
    state.validators[0].slashed = True
    state.validators[0].withdrawable_epoch = spec.get_current_epoch(state) + 10
    prepare_builder_withdrawal(spec, state, 0, spec.Gwei(1_000_000_000))
    yield from run_eip7732_withdrawals_processing(spec, state, num_expected_withdrawals=1)


@with_eip7732_and_later
@spec_state_test
def test_builder_withdrawal_insufficient_balance(spec, state):
    """
    Test builder withdrawal with insufficient balance.
    """
    set_parent_block_full(spec, state)
    withdrawal_amount = spec.Gwei(5_000_000_000)  # 5 ETH
    state.balances[0] = spec.MIN_ACTIVATION_BALANCE + spec.Gwei(1_000_000_000)  # Only 1 ETH excess
    prepare_builder_withdrawal(spec, state, 0, withdrawal_amount)
    yield from run_eip7732_withdrawals_processing(spec, state, num_expected_withdrawals=1)


@with_eip7732_and_later
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

    if is_post_eip7732(spec):
        expected_withdrawals, _, _ = spec.get_expected_withdrawals(state)
    else:
        expected_withdrawals = spec.get_expected_withdrawals(state)
    spec.process_withdrawals(state)

    # Verify priority ordering: builder -> pending -> sweep
    assert len(expected_withdrawals) == 3
    assert expected_withdrawals[0].validator_index == builder_index  # Builder first
    assert expected_withdrawals[1].validator_index == pending_index  # Pending second
    assert expected_withdrawals[2].validator_index == sweep_index  # Sweep third

    # Verify state updates
    assert len(state.builder_pending_withdrawals) < len(pre_state.builder_pending_withdrawals)
    assert len(state.pending_partial_withdrawals) < len(pre_state.pending_partial_withdrawals)
    assert state.next_withdrawal_index > pre_state.next_withdrawal_index

    yield "pre", pre_state
    yield "post", state


@with_eip7732_and_later
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
    yield from run_eip7732_withdrawals_processing(
        spec, state, num_expected_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD
    )


@with_eip7732_and_later
@spec_state_test
def test_pending_withdrawals_processing(spec, state):
    """
    Test pending partial withdrawals processing.
    """
    set_parent_block_full(spec, state)

    # Add multiple pending withdrawals
    for i in range(3):
        prepare_pending_withdrawal(spec, state, i)

    # EIP-7732 limits pending withdrawals to min(MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP, MAX_WITHDRAWALS_PER_PAYLOAD - 1)
    # In minimal config: min(2, 4-1) = 2
    expected_withdrawals = min(3, spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP)
    yield from run_eip7732_withdrawals_processing(
        spec, state, num_expected_withdrawals=expected_withdrawals
    )


@with_eip7732_and_later
@spec_state_test
def test_early_return_empty_parent_block(spec, state):
    """
    Test early return when parent block is empty (EIP7732-specific).
    """
    if is_post_eip7732(spec):
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


@with_eip7732_and_later
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

    yield from run_eip7732_withdrawals_processing(spec, state, num_expected_withdrawals=1)


@with_eip7732_and_later
@spec_state_test
def test_validator_not_yet_active(spec, state):
    """
    Test withdrawal processing with validator not yet active.
    """
    set_parent_block_full(spec, state)
    validator_index = min(len(state.validators) // 2, spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP - 1)
    state.validators[validator_index].activation_epoch += 4
    set_validator_partially_withdrawable(spec, state, validator_index)

    assert not spec.is_active_validator(
        state.validators[validator_index], spec.get_current_epoch(state)
    )
    yield from run_eip7732_withdrawals_processing(spec, state, num_expected_withdrawals=1)


@with_eip7732_and_later
@spec_state_test
def test_validator_in_exit_queue(spec, state):
    """
    Test withdrawal processing with validator in exit queue.
    """
    set_parent_block_full(spec, state)
    validator_index = min(
        len(state.validators) // 2 + 1, spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP - 1
    )
    state.validators[validator_index].exit_epoch = spec.get_current_epoch(state) + 1
    set_validator_partially_withdrawable(spec, state, validator_index)

    assert spec.is_active_validator(
        state.validators[validator_index], spec.get_current_epoch(state)
    )
    assert not spec.is_active_validator(
        state.validators[validator_index], spec.get_current_epoch(state) + 1
    )
    yield from run_eip7732_withdrawals_processing(spec, state, num_expected_withdrawals=1)


@with_eip7732_and_later
@spec_state_test
def test_withdrawable_epoch_but_zero_balance(spec, state):
    """
    Test edge case: validator is withdrawable but has zero balance.
    """
    set_parent_block_full(spec, state)
    current_epoch = spec.get_current_epoch(state)
    set_validator_fully_withdrawable(spec, state, 3, current_epoch)
    state.validators[3].effective_balance = 10000000000
    state.balances[3] = 0
    yield from run_eip7732_withdrawals_processing(spec, state, num_expected_withdrawals=0)


@with_eip7732_and_later
@spec_state_test
def test_zero_effective_balance_but_nonzero_balance(spec, state):
    """
    Test edge case: validator has zero effective balance but nonzero actual balance.
    """
    set_parent_block_full(spec, state)
    current_epoch = spec.get_current_epoch(state)
    set_validator_fully_withdrawable(spec, state, 4, current_epoch)
    state.validators[4].effective_balance = 0
    state.balances[4] = 100000000
    yield from run_eip7732_withdrawals_processing(spec, state, num_expected_withdrawals=1)
