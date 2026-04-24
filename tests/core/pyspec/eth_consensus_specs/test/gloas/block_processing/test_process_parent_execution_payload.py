from eth_consensus_specs.test.context import (
    expect_assertion_error,
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.deposits import (
    make_withdrawal_credentials,
    prepare_deposit_request,
)
from eth_consensus_specs.test.helpers.execution_requests import (
    get_non_empty_execution_requests,
)
from eth_consensus_specs.test.helpers.keys import pubkeys
from tests.infra.helpers.withdrawals import set_parent_block_full


def _commit_parent_requests(spec, state, requests, value=None, builder_index=None):
    """
    Configure state so the parent block was FULL and the parent bid commits to ``requests``.
    If ``value`` > 0, also populate the corresponding ``builder_pending_payments`` slot so
    ``apply_parent_execution_payload`` has a payment to settle.
    """
    set_parent_block_full(spec, state)

    bid = state.latest_execution_payload_bid
    bid.execution_requests_root = spec.hash_tree_root(requests)

    if value is not None:
        bid.value = value
    if builder_index is not None:
        bid.builder_index = builder_index

    if bid.value > 0:
        payment_idx = spec.SLOTS_PER_EPOCH + bid.slot % spec.SLOTS_PER_EPOCH
        state.builder_pending_payments[payment_idx] = spec.BuilderPendingPayment(
            weight=spec.Gwei(0),
            withdrawal=spec.BuilderPendingWithdrawal(
                fee_recipient=bid.fee_recipient,
                amount=bid.value,
                builder_index=bid.builder_index,
            ),
        )


def run_parent_execution_payload_processing(spec, state, block, valid=True):
    """
    Run ``process_parent_execution_payload`` against a prepared pre-state.
    """
    yield "pre", state
    yield "block", block

    if not valid:
        expect_assertion_error(lambda: spec.process_parent_execution_payload(state, block))
        yield "post", None
        return

    spec.process_parent_execution_payload(state, block)
    yield "post", state


@with_gloas_and_later
@spec_state_test
def test_process_parent_execution_payload__empty_parent(spec, state):
    """
    Test that process_parent_execution_payload returns early when the parent
    block was empty (payload not delivered).
    """
    block = build_empty_block_for_next_slot(spec, state)

    is_parent_block_full = (
        block.body.signed_execution_payload_bid.message.parent_block_hash
        == state.latest_execution_payload_bid.block_hash
    )
    assert not is_parent_block_full

    pre_latest_block_hash = state.latest_block_hash
    parent_slot = state.latest_execution_payload_bid.slot
    pre_availability = state.execution_payload_availability[
        parent_slot % spec.SLOTS_PER_HISTORICAL_ROOT
    ]

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)

    assert state.latest_block_hash == pre_latest_block_hash
    assert (
        state.execution_payload_availability[parent_slot % spec.SLOTS_PER_HISTORICAL_ROOT]
        == pre_availability
    )


@with_gloas_and_later
@spec_state_test
def test_process_parent_execution_payload__full_parent(spec, state):
    """
    Test that process_parent_execution_payload processes the parent's execution
    requests and updates state when the parent block was full.
    """
    set_parent_block_full(spec, state)
    block = build_empty_block_for_next_slot(spec, state)

    parent_bid = state.latest_execution_payload_bid.copy()
    parent_slot_index = parent_bid.slot % spec.SLOTS_PER_HISTORICAL_ROOT
    state.execution_payload_availability[parent_slot_index] = 0b0

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)

    assert state.latest_block_hash == parent_bid.block_hash
    assert state.execution_payload_availability[parent_slot_index] == 0b1


@with_gloas_and_later
@spec_state_test
def test_process_parent_execution_payload__empty_parent_requires_empty_requests(spec, state):
    """
    Test that when parent is empty, parent_execution_requests must be empty.
    """
    block = build_empty_block_for_next_slot(spec, state)

    is_parent_block_full = (
        block.body.signed_execution_payload_bid.message.parent_block_hash
        == state.latest_execution_payload_bid.block_hash
    )
    assert not is_parent_block_full

    block.body.parent_execution_requests = get_non_empty_execution_requests(spec)

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block, valid=False)


@with_gloas_and_later
@spec_state_test
def test_process_parent_execution_payload_genesis(spec, state):
    """
    Verify that process_parent_execution_payload does not update
    latest_block_hash when both hashes are Hash32().
    """
    state.latest_block_hash = spec.Hash32()
    state.latest_execution_payload_bid.block_hash = spec.Hash32()

    block = build_empty_block_for_next_slot(spec, state)
    block.body.signed_execution_payload_bid.message.parent_block_hash = spec.Hash32()

    pre_latest_block_hash = state.latest_block_hash

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)

    assert state.latest_block_hash == pre_latest_block_hash


@with_gloas_and_later
@spec_state_test
def test_process_parent_execution_payload__full_parent_settles_builder_payment(spec, state):
    """
    Test that when the parent block was full with a non-zero builder payment,
    the payment is settled into ``builder_pending_withdrawals`` and the pending
    payments slot is cleared.
    """
    builder_index = 0
    value = spec.Gwei(50_000_000)
    fee_recipient = spec.ExecutionAddress(b"\xab" * 20)

    # Set the fee recipient before committing the parent requests so the pending
    # payment uses the same address.
    state.latest_execution_payload_bid.fee_recipient = fee_recipient
    _commit_parent_requests(
        spec, state, spec.ExecutionRequests(), value=value, builder_index=builder_index
    )
    parent_bid = state.latest_execution_payload_bid.copy()
    payment_idx = spec.SLOTS_PER_EPOCH + parent_bid.slot % spec.SLOTS_PER_EPOCH

    block = build_empty_block_for_next_slot(spec, state)
    pre_pending_withdrawals_len = len(state.builder_pending_withdrawals)

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)

    # A new pending withdrawal was added for the builder payment
    assert len(state.builder_pending_withdrawals) == pre_pending_withdrawals_len + 1
    new_withdrawal = state.builder_pending_withdrawals[pre_pending_withdrawals_len]
    assert new_withdrawal.amount == value
    assert new_withdrawal.builder_index == builder_index
    assert new_withdrawal.fee_recipient == fee_recipient

    # The pending payment slot was cleared
    assert state.builder_pending_payments[payment_idx] == spec.BuilderPendingPayment()


@with_gloas_and_later
@spec_state_test
def test_process_parent_execution_payload__full_parent_self_build_zero_value(spec, state):
    """
    Test that a self-build parent (value == 0) does not add a builder pending
    withdrawal while still marking the payload as available.
    """
    _commit_parent_requests(
        spec,
        state,
        spec.ExecutionRequests(),
        value=spec.Gwei(0),
        builder_index=spec.BUILDER_INDEX_SELF_BUILD,
    )
    parent_bid = state.latest_execution_payload_bid.copy()
    parent_slot_index = parent_bid.slot % spec.SLOTS_PER_HISTORICAL_ROOT
    state.execution_payload_availability[parent_slot_index] = 0b0

    block = build_empty_block_for_next_slot(spec, state)
    pre_pending_withdrawals_len = len(state.builder_pending_withdrawals)

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)

    # Zero-value self-build produces no new builder pending withdrawal
    assert len(state.builder_pending_withdrawals) == pre_pending_withdrawals_len
    # Payload was still marked available and latest_block_hash advanced
    assert state.execution_payload_availability[parent_slot_index] == 0b1
    assert state.latest_block_hash == parent_bid.block_hash


@with_gloas_and_later
@spec_state_test
def test_process_parent_execution_payload__full_parent_with_execution_requests(spec, state):
    """
    Test that deposits, withdrawals, and consolidations in the parent's execution
    requests are processed when the parent block was full. Deposits are always
    appended to ``pending_deposits``; withdrawal and consolidation requests with
    unknown pubkeys are no-ops.
    """
    requests = spec.ExecutionRequests(
        deposits=spec.List[spec.DepositRequest, spec.MAX_DEPOSIT_REQUESTS_PER_PAYLOAD](
            [
                spec.DepositRequest(
                    pubkey=spec.BLSPubkey(b"\x01" * 48),
                    withdrawal_credentials=spec.Bytes32(b"\x02" * 32),
                    amount=spec.Gwei(32_000_000_000),
                    signature=spec.BLSSignature(b"\x03" * 96),
                    index=spec.uint64(0),
                )
            ]
        ),
        withdrawals=spec.List[spec.WithdrawalRequest, spec.MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD](
            [
                spec.WithdrawalRequest(
                    source_address=spec.ExecutionAddress(b"\x04" * 20),
                    validator_pubkey=spec.BLSPubkey(b"\x05" * 48),
                    amount=spec.Gwei(16_000_000_000),
                )
            ]
        ),
        consolidations=spec.List[
            spec.ConsolidationRequest, spec.MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD
        ](
            [
                spec.ConsolidationRequest(
                    source_address=spec.ExecutionAddress(b"\x06" * 20),
                    source_pubkey=spec.BLSPubkey(b"\x07" * 48),
                    target_pubkey=spec.BLSPubkey(b"\x08" * 48),
                )
            ]
        ),
    )

    _commit_parent_requests(spec, state, requests)
    deposit_request = requests.deposits[0]

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests
    pre_pending_deposits_len = len(state.pending_deposits)
    pre_pending_partial_withdrawals_len = len(state.pending_partial_withdrawals)
    pre_pending_consolidations_len = len(state.pending_consolidations)
    pre_validators = [v.copy() for v in state.validators]

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)

    # The deposit request was queued as a pending deposit
    assert len(state.pending_deposits) == pre_pending_deposits_len + 1
    new_pending_deposit = state.pending_deposits[pre_pending_deposits_len]
    assert new_pending_deposit.pubkey == deposit_request.pubkey
    assert new_pending_deposit.withdrawal_credentials == deposit_request.withdrawal_credentials
    assert new_pending_deposit.amount == deposit_request.amount

    # The withdrawal request (unknown validator_pubkey) and the consolidation
    # request (unknown source/target pubkeys) must be no-ops: no queue entries,
    # no exit initiated, no credentials or withdrawable_epoch changes.
    assert len(state.pending_partial_withdrawals) == pre_pending_partial_withdrawals_len
    assert len(state.pending_consolidations) == pre_pending_consolidations_len
    assert len(state.validators) == len(pre_validators)
    for i, pre_v in enumerate(pre_validators):
        post_v = state.validators[i]
        assert post_v.exit_epoch == pre_v.exit_epoch
        assert post_v.withdrawable_epoch == pre_v.withdrawable_epoch
        assert post_v.withdrawal_credentials == pre_v.withdrawal_credentials


@with_gloas_and_later
@spec_state_test
def test_process_parent_execution_payload__builder_deposit_after_pending_validator(spec, state):
    """
    Test that a builder deposit cannot claim a pubkey that is already a pending validator
    earlier in the same parent execution requests batch.
    """
    new_validator_index = len(state.validators)
    new_validator_pubkey = pubkeys[new_validator_index]
    amount = spec.MIN_DEPOSIT_AMOUNT

    # First deposit: regular validator credentials with valid signature.
    # Since no validator/builder/pending deposit exists for this pubkey, it is queued as a pending validator.
    deposit_request_1 = prepare_deposit_request(
        spec,
        new_validator_index,
        amount,
        index=0,
        pubkey=new_validator_pubkey,
        withdrawal_credentials=make_withdrawal_credentials(
            spec, spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX, b"\xab"
        ),
        signed=True,
    )

    # Second deposit: builder credentials for the same pubkey.
    # ``is_pending_validator`` must see the first deposit (just queued) and route this one
    # to the pending queue instead of the builder registry, preventing a builder from
    # claiming a pubkey already in the validator queue.
    deposit_request_2 = prepare_deposit_request(
        spec,
        new_validator_index,
        amount,
        index=1,
        pubkey=new_validator_pubkey,
        withdrawal_credentials=make_withdrawal_credentials(
            spec, spec.BUILDER_WITHDRAWAL_PREFIX, b"\x59"
        ),
        signed=True,
    )

    requests = spec.ExecutionRequests(
        deposits=spec.List[spec.DepositRequest, spec.MAX_DEPOSIT_REQUESTS_PER_PAYLOAD](
            [deposit_request_1, deposit_request_2]
        ),
        withdrawals=spec.List[spec.WithdrawalRequest, spec.MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD](),
        consolidations=spec.List[
            spec.ConsolidationRequest, spec.MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD
        ](),
    )

    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests
    pre_pending_deposits_len = len(state.pending_deposits)
    pre_builder_count = len(state.builders)

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)

    # Both deposits must end up in the pending queue, with no new builder created
    assert len(state.pending_deposits) == pre_pending_deposits_len + 2
    assert len(state.builders) == pre_builder_count
    first = state.pending_deposits[pre_pending_deposits_len]
    second = state.pending_deposits[pre_pending_deposits_len + 1]
    assert first.pubkey == deposit_request_1.pubkey
    assert first.withdrawal_credentials == deposit_request_1.withdrawal_credentials
    assert first.amount == deposit_request_1.amount
    assert second.pubkey == deposit_request_2.pubkey
    assert second.withdrawal_credentials == deposit_request_2.withdrawal_credentials
    assert second.amount == deposit_request_2.amount
