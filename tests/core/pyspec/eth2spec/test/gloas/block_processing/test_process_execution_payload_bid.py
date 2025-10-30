from eth2spec.test.context import (
    always_bls,
    spec_state_test,
    with_gloas_and_later,
)
from eth2spec.test.helpers.block import build_empty_block_for_next_slot
from eth2spec.test.helpers.keys import privkeys
from eth2spec.test.helpers.withdrawals import (
    set_builder_withdrawal_credential,
    set_builder_withdrawal_credential_with_balance,
)


def run_execution_payload_bid_processing(spec, state, block, valid=True):
    """
    Run ``process_execution_payload_bid``, yielding:
    - pre-state ('pre')
    - block ('block')
    - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    yield "pre", state
    yield "block", block

    if not valid:
        try:
            spec.process_execution_payload_bid(state, block)
            assert False, "Expected AssertionError but none was raised"
        except AssertionError:
            pass
        yield "post", None
        return

    spec.process_execution_payload_bid(state, block)
    yield "post", state


def prepare_signed_execution_payload_bid(
    spec,
    state,
    builder_index=None,
    value=None,
    slot=None,
    parent_block_hash=None,
    parent_block_root=None,
    fee_recipient=None,
    gas_limit=None,
    block_hash=None,
    blob_kzg_commitments_root=None,
    valid_signature=True,
):
    """
    Helper to create a signed execution payload bid with customizable parameters.
    If slot is None, the current state slot will be used.
    """
    if slot is None:
        slot = state.slot
    assert slot >= state.slot
    spec.process_slots(state, slot)

    if builder_index is None:
        builder_index = spec.get_beacon_proposer_index(state)

    if parent_block_hash is None:
        parent_block_hash = state.latest_block_hash

    if parent_block_root is None:
        parent_block_root = state.latest_block_header.hash_tree_root()

    if fee_recipient is None:
        fee_recipient = spec.ExecutionAddress()

    if gas_limit is None:
        gas_limit = spec.uint64(30000000)

    if block_hash is None:
        block_hash = spec.Hash32()

    if value is None:
        value = spec.Gwei(0)

    # Validation: if builder index equals proposer index, value must be 0
    proposer_index = spec.get_beacon_proposer_index(state)
    if builder_index == proposer_index and value != 0:
        raise ValueError("Self-builder (builder_index == proposer_index) must use zero value")

    if blob_kzg_commitments_root is None:
        kzg_list = spec.ProgressiveList[spec.KZGCommitment]()
        blob_kzg_commitments_root = kzg_list.hash_tree_root()

    bid = spec.ExecutionPayloadBid(
        parent_block_hash=parent_block_hash,
        parent_block_root=parent_block_root,
        block_hash=block_hash,
        fee_recipient=fee_recipient,
        gas_limit=gas_limit,
        builder_index=builder_index,
        slot=slot,
        value=value,
        blob_kzg_commitments_root=blob_kzg_commitments_root,
    )

    if valid_signature:
        # Check if this is a self-build case
        proposer_index = spec.get_beacon_proposer_index(state)
        if builder_index == proposer_index:
            # Self-builds must use G2_POINT_AT_INFINITY
            signature = spec.bls.G2_POINT_AT_INFINITY
        else:
            # External builders use real signatures
            privkey = privkeys[builder_index]
            signature = spec.get_execution_payload_bid_signature(state, bid, privkey)
    else:
        # Invalid signature
        signature = spec.BLSSignature()

    return spec.SignedExecutionPayloadBid(
        message=bid,
        signature=signature,
    )


def make_validator_builder(spec, state, validator_index):
    """
    Helper to make a validator a builder by setting builder withdrawal credentials.
    """
    set_builder_withdrawal_credential(spec, state, validator_index)


def prepare_block_with_execution_payload_bid(spec, state, **bid_kwargs):
    """
    Helper that properly creates a block with execution payload bid,
    handling the slot advancement correctly.
    """
    # Create block first (this advances state.slot)
    block = build_empty_block_for_next_slot(spec, state)

    # Ensure the bid matches the block's context
    bid_kwargs["slot"] = block.slot
    bid_kwargs["parent_block_root"] = block.parent_root

    # Default builder_index to the block's proposer_index if not specified
    if "builder_index" not in bid_kwargs:
        bid_kwargs["builder_index"] = block.proposer_index

    # Now create bid with the correct slot and parent root
    signed_bid = prepare_signed_execution_payload_bid(spec, state, **bid_kwargs)
    block.body.signed_execution_payload_bid = signed_bid

    return block, signed_bid


def prepare_block_with_non_proposer_builder(spec, state):
    """
    Helper that creates a block and sets up a non-proposer builder for non-self-building tests.
    Returns (block, builder_index) where builder_index != block.proposer_index.
    """
    # Create block first (this advances state.slot)
    block = build_empty_block_for_next_slot(spec, state)

    # Use a different validator as builder (clearly not self-building)
    builder_index = (block.proposer_index + 1) % len(state.validators)
    make_validator_builder(spec, state, builder_index)

    # Ensure the contract is satisfied
    assert builder_index != block.proposer_index, "Helper must return non-self-building scenario"

    return block, builder_index


#
# Valid cases
#


@with_gloas_and_later
@spec_state_test
def test_process_execution_payload_bid_valid_self_build(spec, state):
    """
    Test valid self-building scenario (proposer building their own block with zero value)
    """
    block, signed_bid = prepare_block_with_execution_payload_bid(spec, state, value=spec.Gwei(0))

    yield from run_execution_payload_bid_processing(spec, state, block)


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_bid_valid_builder(spec, state):
    """
    Test valid builder scenario with registered builder and non-zero value
    """
    block, builder_index = prepare_block_with_non_proposer_builder(spec, state)

    # Ensure builder has sufficient balance
    value = spec.Gwei(1000000)  # 0.001 ETH
    required_balance = value + spec.MIN_ACTIVATION_BALANCE
    state.balances[builder_index] = required_balance

    pre_balance = state.balances[builder_index]
    pre_pending_payments_len = len(
        [p for p in state.builder_pending_payments if p.withdrawal.amount > 0]
    )

    # Create bid with this non-proposer builder
    signed_bid = prepare_signed_execution_payload_bid(
        spec,
        state,
        builder_index=builder_index,
        value=value,
        slot=block.slot,
        parent_block_root=block.parent_root,
    )

    block.body.signed_execution_payload_bid = signed_bid

    yield from run_execution_payload_bid_processing(spec, state, block)

    # Verify state updates
    assert state.latest_execution_payload_bid == signed_bid.message

    # Verify builder balance is still the same
    assert state.balances[builder_index] == pre_balance

    # Verify pending payment was recorded
    slot_index = spec.SLOTS_PER_EPOCH + (signed_bid.message.slot % spec.SLOTS_PER_EPOCH)
    pending_payment = state.builder_pending_payments[slot_index]
    assert pending_payment.withdrawal.amount == value
    assert pending_payment.withdrawal.builder_index == builder_index
    assert pending_payment.withdrawal.withdrawable_epoch == spec.FAR_FUTURE_EPOCH
    assert pending_payment.weight == 0

    # Verify pending payments count increased by 1
    post_pending_payments_len = len(
        [p for p in state.builder_pending_payments if p.withdrawal.amount > 0]
    )
    assert post_pending_payments_len == pre_pending_payments_len + 1


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_bid_valid_builder_zero_value(spec, state):
    """
    Test valid builder scenario with registered builder and zero value
    """
    block, builder_index = prepare_block_with_non_proposer_builder(spec, state)

    # Create bid with this non-proposer builder
    signed_bid = prepare_signed_execution_payload_bid(
        spec,
        state,
        builder_index=builder_index,
        value=spec.Gwei(0),
        slot=block.slot,
        parent_block_root=block.parent_root,
    )

    block.body.signed_execution_payload_bid = signed_bid

    yield from run_execution_payload_bid_processing(spec, state, block)


#
# Invalid signature tests
#


@with_gloas_and_later
@spec_state_test
def test_process_execution_payload_bid_invalid_signature(spec, state):
    """
    Test invalid signature fails
    """
    proposer_index = spec.get_beacon_proposer_index(state)

    block, signed_bid = prepare_block_with_execution_payload_bid(
        spec, state, builder_index=proposer_index, valid_signature=False
    )

    yield from run_execution_payload_bid_processing(spec, state, block, valid=False)


#
# Builder validation tests
#


@with_gloas_and_later
@spec_state_test
def test_process_execution_payload_bid_inactive_builder(spec, state):
    """
    Test inactive builder fails
    """
    block, builder_index = prepare_block_with_non_proposer_builder(spec, state)

    # Make builder inactive by setting exit epoch
    state.validators[builder_index].exit_epoch = spec.get_current_epoch(state)

    # Ensure builder has sufficient balance for the bid to avoid balance check failure
    value = spec.Gwei(1000000)
    required_balance = value + spec.MIN_ACTIVATION_BALANCE
    state.balances[builder_index] = required_balance

    # Create bid with this non-proposer builder
    signed_bid = prepare_signed_execution_payload_bid(
        spec,
        state,
        builder_index=builder_index,
        value=value,
        slot=block.slot,
        parent_block_root=block.parent_root,
    )

    block.body.signed_execution_payload_bid = signed_bid

    yield from run_execution_payload_bid_processing(spec, state, block, valid=False)


@with_gloas_and_later
@spec_state_test
def test_process_execution_payload_bid_slashed_builder(spec, state):
    """
    Test slashed builder fails
    """
    block, builder_index = prepare_block_with_non_proposer_builder(spec, state)

    # Slash the builder
    state.validators[builder_index].slashed = True

    # Ensure builder has sufficient balance for the bid to avoid balance check failure
    value = spec.Gwei(1000000)
    required_balance = value + spec.MIN_ACTIVATION_BALANCE
    state.balances[builder_index] = required_balance

    # Create bid with this non-proposer builder
    signed_bid = prepare_signed_execution_payload_bid(
        spec,
        state,
        builder_index=builder_index,
        value=value,
        slot=block.slot,
        parent_block_root=block.parent_root,
    )

    block.body.signed_execution_payload_bid = signed_bid

    yield from run_execution_payload_bid_processing(spec, state, block, valid=False)


@with_gloas_and_later
@spec_state_test
def test_process_execution_payload_bid_self_build_non_zero_value(spec, state):
    """
    Test self-builder with non-zero value fails (builder_index == proposer_index but value > 0)
    """
    block = build_empty_block_for_next_slot(spec, state)
    kzg_list = spec.ProgressiveList[spec.KZGCommitment]()
    blob_kzg_commitments_root = kzg_list.hash_tree_root()

    bid = spec.ExecutionPayloadBid(
        parent_block_hash=state.latest_block_hash,
        parent_block_root=block.parent_root,
        block_hash=spec.Hash32(),
        fee_recipient=spec.ExecutionAddress(),
        gas_limit=spec.uint64(30000000),
        builder_index=block.proposer_index,  # Same as proposer (self-build)
        slot=block.slot,
        value=1,
        blob_kzg_commitments_root=blob_kzg_commitments_root,
    )

    # Sign the bid
    privkey = privkeys[block.proposer_index]
    signature = spec.get_execution_payload_bid_signature(state, bid, privkey)

    signed_bid = spec.SignedExecutionPayloadBid(
        message=bid,
        signature=signature,
    )

    block.body.signed_execution_payload_bid = signed_bid

    yield from run_execution_payload_bid_processing(spec, state, block, valid=False)


@with_gloas_and_later
@spec_state_test
def test_process_execution_payload_bid_non_builder_non_zero_value(spec, state):
    """
    Test non-builder attempting non-zero value fails
    """
    proposer_index = spec.get_beacon_proposer_index(state)

    # Ensure builder has sufficient balance for the bid to avoid balance check failure
    value = spec.Gwei(1000000)
    required_balance = value + spec.MIN_ACTIVATION_BALANCE
    state.balances[proposer_index] = required_balance

    # Don't make proposer a builder, but try non-zero value
    block, signed_bid = prepare_block_with_execution_payload_bid(
        spec,
        state,
        builder_index=proposer_index,
        value=value,  # Non-zero value should fail for non-builder
    )

    yield from run_execution_payload_bid_processing(spec, state, block, valid=False)


@with_gloas_and_later
@spec_state_test
def test_process_execution_payload_bid_non_builder_wrong_proposer(spec, state):
    """
    Test non-builder with wrong proposer index fails
    """
    proposer_index = spec.get_beacon_proposer_index(state)
    other_index = (proposer_index + 1) % len(state.validators)

    # Non-builder but not the proposer
    block, signed_bid = prepare_block_with_execution_payload_bid(
        spec, state, builder_index=other_index, value=spec.Gwei(0)
    )

    yield from run_execution_payload_bid_processing(spec, state, block, valid=False)


#
# Balance validation tests
#


@with_gloas_and_later
@spec_state_test
def test_process_execution_payload_bid_insufficient_balance(spec, state):
    """
    Test insufficient balance for bid fails
    """
    block, builder_index = prepare_block_with_non_proposer_builder(spec, state)

    value = spec.Gwei(1000000)  # 0.001 ETH
    # Set balance too low
    state.balances[builder_index] = value - 1

    # Create bid with this non-proposer builder
    signed_bid = prepare_signed_execution_payload_bid(
        spec,
        state,
        builder_index=builder_index,
        value=value,
        slot=block.slot,
        parent_block_root=block.parent_root,
    )

    block.body.signed_execution_payload_bid = signed_bid

    yield from run_execution_payload_bid_processing(spec, state, block, valid=False)


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_bid_excess_balance(spec, state):
    """
    Test builder with excess balance (2048.25 ETH) can submit bid for 2016.25 ETH
    Edge case where bid limit depends on builder's balance, not effective balance
    """
    block, builder_index = prepare_block_with_non_proposer_builder(spec, state)

    # Set up builder with excess balance as requested by reviewer
    excess_balance = spec.Gwei(2048250000000)  # 2048.25 ETH in Gwei
    bid_value = spec.Gwei(2016250000000)  # 2016.25 ETH in Gwei

    # Use the helper function to set up builder with specific balance
    set_builder_withdrawal_credential_with_balance(
        spec,
        state,
        builder_index,
        balance=excess_balance,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,  # Standard max effective balance
    )

    pre_balance = state.balances[builder_index]
    pre_pending_payments_len = len(
        [p for p in state.builder_pending_payments if p.withdrawal.amount > 0]
    )

    # Create bid with this non-proposer builder
    signed_bid = prepare_signed_execution_payload_bid(
        spec,
        state,
        builder_index=builder_index,
        value=bid_value,
        slot=block.slot,
        parent_block_root=block.parent_root,
    )

    block.body.signed_execution_payload_bid = signed_bid

    yield from run_execution_payload_bid_processing(spec, state, block)

    # Verify state updates
    assert state.latest_execution_payload_bid == signed_bid.message

    # Verify builder balance is still the same (payment is pending)
    assert state.balances[builder_index] == pre_balance

    # Verify pending payment was recorded
    slot_index = spec.SLOTS_PER_EPOCH + (signed_bid.message.slot % spec.SLOTS_PER_EPOCH)
    pending_payment = state.builder_pending_payments[slot_index]
    assert pending_payment.withdrawal.amount == bid_value
    assert pending_payment.withdrawal.builder_index == builder_index
    assert pending_payment.withdrawal.withdrawable_epoch == spec.FAR_FUTURE_EPOCH
    assert pending_payment.weight == 0

    # Verify pending payments count increased by 1
    post_pending_payments_len = len(
        [p for p in state.builder_pending_payments if p.withdrawal.amount > 0]
    )
    assert post_pending_payments_len == pre_pending_payments_len + 1


@with_gloas_and_later
@spec_state_test
def test_process_execution_payload_bid_insufficient_balance_with_pending_payments(spec, state):
    """
    Test builder with sufficient balance for bid alone but insufficient when considering pending payments and min activation balance
    """
    block, builder_index = prepare_block_with_non_proposer_builder(spec, state)

    # Set up scenario: balance=32000000000 + 1000, bid=600, existing_pending=500
    # Total needed: 600 + 500 + 32000000000 = 32000001100 > 32000001000 (should fail)
    balance = spec.MIN_ACTIVATION_BALANCE + spec.Gwei(1000)  # 32 ETH + 1000 gwei
    bid_amount = spec.Gwei(600)
    existing_pending = spec.Gwei(500)

    state.balances[builder_index] = balance

    # Create existing pending payment for this builder
    slot_index = 5  # Some slot in first epoch
    state.builder_pending_payments[slot_index] = spec.BuilderPendingPayment(
        weight=spec.Gwei(0),
        withdrawal=spec.BuilderPendingWithdrawal(
            fee_recipient=spec.ExecutionAddress(),
            amount=existing_pending,
            builder_index=builder_index,
            withdrawable_epoch=spec.Epoch(0),
        ),
    )

    # Create bid with this non-proposer builder
    signed_bid = prepare_signed_execution_payload_bid(
        spec,
        state,
        builder_index=builder_index,
        value=bid_amount,
        slot=block.slot,
        parent_block_root=block.parent_root,
    )

    block.body.signed_execution_payload_bid = signed_bid

    yield from run_execution_payload_bid_processing(spec, state, block, valid=False)


@with_gloas_and_later
@spec_state_test
def test_process_execution_payload_bid_sufficient_balance_with_pending_payments(spec, state):
    """
    Test builder with sufficient balance for both bid and existing pending payments
    """
    block, builder_index = prepare_block_with_non_proposer_builder(spec, state)

    # Set up scenario: balance=2000, bid=600, existing_pending=500, min_activation=32ETH
    # Total needed: 600 + 500 + 32000000000 = ~32.0011 ETH < 2000 ETH (should pass)
    balance = spec.Gwei(2000000000000)  # 2000 ETH
    bid_amount = spec.Gwei(600)
    existing_pending = spec.Gwei(500)

    state.balances[builder_index] = balance

    # Create existing pending payment for this builder
    slot_index = 5  # Some slot in first epoch
    state.builder_pending_payments[slot_index] = spec.BuilderPendingPayment(
        weight=spec.Gwei(0),
        withdrawal=spec.BuilderPendingWithdrawal(
            fee_recipient=spec.ExecutionAddress(),
            amount=existing_pending,
            builder_index=builder_index,
            withdrawable_epoch=spec.Epoch(0),
        ),
    )

    pre_balance = state.balances[builder_index]
    pre_pending_payments_len = len(
        [p for p in state.builder_pending_payments if p.withdrawal.amount > 0]
    )

    # Create bid with this non-proposer builder
    signed_bid = prepare_signed_execution_payload_bid(
        spec,
        state,
        builder_index=builder_index,
        value=bid_amount,
        slot=block.slot,
        parent_block_root=block.parent_root,
    )

    block.body.signed_execution_payload_bid = signed_bid

    yield from run_execution_payload_bid_processing(spec, state, block)

    # Verify state updates
    assert state.latest_execution_payload_bid == signed_bid.message

    # Verify builder balance is still the same (payment is pending)
    assert state.balances[builder_index] == pre_balance

    # Verify new pending payment was recorded
    slot_index_new = spec.SLOTS_PER_EPOCH + (signed_bid.message.slot % spec.SLOTS_PER_EPOCH)
    pending_payment = state.builder_pending_payments[slot_index_new]
    assert pending_payment.withdrawal.amount == bid_amount
    assert pending_payment.withdrawal.builder_index == builder_index
    assert pending_payment.withdrawal.withdrawable_epoch == spec.FAR_FUTURE_EPOCH
    assert pending_payment.weight == 0

    # Verify pending payments count increased by 1 (now we have 2 total)
    post_pending_payments_len = len(
        [p for p in state.builder_pending_payments if p.withdrawal.amount > 0]
    )
    assert post_pending_payments_len == pre_pending_payments_len + 1


@with_gloas_and_later
@spec_state_test
def test_process_execution_payload_bid_insufficient_balance_with_pending_withdrawals(spec, state):
    """
    Test builder with sufficient balance for bid alone but insufficient when considering pending withdrawals and min activation balance
    """
    block, builder_index = prepare_block_with_non_proposer_builder(spec, state)

    # Set up scenario: balance=32000000000 + 1000, bid=600, existing_withdrawal=500
    # Total needed: 600 + 500 + 32000000000 = 32000001100 > 32000001000 (should fail)
    balance = spec.MIN_ACTIVATION_BALANCE + spec.Gwei(1000)  # 32 ETH + 1000 gwei
    bid_amount = spec.Gwei(600)
    existing_withdrawal = spec.Gwei(500)

    state.balances[builder_index] = balance

    # Create existing pending withdrawal for this builder
    state.builder_pending_withdrawals.append(
        spec.BuilderPendingWithdrawal(
            fee_recipient=spec.ExecutionAddress(),
            amount=existing_withdrawal,
            builder_index=builder_index,
            withdrawable_epoch=spec.Epoch(100),  # Future epoch
        )
    )

    # Create bid with this non-proposer builder
    signed_bid = prepare_signed_execution_payload_bid(
        spec,
        state,
        builder_index=builder_index,
        value=bid_amount,
        slot=block.slot,
        parent_block_root=block.parent_root,
    )

    block.body.signed_execution_payload_bid = signed_bid

    yield from run_execution_payload_bid_processing(spec, state, block, valid=False)


@with_gloas_and_later
@spec_state_test
def test_process_execution_payload_bid_sufficient_balance_with_pending_withdrawals(spec, state):
    """
    Test builder with sufficient balance for both bid and existing pending withdrawals
    """
    block, builder_index = prepare_block_with_non_proposer_builder(spec, state)

    # Set up scenario: balance=2000, bid=600, existing_withdrawal=500, min_activation=32ETH
    # Total needed: 600 + 500 + 32000000000 = ~32.0011 ETH < 2000 ETH (should pass)
    balance = spec.Gwei(2000000000000)  # 2000 ETH
    bid_amount = spec.Gwei(600)
    existing_withdrawal = spec.Gwei(500)

    state.balances[builder_index] = balance

    # Create existing pending withdrawal for this builder
    state.builder_pending_withdrawals.append(
        spec.BuilderPendingWithdrawal(
            fee_recipient=spec.ExecutionAddress(),
            amount=existing_withdrawal,
            builder_index=builder_index,
            withdrawable_epoch=spec.Epoch(100),  # Future epoch
        )
    )

    pre_balance = state.balances[builder_index]
    pre_pending_payments_len = len(
        [p for p in state.builder_pending_payments if p.withdrawal.amount > 0]
    )
    pre_pending_withdrawals_len = len(state.builder_pending_withdrawals)

    # Create bid with this non-proposer builder
    signed_bid = prepare_signed_execution_payload_bid(
        spec,
        state,
        builder_index=builder_index,
        value=bid_amount,
        slot=block.slot,
        parent_block_root=block.parent_root,
    )

    block.body.signed_execution_payload_bid = signed_bid

    yield from run_execution_payload_bid_processing(spec, state, block)

    # Verify state updates
    assert state.latest_execution_payload_bid == signed_bid.message

    # Verify builder balance is still the same (payment is pending)
    assert state.balances[builder_index] == pre_balance

    # Verify new pending payment was recorded
    slot_index_new = spec.SLOTS_PER_EPOCH + (signed_bid.message.slot % spec.SLOTS_PER_EPOCH)
    pending_payment = state.builder_pending_payments[slot_index_new]
    assert pending_payment.withdrawal.amount == bid_amount
    assert pending_payment.withdrawal.builder_index == builder_index
    assert pending_payment.withdrawal.withdrawable_epoch == spec.FAR_FUTURE_EPOCH
    assert pending_payment.weight == 0

    # Verify pending payments count increased by 1
    post_pending_payments_len = len(
        [p for p in state.builder_pending_payments if p.withdrawal.amount > 0]
    )
    assert post_pending_payments_len == pre_pending_payments_len + 1

    # Verify pending withdrawals count stayed the same (existing withdrawal still there)
    post_pending_withdrawals_len = len(state.builder_pending_withdrawals)
    assert post_pending_withdrawals_len == pre_pending_withdrawals_len


#
# Bid field validation tests
#


@with_gloas_and_later
@spec_state_test
def test_process_execution_payload_bid_wrong_slot(spec, state):
    """
    Test wrong slot in bid fails
    """
    proposer_index = spec.get_beacon_proposer_index(state)

    # Create block first to advance slot
    block = build_empty_block_for_next_slot(spec, state)

    # Create bid with wrong slot
    signed_bid = prepare_signed_execution_payload_bid(
        spec,
        state,
        builder_index=proposer_index,
        slot=block.slot + 1,  # Wrong slot
        parent_block_root=block.parent_root,
    )

    block.body.signed_execution_payload_bid = signed_bid

    yield from run_execution_payload_bid_processing(spec, state, block, valid=False)


@with_gloas_and_later
@spec_state_test
def test_process_execution_payload_bid_wrong_parent_block_hash(spec, state):
    """
    Test wrong parent block hash fails
    """
    proposer_index = spec.get_beacon_proposer_index(state)

    # Create block first to advance slot
    block = build_empty_block_for_next_slot(spec, state)

    # Create bid with wrong parent block hash
    wrong_hash = spec.Hash32(b"\x42" * 32)
    signed_bid = prepare_signed_execution_payload_bid(
        spec,
        state,
        builder_index=proposer_index,
        slot=block.slot,
        parent_block_root=block.parent_root,
        parent_block_hash=wrong_hash,
    )

    block.body.signed_execution_payload_bid = signed_bid

    yield from run_execution_payload_bid_processing(spec, state, block, valid=False)


@with_gloas_and_later
@spec_state_test
def test_process_execution_payload_bid_wrong_parent_block_root(spec, state):
    """
    Test wrong parent block root fails
    """
    proposer_index = spec.get_beacon_proposer_index(state)

    # Create block first to advance slot
    block = build_empty_block_for_next_slot(spec, state)

    # Create bid with wrong parent block root
    wrong_root = spec.Root(b"\x42" * 32)
    signed_bid = prepare_signed_execution_payload_bid(
        spec, state, builder_index=proposer_index, slot=block.slot, parent_block_root=wrong_root
    )

    block.body.signed_execution_payload_bid = signed_bid

    yield from run_execution_payload_bid_processing(spec, state, block, valid=False)
