from eth_consensus_specs.test.context import (
    expect_assertion_error,
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.builder_deposit_requests import (
    prepare_process_builder_deposit_request,
)
from eth_consensus_specs.test.helpers.deposits import (
    make_withdrawal_credentials,
    prepare_deposit_request,
)
from eth_consensus_specs.test.helpers.execution_requests import (
    get_non_empty_execution_requests,
)
from eth_consensus_specs.test.helpers.keys import pubkeys
from eth_consensus_specs.test.helpers.withdrawals import set_parent_block_full


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


def _commit_full_parent_with_payment(spec, state, value, builder_index, fee_recipient):
    """
    Commit a FULL parent with a builder payment at slot ``SLOTS_PER_EPOCH - 1``.
    Clear its availability bit.
    """
    state.latest_execution_payload_bid.slot = spec.Slot(spec.SLOTS_PER_EPOCH - 1)
    state.latest_execution_payload_bid.fee_recipient = fee_recipient
    _commit_parent_requests(
        spec, state, spec.ExecutionRequests(), value=value, builder_index=builder_index
    )

    parent_bid = state.latest_execution_payload_bid.copy()
    state.execution_payload_availability[parent_bid.slot % spec.SLOTS_PER_HISTORICAL_ROOT] = 0b0
    return parent_bid


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
    Verify that process_parent_execution_payload does not update in genesis.
    """
    block = build_empty_block_for_next_slot(spec, state)
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
        deposits=spec.ProgressiveList[spec.DepositRequest](
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
        withdrawals=spec.ProgressiveList[spec.WithdrawalRequest](
            [
                spec.WithdrawalRequest(
                    source_address=spec.ExecutionAddress(b"\x04" * 20),
                    validator_pubkey=spec.BLSPubkey(b"\x05" * 48),
                    amount=spec.Gwei(16_000_000_000),
                )
            ]
        ),
        consolidations=spec.ProgressiveList[spec.ConsolidationRequest](
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
def test_process_parent_execution_payload__builder_credential_deposits_queued(spec, state):
    """
    Test that deposit requests are queued as pending deposits regardless of
    their withdrawal credentials. Deposit requests never create builders.
    """
    new_validator_index = len(state.validators)
    new_validator_pubkey = pubkeys[new_validator_index]
    amount = spec.MIN_DEPOSIT_AMOUNT

    # First deposit: regular validator credentials with valid signature
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

    # Second deposit: builder credentials for the same pubkey, also queued
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
        deposits=spec.ProgressiveList[spec.DepositRequest]([deposit_request_1, deposit_request_2]),
        withdrawals=spec.ProgressiveList[spec.WithdrawalRequest](),
        consolidations=spec.ProgressiveList[spec.ConsolidationRequest](),
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


@with_gloas_and_later
@spec_state_test
def test_process_parent_execution_payload__settle_previous_epoch(spec, state):
    """
    Test ``apply_parent_execution_payload`` settles the previous epoch payment
    slot when the parent's slot falls in the previous epoch.
    """
    builder_index = 0
    value = spec.Gwei(50_000_000)
    fee_recipient = spec.ExecutionAddress(b"\xab" * 20)
    parent_bid = _commit_full_parent_with_payment(spec, state, value, builder_index, fee_recipient)
    previous_epoch_idx = parent_bid.slot % spec.SLOTS_PER_EPOCH

    # Process one epoch
    spec.process_slots(state, spec.SLOTS_PER_EPOCH)

    assert spec.compute_epoch_at_slot(parent_bid.slot) == spec.get_previous_epoch(state)
    assert state.builder_pending_payments[previous_epoch_idx].withdrawal.amount == value

    block = build_empty_block_for_next_slot(spec, state)
    spec.process_slots(state, block.slot)
    pre_pending_withdrawals_len = len(state.builder_pending_withdrawals)

    yield from run_parent_execution_payload_processing(spec, state, block)

    assert len(state.builder_pending_withdrawals) == pre_pending_withdrawals_len + 1
    withdrawal = state.builder_pending_withdrawals[pre_pending_withdrawals_len]
    assert withdrawal.amount == value
    assert withdrawal.builder_index == builder_index
    assert withdrawal.fee_recipient == fee_recipient

    # Previous epoch slot cleared and availability bit flipped
    assert state.builder_pending_payments[previous_epoch_idx] == spec.BuilderPendingPayment()
    assert (
        state.execution_payload_availability[parent_bid.slot % spec.SLOTS_PER_HISTORICAL_ROOT]
        == 0b1
    )


@with_gloas_and_later
@spec_state_test
def test_process_parent_execution_payload__older_than_previous_epoch(spec, state):
    """
    Test ``apply_parent_execution_payload`` appends the withdrawal directly when
    the parent's slot is older than the previous epoch.
    """
    builder_index = 0
    value = spec.Gwei(50_000_000)
    fee_recipient = spec.ExecutionAddress(b"\xab" * 20)
    parent_bid = _commit_full_parent_with_payment(spec, state, value, builder_index, fee_recipient)
    previous_epoch_idx = parent_bid.slot % spec.SLOTS_PER_EPOCH

    # Cross two epoch boundaries to evict payments
    spec.process_slots(state, 2 * spec.SLOTS_PER_EPOCH)
    block = build_empty_block_for_next_slot(spec, state)
    spec.process_slots(state, block.slot)

    # Assert payment was evicted from the previous epoch
    assert spec.compute_epoch_at_slot(parent_bid.slot) < spec.get_previous_epoch(state)
    assert state.builder_pending_payments[previous_epoch_idx] == spec.BuilderPendingPayment()

    pre_pending_withdrawals_len = len(state.builder_pending_withdrawals)
    pre_payments = state.builder_pending_payments.copy()

    yield from run_parent_execution_payload_processing(spec, state, block)

    # Check we have a pending withdrawal
    assert len(state.builder_pending_withdrawals) == pre_pending_withdrawals_len + 1
    withdrawal = state.builder_pending_withdrawals[pre_pending_withdrawals_len]
    assert withdrawal.amount == value
    assert withdrawal.builder_index == builder_index
    assert withdrawal.fee_recipient == fee_recipient

    # Assert no payment slot is modified
    assert all(
        post == pre for post, pre in zip(state.builder_pending_payments, pre_payments, strict=True)
    )


@with_gloas_and_later
@spec_state_test
def test_process_parent_execution_payload__new_builder_does_not_reuse_topped_up_builder_slot(
    spec, state
):
    """
    Test that a reusable builder slot is no longer reusable after an earlier
    positive top-up in the same parent execution requests batch.
    """
    existing_builder_pubkey = state.builders[0].pubkey
    pre_builder_count = len(state.builders)
    pre_pending_deposits_len = len(state.pending_deposits)

    state.builders[0].withdrawable_epoch = spec.get_current_epoch(state)
    state.builders[0].balance = spec.Gwei(0)
    existing_builder_pre_balance = state.builders[0].balance

    top_up_amount = spec.MIN_DEPOSIT_AMOUNT
    new_builder_amount = spec.MIN_DEPOSIT_AMOUNT

    builder_deposit_request_1 = prepare_process_builder_deposit_request(
        spec,
        state,
        builder_index=0,
        pubkey=existing_builder_pubkey,
        amount=top_up_amount,
        signed=True,
    )
    builder_deposit_request_2 = prepare_process_builder_deposit_request(
        spec,
        state,
        amount=new_builder_amount,
        signed=True,
    )

    requests = spec.ExecutionRequests(
        builder_deposits=spec.ProgressiveList[spec.BuilderDepositRequest](
            [builder_deposit_request_1, builder_deposit_request_2]
        ),
    )

    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)

    assert len(state.pending_deposits) == pre_pending_deposits_len
    assert len(state.builders) == pre_builder_count + 1

    topped_up_builder = state.builders[0]
    assert topped_up_builder.pubkey == existing_builder_pubkey
    assert topped_up_builder.balance == existing_builder_pre_balance + top_up_amount

    new_builder_index = None
    for i, builder in enumerate(state.builders):
        if builder.pubkey == builder_deposit_request_2.pubkey:
            new_builder_index = i
            break

    assert new_builder_index is not None
    assert new_builder_index != 0
    assert state.builders[new_builder_index].balance == new_builder_amount


@with_gloas_and_later
@spec_state_test
def test_process_parent_execution_payload__builder_exit_request(spec, state):
    """
    Test that a builder exit request in the parent's execution requests exits an
    active builder authorized by its execution address.
    """
    builder_index = 0

    # Finalize the builder's deposit epoch so that it is active
    state.finalized_checkpoint.epoch = state.builders[builder_index].deposit_epoch + 1
    assert spec.is_active_builder(state, builder_index)
    assert spec.get_pending_balance_to_withdraw_for_builder(state, builder_index) == 0

    builder = state.builders[builder_index]
    requests = spec.ExecutionRequests(
        builder_exits=spec.ProgressiveList[spec.BuilderExitRequest](
            [
                spec.BuilderExitRequest(
                    source_address=builder.execution_address,
                    pubkey=builder.pubkey,
                )
            ]
        ),
    )

    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    current_epoch = spec.get_current_epoch(state)

    yield from run_parent_execution_payload_processing(spec, state, block)

    # The builder exit was initiated
    assert not spec.is_active_builder(state, builder_index)
    expected_withdrawable = current_epoch + spec.config.MIN_BUILDER_WITHDRAWABILITY_DELAY
    assert state.builders[builder_index].withdrawable_epoch == expected_withdrawable


@with_gloas_and_later
@spec_state_test
def test_max_deposit_requests(spec, state):
    requests = spec.ExecutionRequests(
        deposits=spec.ProgressiveList[spec.DepositRequest](
            [spec.DepositRequest()] * spec.MAX_DEPOSIT_REQUESTS_PER_PAYLOAD
        ),
    )
    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)


@with_gloas_and_later
@spec_state_test
def test_invalid_too_many_deposit_requests(spec, state):
    requests = spec.ExecutionRequests(
        deposits=spec.ProgressiveList[spec.DepositRequest](
            [spec.DepositRequest()] * (spec.MAX_DEPOSIT_REQUESTS_PER_PAYLOAD + 1)
        ),
    )
    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block, valid=False)


@with_gloas_and_later
@spec_state_test
def test_max_withdrawal_requests(spec, state):
    requests = spec.ExecutionRequests(
        withdrawals=spec.ProgressiveList[spec.WithdrawalRequest](
            [spec.WithdrawalRequest()] * spec.MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD
        ),
    )
    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)


@with_gloas_and_later
@spec_state_test
def test_invalid_too_many_withdrawal_requests(spec, state):
    requests = spec.ExecutionRequests(
        withdrawals=spec.ProgressiveList[spec.WithdrawalRequest](
            [spec.WithdrawalRequest()] * (spec.MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD + 1)
        ),
    )
    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block, valid=False)


@with_gloas_and_later
@spec_state_test
def test_max_consolidation_requests(spec, state):
    requests = spec.ExecutionRequests(
        consolidations=spec.ProgressiveList[spec.ConsolidationRequest](
            [spec.ConsolidationRequest()] * spec.MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD
        ),
    )
    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)


@with_gloas_and_later
@spec_state_test
def test_invalid_too_many_consolidation_requests(spec, state):
    requests = spec.ExecutionRequests(
        consolidations=spec.ProgressiveList[spec.ConsolidationRequest](
            [spec.ConsolidationRequest()] * (spec.MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD + 1)
        ),
    )
    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block, valid=False)


@with_gloas_and_later
@spec_state_test
def test_max_builder_deposit_requests(spec, state):
    requests = spec.ExecutionRequests(
        builder_deposits=spec.ProgressiveList[spec.BuilderDepositRequest](
            [spec.BuilderDepositRequest()] * spec.MAX_BUILDER_DEPOSIT_REQUESTS_PER_PAYLOAD
        ),
    )
    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)


@with_gloas_and_later
@spec_state_test
def test_invalid_too_many_builder_deposit_requests(spec, state):
    requests = spec.ExecutionRequests(
        builder_deposits=spec.ProgressiveList[spec.BuilderDepositRequest](
            [spec.BuilderDepositRequest()] * (spec.MAX_BUILDER_DEPOSIT_REQUESTS_PER_PAYLOAD + 1)
        ),
    )
    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block, valid=False)


@with_gloas_and_later
@spec_state_test
def test_max_builder_exit_requests(spec, state):
    requests = spec.ExecutionRequests(
        builder_exits=spec.ProgressiveList[spec.BuilderExitRequest](
            [spec.BuilderExitRequest()] * spec.MAX_BUILDER_EXIT_REQUESTS_PER_PAYLOAD
        ),
    )
    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)


@with_gloas_and_later
@spec_state_test
def test_invalid_too_many_builder_exit_requests(spec, state):
    requests = spec.ExecutionRequests(
        builder_exits=spec.ProgressiveList[spec.BuilderExitRequest](
            [spec.BuilderExitRequest()] * (spec.MAX_BUILDER_EXIT_REQUESTS_PER_PAYLOAD + 1)
        ),
    )
    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block, valid=False)
