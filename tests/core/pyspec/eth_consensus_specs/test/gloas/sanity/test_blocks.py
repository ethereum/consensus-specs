from random import Random

from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.attestations import get_max_attestations
from eth_consensus_specs.test.helpers.attester_slashings import (
    get_max_attester_slashings,
    get_valid_attester_slashing_by_indices,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block,
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.bls_to_execution_changes import get_signed_address_change
from eth_consensus_specs.test.helpers.deposits import build_deposit_data, deposit_from_context
from eth_consensus_specs.test.helpers.execution_requests import (
    get_non_empty_execution_requests,
)
from eth_consensus_specs.test.helpers.keys import builder_privkeys, privkeys, pubkeys
from eth_consensus_specs.test.helpers.multi_operations import (
    get_random_attestations,
)
from eth_consensus_specs.test.helpers.payload_attestation import get_random_payload_attestations
from eth_consensus_specs.test.helpers.proposer_slashings import (
    get_valid_proposer_slashings,
)
from eth_consensus_specs.test.helpers.state import (
    next_epoch,
    next_epoch_with_full_participation,
    next_slots,
    state_transition_and_sign_block,
)
from eth_consensus_specs.test.helpers.voluntary_exits import prepare_signed_exits
from eth_consensus_specs.test.helpers.withdrawals import (
    prepare_withdrawal_request,
    set_validator_fully_withdrawable,
)
from tests.infra.helpers.withdrawals import (
    get_expected_withdrawals,
    set_parent_block_full,
)


def _setup_missed_payload_with_withdrawals(spec, state, num_withdrawal_validators=1):
    """
    Common setup: set validators as fully withdrawable, make parent block full,
    process Block 1 (which computes withdrawals), and skip payload delivery.

    When num_withdrawal_validators > MAX_WITHDRAWALS_PER_PAYLOAD, Block 1 processes
    exactly MAX_WITHDRAWALS_PER_PAYLOAD validators and the remainder stay withdrawable
    for Block 2's hypothetical sweep.

    After this:
    - Block 1's withdrawals (W_1) are stored in state.payload_expected_withdrawals
    - is_parent_block_full returns False (payload for Block 1 was not delivered)

    Returns:
        (pre_state, signed_block_1, block_1_withdrawals)
    """
    # Make parent block full so Block 1's process_withdrawals runs
    set_parent_block_full(spec, state)

    # Set up validators as fully withdrawable
    for i in range(num_withdrawal_validators):
        set_validator_fully_withdrawable(spec, state, i)

    # Verify there are expected withdrawals before processing Block 1
    assert len(get_expected_withdrawals(spec, state)) > 0

    # Save pre-state before any blocks
    pre_state = state.copy()

    # Process Block 1 — process_withdrawals runs (parent is full),
    # computes withdrawals W_1, applies balance changes, stores in payload_expected_withdrawals.
    # process_execution_payload_bid commits the bid.
    # Payload is NOT delivered.
    block_1 = build_empty_block_for_next_slot(spec, state)
    signed_block_1 = state_transition_and_sign_block(spec, state, block_1)

    # Block 1 should have computed non-empty withdrawals
    block_1_withdrawals = list(state.payload_expected_withdrawals)
    assert len(block_1_withdrawals) > 0

    # Payload for Block 1 was not delivered, so parent is empty for Block 2
    is_parent_block_full = state.latest_block_hash == state.latest_execution_payload_bid.block_hash
    assert not is_parent_block_full

    return pre_state, signed_block_1, block_1_withdrawals


def _attempt_payload_with_withdrawals(spec, state, withdrawals):
    """
    Attempt to verify a payload for the current slot with the given withdrawals.
    Operates on a copy to avoid mutating the test state.
    BLS is disabled in tests by default, so signature verification passes.

    Returns True if accepted, False if rejected.
    """
    test_state = state.copy()
    committed_bid = test_state.latest_execution_payload_bid

    # Build payload matching the committed bid in every field
    payload = spec.ExecutionPayload(
        parent_hash=test_state.latest_block_hash,
        prev_randao=committed_bid.prev_randao,
        gas_limit=committed_bid.gas_limit,
        block_hash=committed_bid.block_hash,
        timestamp=spec.compute_time_at_slot(test_state, test_state.slot),
        withdrawals=withdrawals,
        slot_number=test_state.slot,
    )

    # Cache state root for beacon_block_root computation
    header = test_state.latest_block_header.copy()
    header.state_root = test_state.hash_tree_root()

    envelope = spec.ExecutionPayloadEnvelope(
        payload=payload,
        execution_requests=spec.ExecutionRequests(),
        builder_index=committed_bid.builder_index,
        beacon_block_root=header.hash_tree_root(),
        parent_beacon_block_root=test_state.latest_block_header.parent_root,
    )

    if envelope.builder_index == spec.BUILDER_INDEX_SELF_BUILD:
        privkey = privkeys[test_state.latest_block_header.proposer_index]
    else:
        privkey = builder_privkeys[envelope.builder_index]
    signature = spec.get_execution_payload_envelope_signature(test_state, envelope, privkey)

    signed_envelope = spec.SignedExecutionPayloadEnvelope(
        message=envelope,
        signature=signature,
    )

    engine = spec.NoopExecutionEngine()

    try:
        spec.verify_execution_payload_envelope(test_state, signed_envelope, engine)
        return True
    except AssertionError:
        return False


@with_gloas_and_later
@spec_state_test
def test_missed_payload_next_block_with_withdrawals_satisfying_payload(spec, state):
    """
    Block 1: has withdrawal-eligible validators (more than MAX_WITHDRAWALS_PER_PAYLOAD).
    Payload for Block 1 does not arrive.
    Block 2: remaining validators are still withdrawal-eligible.
    Payload for Block 2: includes Block 1's stale withdrawals (W_1) → accepted.
    """
    # Set up MAX + 1 validators. Block 1 processes exactly MAX, leaving 1 remaining.
    pre_state, signed_block_1, block_1_withdrawals = _setup_missed_payload_with_withdrawals(
        spec, state, num_withdrawal_validators=spec.MAX_WITHDRAWALS_PER_PAYLOAD + 1
    )

    # Process Block 2 (parent empty → process_withdrawals returns early)
    block_2 = build_empty_block_for_next_slot(spec, state)
    signed_block_2 = state_transition_and_sign_block(spec, state, block_2)

    yield "pre", pre_state
    yield "blocks", [signed_block_1, signed_block_2]
    yield "post", state

    # Remaining validator is still withdrawable, but process_withdrawals skipped it
    current_expected = get_expected_withdrawals(spec, state)
    assert len(current_expected) > 0
    assert list(current_expected) != block_1_withdrawals

    # A payload with Block 1's stale withdrawals (W_1) is accepted
    satisfying = spec.ProgressiveList[spec.Withdrawal](block_1_withdrawals)
    assert _attempt_payload_with_withdrawals(spec, state, satisfying)


@with_gloas_and_later
@spec_state_test
def test_missed_payload_next_block_with_withdrawals_unsatisfying_payload(spec, state):
    """
    Block 1: has withdrawal-eligible validators (more than MAX_WITHDRAWALS_PER_PAYLOAD).
    Payload for Block 1 does not arrive.
    Block 2: remaining validators are still withdrawal-eligible.
    Payload for Block 2: includes fresh expected withdrawals instead of W_1 → rejected.
    """
    # Set up MAX + 1 validators. Block 1 processes exactly MAX, leaving 1 remaining.
    pre_state, signed_block_1, block_1_withdrawals = _setup_missed_payload_with_withdrawals(
        spec, state, num_withdrawal_validators=spec.MAX_WITHDRAWALS_PER_PAYLOAD + 1
    )

    # Process Block 2 (parent empty → process_withdrawals returns early)
    block_2 = build_empty_block_for_next_slot(spec, state)
    signed_block_2 = state_transition_and_sign_block(spec, state, block_2)

    yield "pre", pre_state
    yield "blocks", [signed_block_1, signed_block_2]
    yield "post", state

    # Fresh expected withdrawals differ from W_1
    current_expected = get_expected_withdrawals(spec, state)
    assert len(current_expected) > 0
    assert list(current_expected) != block_1_withdrawals

    # A payload with fresh withdrawals (not W_1) is rejected
    unsatisfying = spec.ProgressiveList[spec.Withdrawal](current_expected)
    assert not _attempt_payload_with_withdrawals(spec, state, unsatisfying)


@with_gloas_and_later
@spec_state_test
def test_missed_payload_next_block_without_withdrawals_satisfying_payload(spec, state):
    """
    Block 1: has withdrawal-eligible validators. Payload does not arrive.
    Block 2: no new withdrawal-eligible validators.
    Payload for Block 2: includes Block 1's stale withdrawals (W_1) → accepted.
    """
    pre_state, signed_block_1, block_1_withdrawals = _setup_missed_payload_with_withdrawals(
        spec, state
    )

    # Process Block 2 (parent empty → process_withdrawals returns early)
    block_2 = build_empty_block_for_next_slot(spec, state)
    signed_block_2 = state_transition_and_sign_block(spec, state, block_2)

    yield "pre", pre_state
    yield "blocks", [signed_block_1, signed_block_2]
    yield "post", state

    # No withdrawable validators remain
    current_expected = get_expected_withdrawals(spec, state)
    assert len(current_expected) == 0

    # Despite no current withdrawals, payload must include W_1 — and it's accepted
    satisfying = spec.ProgressiveList[spec.Withdrawal](block_1_withdrawals)
    assert _attempt_payload_with_withdrawals(spec, state, satisfying)


@with_gloas_and_later
@spec_state_test
def test_missed_payload_next_block_without_withdrawals_unsatisfying_payload(spec, state):
    """
    Block 1: has withdrawal-eligible validators. Payload does not arrive.
    Block 2: no new withdrawal-eligible validators.
    Payload for Block 2: includes empty withdrawals (not W_1) → rejected.
    """
    pre_state, signed_block_1, _ = _setup_missed_payload_with_withdrawals(spec, state)

    # Process Block 2 (parent empty → process_withdrawals returns early)
    block_2 = build_empty_block_for_next_slot(spec, state)
    signed_block_2 = state_transition_and_sign_block(spec, state, block_2)

    yield "pre", pre_state
    yield "blocks", [signed_block_1, signed_block_2]
    yield "post", state

    # No withdrawable validators remain
    current_expected = get_expected_withdrawals(spec, state)
    assert len(current_expected) == 0

    # An empty payload is rejected — it must include W_1
    empty_withdrawals = spec.ProgressiveList[spec.Withdrawal]()
    assert not _attempt_payload_with_withdrawals(spec, state, empty_withdrawals)


@with_gloas_and_later
@spec_state_test
def test_process_parent_execution_payload__wrong_execution_requests_root(spec, state):
    """
    Test that process_parent_execution_payload rejects a block whose
    parent_execution_requests do not match parent_bid.execution_requests_root
    when the parent block was full.
    """
    set_parent_block_full(spec, state)

    # Build a valid block, then tamper with parent_execution_requests
    block = build_empty_block_for_next_slot(spec, state)

    # Inject a non-empty deposit so the hash diverges from the committed root
    block.body.parent_execution_requests = get_non_empty_execution_requests(spec)

    yield "pre", state
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield "blocks", [signed_block]
    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_invalid_too_many_proposer_slashings(spec, state):
    num_slashings = spec.MAX_PROPOSER_SLASHINGS + 1
    proposer_slashings = get_valid_proposer_slashings(spec, state, num_slashings)

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.proposer_slashings = proposer_slashings
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield "blocks", [signed_block]
    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_invalid_too_many_attester_slashings(spec, state):
    num_slashings = get_max_attester_slashings(spec) + 1
    full_indices = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[:8]
    per_slashing_length = len(full_indices) // num_slashings
    attester_slashings = [
        get_valid_attester_slashing_by_indices(
            spec,
            state,
            full_indices[i * per_slashing_length : (i + 1) * per_slashing_length],
            signed_1=True,
            signed_2=True,
        )
        for i in range(num_slashings)
    ]

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.attester_slashings = attester_slashings
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield "blocks", [signed_block]
    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_invalid_too_many_attestations(spec, state):
    rng = Random(2000)

    next_epoch(spec, state)
    num_attestations = get_max_attestations(spec) + 1
    attestations = get_random_attestations(spec, state, rng, num_attestations)

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.attestations = attestations
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield "blocks", [signed_block]
    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_invalid_too_many_deposits(spec, state):
    num_deposits = spec.MAX_DEPOSITS + 1
    validator_index = len(state.validators)
    amount = spec.MIN_ACTIVATION_BALANCE

    deposit_data_list = [spec.DepositData() for _ in range(state.eth1_deposit_index)]
    for _ in range(num_deposits):
        deposit_data = build_deposit_data(
            spec,
            pubkeys[validator_index],
            privkeys[validator_index],
            amount,
            withdrawal_credentials=b"\x00" * 32,
            signed=True,
        )
        deposit_data_list.append(deposit_data)

    deposits = []
    deposit_root = None
    for i in range(state.eth1_deposit_index, state.eth1_deposit_index + num_deposits):
        deposit, deposit_root, _ = deposit_from_context(spec, deposit_data_list, i)
        deposits.append(deposit)

    state.eth1_data.deposit_root = deposit_root
    state.eth1_data.deposit_count = len(deposit_data_list)

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.deposits = deposits
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield "blocks", [signed_block]
    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_invalid_too_many_voluntary_exits(spec, state):
    next_slots(spec, state, spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH)
    num_exits = spec.MAX_VOLUNTARY_EXITS + 1
    full_indices = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[
        :num_exits
    ]
    signed_exits = prepare_signed_exits(spec, state, full_indices)

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.voluntary_exits = signed_exits
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield "blocks", [signed_block]
    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_invalid_too_many_bls_to_execution_changes(spec, state):
    num_address_changes = spec.MAX_BLS_TO_EXECUTION_CHANGES + 1
    signed_address_changes = [
        get_signed_address_change(spec, state, validator_index=i)
        for i in range(num_address_changes)
    ]

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.bls_to_execution_changes = signed_address_changes
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield "blocks", [signed_block]
    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_invalid_too_many_payload_attestations(spec, state):
    rng = Random(3000)

    state_transition_and_sign_block(spec, state, build_empty_block_for_next_slot(spec, state))

    payload_attestations = []
    for _ in range(spec.MAX_PAYLOAD_ATTESTATIONS + 1):
        payload_attestations.extend(get_random_payload_attestations(spec, state, rng))
    assert len(payload_attestations) > spec.MAX_PAYLOAD_ATTESTATIONS

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.payload_attestations = payload_attestations
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield "blocks", [signed_block]
    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_builder_payment_after_missed_epochs(spec, state):
    """
    Test that a builder is correctly charged when their canonical payload
    is processed after 2+ epochs of missed blocks.
    """
    # Advance to get finalization
    for _ in range(4):
        next_epoch_with_full_participation(spec, state)
    assert state.finalized_checkpoint.epoch == 2

    # Build Block 1 with a non-zero value bid from a builder
    block_1 = build_empty_block_for_next_slot(spec, state)
    builder_index = 0
    value = spec.Gwei(1000000)  # 0.001 ETH
    fee_recipient = b"\xab" * 20

    bid = block_1.body.signed_execution_payload_bid.message
    bid.builder_index = builder_index
    bid.value = value
    bid.fee_recipient = fee_recipient
    bid.execution_requests_root = spec.hash_tree_root(spec.ExecutionRequests())

    # Chain onto the previous bid so both block_1 and block_2 see a FULL parent
    # TODO(jtraglia): make this less hacky
    bid.parent_block_hash = state.latest_block_hash
    bid.block_hash = state.latest_block_hash

    # Sign the bid with the builder's private key
    signature = spec.get_execution_payload_bid_signature(
        state, bid, builder_privkeys[builder_index]
    )
    block_1.body.signed_execution_payload_bid = spec.SignedExecutionPayloadBid(
        message=bid,
        signature=signature,
    )

    # Ensure builder can cover the bid
    state.builders[builder_index].balance = spec.MIN_DEPOSIT_AMOUNT + value

    yield "pre", state

    # Process Block 1 — creates a pending payment for the builder
    signed_block_1 = state_transition_and_sign_block(spec, state, block_1)

    # Verify pending payment was created
    payment_idx = spec.SLOTS_PER_EPOCH + block_1.slot % spec.SLOTS_PER_EPOCH
    payment = state.builder_pending_payments[payment_idx]
    assert payment.withdrawal.amount == value
    assert payment.withdrawal.builder_index == builder_index
    assert payment.weight == 0

    pre_builder_balance = state.builders[builder_index].balance

    # Build Block 2 with 2+ epochs of missed slots. During the slot advancement,
    # process_builder_pending_payments runs at each epoch boundary:
    #   1st boundary: shifts payment from second half to first half
    #   2nd boundary: checks quorum on first half — weight 0 < quorum → evicted
    # When Block 2 is processed, parent is FULL so apply_parent_execution_payload
    # runs. Since parent_epoch is older than previous_epoch, payment_index is None.
    # The fix creates the withdrawal directly from the bid in this case.
    block_1_epoch = spec.compute_epoch_at_slot(block_1.slot)
    block_2_slot = (block_1_epoch + 2) * spec.SLOTS_PER_EPOCH + 1
    block_2 = build_empty_block(spec, state, slot=block_2_slot)
    signed_block_2 = state_transition_and_sign_block(spec, state, block_2)

    yield "blocks", [signed_block_1, signed_block_2]
    yield "post", state

    # Verify apply_parent_execution_payload actually ran (parent was FULL)
    parent_slot_index = bid.slot % spec.SLOTS_PER_HISTORICAL_ROOT
    assert state.execution_payload_availability[parent_slot_index] == 0b1

    # Verify the builder was charged — balance decreased by the bid value
    assert state.builders[builder_index].balance == pre_builder_balance - value


@with_gloas_and_later
@spec_state_test
def test_voluntary_exit_fails_after_parent_payload_withdrawal_request(spec, state):
    """
    Test that a voluntary exit is rejected when the parent payload's deferred
    execution requests have already initiated the validator's exit.
    """
    validator_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]

    # Move state forward SHARD_COMMITTEE_PERIOD epochs so the validator can exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    # Set up the parent block as FULL with a bid that commits to a full-exit
    # withdrawal request for the validator.
    set_parent_block_full(spec, state)
    withdrawal_request = prepare_withdrawal_request(spec, state, validator_index)
    requests = spec.ExecutionRequests(
        withdrawals=spec.List[spec.WithdrawalRequest, spec.MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD](
            [withdrawal_request]
        ),
    )
    state.latest_execution_payload_bid.execution_requests_root = spec.hash_tree_root(requests)

    # Build a block that delivers the parent's deferred execution requests
    # (initiating the validator's exit) and also tries to voluntarily exit the
    # same validator. The voluntary exit fails the FAR_FUTURE_EPOCH check.
    signed_exits = prepare_signed_exits(spec, state, [validator_index])
    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests
    block.body.voluntary_exits = signed_exits

    yield "pre", state
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)
    yield "blocks", [signed_block]
    yield "post", None
