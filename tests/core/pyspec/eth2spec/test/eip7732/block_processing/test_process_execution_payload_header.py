from eth2spec.test.context import (
    always_bls,
    spec_state_test,
    with_eip7732_and_later,
)
from eth2spec.test.helpers.block import build_empty_block_for_next_slot
from eth2spec.test.helpers.keys import privkeys
from eth2spec.test.helpers.withdrawals import (
    set_builder_withdrawal_credential,
    set_builder_withdrawal_credential_with_balance,
)


def run_execution_payload_header_processing(spec, state, block, valid=True):
    """
    Run ``process_execution_payload_header``, yielding:
    - pre-state ('pre')
    - block ('block')
    - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    yield "pre", state
    yield "block", block

    if not valid:
        expect_assertion_error = True
    else:
        expect_assertion_error = False

    if expect_assertion_error:
        try:
            spec.process_execution_payload_header(state, block)
            assert False, "Expected AssertionError but none was raised"
        except AssertionError:
            pass
        yield "post", None
        return

    spec.process_execution_payload_header(state, block)
    yield "post", state


def prepare_signed_execution_payload_header(
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
    Helper to create a signed execution payload header with customizable parameters.
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
        kzg_list = spec.List[spec.KZGCommitment, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK]()
        blob_kzg_commitments_root = kzg_list.hash_tree_root()

    header = spec.ExecutionPayloadHeader(
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
        privkey = privkeys[builder_index]
        signature = spec.get_execution_payload_header_signature(state, header, privkey)
    else:
        # Invalid signature
        signature = spec.BLSSignature()

    return spec.SignedExecutionPayloadHeader(
        message=header,
        signature=signature,
    )


def make_validator_builder(spec, state, validator_index):
    """
    Helper to make a validator a builder by setting builder withdrawal credentials.
    """
    set_builder_withdrawal_credential(spec, state, validator_index)


def prepare_block_with_execution_payload_header(spec, state, **header_kwargs):
    """
    Helper that properly creates a block with execution payload header,
    handling the slot advancement correctly.
    """
    # Create block first (this advances state.slot)
    block = build_empty_block_for_next_slot(spec, state)

    # Ensure the header matches the block's context
    header_kwargs["slot"] = block.slot
    header_kwargs["parent_block_root"] = block.parent_root

    # Default builder_index to the block's proposer_index if not specified
    if "builder_index" not in header_kwargs:
        header_kwargs["builder_index"] = block.proposer_index

    # Now create header with the correct slot and parent root
    signed_header = prepare_signed_execution_payload_header(spec, state, **header_kwargs)
    block.body.signed_execution_payload_header = signed_header

    return block, signed_header


#
# Valid cases
#


@with_eip7732_and_later
@spec_state_test
def test_process_execution_payload_header_valid_self_build(spec, state):
    """
    Test valid self-building scenario (proposer building their own block with zero value)
    """
    block, signed_header = prepare_block_with_execution_payload_header(
        spec, state, value=spec.Gwei(0)
    )

    yield from run_execution_payload_header_processing(spec, state, block)


@with_eip7732_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_header_valid_builder(spec, state):
    """
    Test valid builder scenario with registered builder and non-zero value
    """
    builder_index = spec.get_beacon_proposer_index(state)

    # Make the validator a registered builder
    make_validator_builder(spec, state, builder_index)

    # Ensure builder has sufficient balance
    value = spec.Gwei(1000000)  # 0.001 ETH
    required_balance = value + spec.MIN_ACTIVATION_BALANCE
    state.balances[builder_index] = required_balance

    pre_balance = state.balances[builder_index]
    pre_pending_payments_len = len(
        [p for p in state.builder_pending_payments if p.withdrawal.amount > 0]
    )

    block, signed_header = prepare_block_with_execution_payload_header(
        spec, state, builder_index=builder_index, value=value
    )

    yield from run_execution_payload_header_processing(spec, state, block)

    # Verify state updates
    assert state.latest_execution_payload_header == signed_header.message

    # Verify builder balance is still the same
    assert state.balances[builder_index] == pre_balance

    # Verify pending payment was recorded
    slot_index = spec.SLOTS_PER_EPOCH + (signed_header.message.slot % spec.SLOTS_PER_EPOCH)
    pending_payment = state.builder_pending_payments[slot_index]
    assert pending_payment.withdrawal.amount == value
    assert pending_payment.withdrawal.builder_index == builder_index
    assert pending_payment.weight == 0

    # Verify pending payments count increased by 1
    post_pending_payments_len = len(
        [p for p in state.builder_pending_payments if p.withdrawal.amount > 0]
    )
    assert post_pending_payments_len == pre_pending_payments_len + 1


@with_eip7732_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_header_valid_builder_zero_value(spec, state):
    """
    Test valid builder scenario with registered builder and zero value
    """
    builder_index = spec.get_beacon_proposer_index(state)

    # Make the validator a registered builder
    make_validator_builder(spec, state, builder_index)

    block, signed_header = prepare_block_with_execution_payload_header(
        spec, state, builder_index=builder_index, value=spec.Gwei(0)
    )

    yield from run_execution_payload_header_processing(spec, state, block)


#
# Invalid signature tests
#


@with_eip7732_and_later
@spec_state_test
def test_process_execution_payload_header_invalid_signature(spec, state):
    """
    Test invalid signature fails
    """
    proposer_index = spec.get_beacon_proposer_index(state)

    block, signed_header = prepare_block_with_execution_payload_header(
        spec, state, builder_index=proposer_index, valid_signature=False
    )

    yield from run_execution_payload_header_processing(spec, state, block, valid=False)


#
# Builder validation tests
#


@with_eip7732_and_later
@spec_state_test
def test_process_execution_payload_header_inactive_builder(spec, state):
    """
    Test inactive builder fails
    """
    # Make builder inactive by setting exit epoch
    builder_index = spec.get_beacon_proposer_index(state)
    state.validators[builder_index].exit_epoch = spec.get_current_epoch(state)

    make_validator_builder(spec, state, builder_index)

    block, signed_header = prepare_block_with_execution_payload_header(
        spec, state, builder_index=builder_index, value=spec.Gwei(1000000)
    )

    yield from run_execution_payload_header_processing(spec, state, block, valid=False)


@with_eip7732_and_later
@spec_state_test
def test_process_execution_payload_header_slashed_builder(spec, state):
    """
    Test slashed builder fails
    """
    builder_index = spec.get_beacon_proposer_index(state)

    # Slash the builder
    state.validators[builder_index].slashed = True
    make_validator_builder(spec, state, builder_index)

    block, signed_header = prepare_block_with_execution_payload_header(
        spec, state, builder_index=builder_index, value=spec.Gwei(1000000)
    )

    yield from run_execution_payload_header_processing(spec, state, block, valid=False)


@with_eip7732_and_later
@spec_state_test
def test_process_execution_payload_header_self_build_non_zero_value(spec, state):
    """
    Test self-builder with non-zero value fails (builder_index == proposer_index but value > 0)
    """
    proposer_index = spec.get_beacon_proposer_index(state)

    # Make the proposer a registered builder
    make_validator_builder(spec, state, proposer_index)

    # Ensure builder has sufficient balance
    value = spec.Gwei(1000000)  # 0.001 ETH
    required_balance = value + spec.MIN_ACTIVATION_BALANCE
    state.balances[proposer_index] = required_balance

    block = build_empty_block_for_next_slot(spec, state)
    kzg_list = spec.List[spec.KZGCommitment, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK]()
    blob_kzg_commitments_root = kzg_list.hash_tree_root()

    header = spec.ExecutionPayloadHeader(
        parent_block_hash=state.latest_block_hash,
        parent_block_root=block.parent_root,
        block_hash=spec.Hash32(),
        fee_recipient=spec.ExecutionAddress(),
        gas_limit=spec.uint64(30000000),
        builder_index=proposer_index,  # Same as proposer (self-build)
        slot=block.slot,
        value=value,  # Non-zero value should fail for self-build
        blob_kzg_commitments_root=blob_kzg_commitments_root,
    )

    # Sign the header
    privkey = privkeys[proposer_index]
    signature = spec.get_execution_payload_header_signature(state, header, privkey)

    signed_header = spec.SignedExecutionPayloadHeader(
        message=header,
        signature=signature,
    )

    block.body.signed_execution_payload_header = signed_header

    yield from run_execution_payload_header_processing(spec, state, block, valid=False)


@with_eip7732_and_later
@spec_state_test
def test_process_execution_payload_header_non_builder_non_zero_value(spec, state):
    """
    Test non-builder attempting non-zero value fails
    """
    proposer_index = spec.get_beacon_proposer_index(state)

    # Don't make proposer a builder, but try non-zero value
    block, signed_header = prepare_block_with_execution_payload_header(
        spec,
        state,
        builder_index=proposer_index,
        value=spec.Gwei(1000000),  # Non-zero value should fail for non-builder
    )

    yield from run_execution_payload_header_processing(spec, state, block, valid=False)


@with_eip7732_and_later
@spec_state_test
def test_process_execution_payload_header_non_builder_wrong_proposer(spec, state):
    """
    Test non-builder with wrong proposer index fails
    """
    proposer_index = spec.get_beacon_proposer_index(state)
    other_index = (proposer_index + 1) % len(state.validators)

    # Non-builder but not the proposer
    block, signed_header = prepare_block_with_execution_payload_header(
        spec, state, builder_index=other_index, value=spec.Gwei(0)
    )

    yield from run_execution_payload_header_processing(spec, state, block, valid=False)


#
# Balance validation tests
#


@with_eip7732_and_later
@spec_state_test
def test_process_execution_payload_header_insufficient_balance(spec, state):
    """
    Test insufficient balance for bid fails
    """
    builder_index = spec.get_beacon_proposer_index(state)
    make_validator_builder(spec, state, builder_index)

    value = spec.Gwei(1000000)  # 0.001 ETH
    # Set balance too low
    state.balances[builder_index] = value - 1

    block, signed_header = prepare_block_with_execution_payload_header(
        spec, state, builder_index=builder_index, value=value
    )

    yield from run_execution_payload_header_processing(spec, state, block, valid=False)


@with_eip7732_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_header_excess_balance(spec, state):
    """
    Test builder with excess balance (2048.25 ETH) can submit bid for 2016.25 ETH
    Edge case where bid limit depends on builder's balance, not effective balance
    """
    builder_index = spec.get_beacon_proposer_index(state)

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

    block, signed_header = prepare_block_with_execution_payload_header(
        spec, state, builder_index=builder_index, value=bid_value
    )

    yield from run_execution_payload_header_processing(spec, state, block)

    # Verify state updates
    assert state.latest_execution_payload_header == signed_header.message

    # Verify builder balance is still the same (payment is pending)
    assert state.balances[builder_index] == pre_balance

    # Verify pending payment was recorded
    slot_index = spec.SLOTS_PER_EPOCH + (signed_header.message.slot % spec.SLOTS_PER_EPOCH)
    pending_payment = state.builder_pending_payments[slot_index]
    assert pending_payment.withdrawal.amount == bid_value
    assert pending_payment.withdrawal.builder_index == builder_index
    assert pending_payment.weight == 0

    # Verify pending payments count increased by 1
    post_pending_payments_len = len(
        [p for p in state.builder_pending_payments if p.withdrawal.amount > 0]
    )
    assert post_pending_payments_len == pre_pending_payments_len + 1


#
# Header field validation tests
#


@with_eip7732_and_later
@spec_state_test
def test_process_execution_payload_header_wrong_slot(spec, state):
    """
    Test wrong slot in header fails
    """
    proposer_index = spec.get_beacon_proposer_index(state)

    # Create block first to advance slot
    block = build_empty_block_for_next_slot(spec, state)

    # Create header with wrong slot
    signed_header = prepare_signed_execution_payload_header(
        spec,
        state,
        builder_index=proposer_index,
        slot=block.slot + 1,  # Wrong slot
        parent_block_root=block.parent_root,
    )

    block.body.signed_execution_payload_header = signed_header

    yield from run_execution_payload_header_processing(spec, state, block, valid=False)


@with_eip7732_and_later
@spec_state_test
def test_process_execution_payload_header_wrong_parent_block_hash(spec, state):
    """
    Test wrong parent block hash fails
    """
    proposer_index = spec.get_beacon_proposer_index(state)

    # Create block first to advance slot
    block = build_empty_block_for_next_slot(spec, state)

    # Create header with wrong parent block hash
    wrong_hash = spec.Hash32(b"\x42" * 32)
    signed_header = prepare_signed_execution_payload_header(
        spec,
        state,
        builder_index=proposer_index,
        slot=block.slot,
        parent_block_root=block.parent_root,
        parent_block_hash=wrong_hash,
    )

    block.body.signed_execution_payload_header = signed_header

    yield from run_execution_payload_header_processing(spec, state, block, valid=False)


@with_eip7732_and_later
@spec_state_test
def test_process_execution_payload_header_wrong_parent_block_root(spec, state):
    """
    Test wrong parent block root fails
    """
    proposer_index = spec.get_beacon_proposer_index(state)

    # Create block first to advance slot
    block = build_empty_block_for_next_slot(spec, state)

    # Create header with wrong parent block root
    wrong_root = spec.Root(b"\x42" * 32)
    signed_header = prepare_signed_execution_payload_header(
        spec, state, builder_index=proposer_index, slot=block.slot, parent_block_root=wrong_root
    )

    block.body.signed_execution_payload_header = signed_header

    yield from run_execution_payload_header_processing(spec, state, block, valid=False)
