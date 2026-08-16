from eth_consensus_specs.test.context import (
    expect_assertion_error,
    spec_state_test,
    with_eip8205_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.builder_deposit_requests import (
    prepare_process_builder_deposit_request,
)
from eth_consensus_specs.test.helpers.constants import MINIMAL
from eth_consensus_specs.test.helpers.deposits import prepare_deposit_request
from eth_consensus_specs.test.helpers.keys import (
    builder_pubkey_to_privkey,
    builder_pubkeys,
    privkeys,
    pubkeys,
)
from eth_consensus_specs.test.helpers.preregistrations import (
    build_preregistration_request,
    preregistration_withdrawal_credentials,
)
from eth_consensus_specs.test.helpers.withdrawals import set_parent_block_full

# A key pair that is not part of the genesis validator set
FRESH_PUBKEY = pubkeys[-1]
FRESH_PRIVKEY = privkeys[-1]


def _commit_parent_requests(spec, state, requests, requests_root=None):
    """
    Configure state so the parent block was FULL and the parent bid commits to
    ``requests`` (or to an explicit ``requests_root``).
    """
    set_parent_block_full(spec, state)
    bid = state.latest_execution_payload_bid
    if requests_root is None:
        requests_root = spec.hash_tree_root(requests)
    bid.execution_requests_root = requests_root


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


def _stored_preregistration(spec, pubkey, expiry_slot):
    return spec.StoredPreregistration(
        pubkey=pubkey,
        withdrawal_credentials=preregistration_withdrawal_credentials(spec),
        expiry_slot=spec.Slot(expiry_slot),
    )


@with_eip8205_and_later
@spec_state_test
def test_parent_payload_preregistration_stored(spec, state):
    """
    A preregistration request in the parent's execution requests is stored with
    an absolute expiry slot derived from the child state's slot.
    """
    withdrawal_credentials = preregistration_withdrawal_credentials(spec)
    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, withdrawal_credentials
    )
    requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests([request]),
    )
    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)

    assert len(state.validator_preregistrations) == 1
    stored = state.validator_preregistrations[0]
    assert stored.pubkey == FRESH_PUBKEY
    assert stored.withdrawal_credentials == withdrawal_credentials
    # Parent execution requests are applied at the child state slot
    assert stored.expiry_slot == block.slot + spec.PREREGISTRATION_EXPIRY_SLOTS


@with_eip8205_and_later
@spec_state_test
def test_parent_payload_deposit_first_for_same_pubkey(spec, state):
    """
    A deposit and a preregistration for the same pubkey in one execution payload
    retain the deposit-first behavior: the deposit is queued unconditionally and
    the preregistration is rejected against the fresh pending deposit. The two
    requests carry different withdrawal credentials so that the processing
    orders diverge: with preregistrations processed first, the binding would be
    stored and the mismatched deposit discarded instead.
    """
    deposit_request = prepare_deposit_request(
        spec,
        len(state.validators),
        spec.MIN_ACTIVATION_BALANCE,
        pubkey=FRESH_PUBKEY,
        privkey=FRESH_PRIVKEY,
        withdrawal_credentials=preregistration_withdrawal_credentials(spec),
        signed=True,
    )
    preregistration_request = build_preregistration_request(
        spec,
        state,
        FRESH_PUBKEY,
        FRESH_PRIVKEY,
        preregistration_withdrawal_credentials(spec, b"\x77"),
    )
    requests = spec.ExecutionRequests(
        deposits=spec.DepositRequests([deposit_request]),
        preregistrations=spec.PreregistrationRequests([preregistration_request]),
    )
    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests
    pre_pending_deposits_len = len(state.pending_deposits)

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)

    assert len(state.pending_deposits) == pre_pending_deposits_len + 1
    assert len(state.validator_preregistrations) == 0


@with_eip8205_and_later
@spec_state_test
def test_parent_payload_builder_deposit_does_not_consume_binding(spec, state):
    """
    Builder deposit requests neither consume nor enforce validator
    preregistrations: a builder deposit for a bound pubkey leaves the binding
    untouched and is processed through the builder flow.
    """
    builder_pubkey = builder_pubkeys[len(state.builders)]
    builder_privkey = builder_pubkey_to_privkey[builder_pubkey]

    # Bind the pubkey with a validator preregistration first
    preregistration_request = build_preregistration_request(
        spec, state, builder_pubkey, builder_privkey, preregistration_withdrawal_credentials(spec)
    )
    spec.process_preregistration_request(state, preregistration_request)
    assert len(state.validator_preregistrations) == 1

    builder_deposit_request = prepare_process_builder_deposit_request(
        spec, state, pubkey=builder_pubkey, signed=True
    )
    requests = spec.ExecutionRequests(
        builder_deposits=spec.BuilderDepositRequests([builder_deposit_request]),
    )
    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests
    pre_builder_count = len(state.builders)

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)

    # The builder was onboarded and the validator preregistration is untouched
    assert len(state.builders) == pre_builder_count + 1
    assert len(state.validator_preregistrations) == 1
    assert state.validator_preregistrations[0].pubkey == builder_pubkey


@with_eip8205_and_later
@spec_state_test
@with_presets([MINIMAL], reason="advancing through the slot-expiry window is slow on mainnet")
def test_parent_payload_deposit_protected_up_to_expiry_boundary(spec, state):
    """
    A mismatched deposit in the final covered payload slot is discarded, even
    when missed slots delay its application past the absolute expiry slot.
    """
    admission_slot = spec.Slot(1)
    expiry_slot = spec.Slot(admission_slot + spec.PREREGISTRATION_EXPIRY_SLOTS)
    spec.process_slots(state, admission_slot)
    state.validator_preregistrations.append(
        _stored_preregistration(spec, FRESH_PUBKEY, expiry_slot)
    )

    deposit_request = prepare_deposit_request(
        spec,
        len(state.validators),
        spec.MIN_ACTIVATION_BALANCE,
        pubkey=FRESH_PUBKEY,
        privkey=FRESH_PRIVKEY,
        withdrawal_credentials=preregistration_withdrawal_credentials(spec, b"\x77"),
        signed=True,
    )
    requests = spec.ExecutionRequests(deposits=spec.DepositRequests([deposit_request]))
    spec.process_slots(state, spec.Slot(expiry_slot - 1))
    _commit_parent_requests(spec, state, requests)
    # The parent payload was created in the final covered slot
    state.latest_execution_payload_bid.slot = spec.Slot(expiry_slot - 1)

    # Missed slots delay application until the next epoch boundary. The sweep
    # keeps the binding while the covered payload is still outstanding.
    next_epoch = spec.Epoch(spec.get_current_epoch(state) + 1)
    spec.process_slots(state, spec.compute_start_slot_at_epoch(next_epoch))
    assert len(state.validator_preregistrations) == 1

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests
    pre_pending_deposits_len = len(state.pending_deposits)

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)

    # The mismatched deposit was discarded and the binding remains active
    assert len(state.pending_deposits) == pre_pending_deposits_len
    assert len(state.validator_preregistrations) == 1


@with_eip8205_and_later
@spec_state_test
@with_presets([MINIMAL], reason="advancing through the slot-expiry window is slow on mainnet")
def test_parent_payload_deposit_unprotected_after_expiry_boundary(spec, state):
    """
    A payload created exactly at a mid-epoch expiry slot is no longer covered:
    the binding is not enforced even though the record is still physically
    present, and the deposit passes through unconditionally.
    """
    admission_slot = spec.Slot(1)
    expiry_slot = spec.Slot(admission_slot + spec.PREREGISTRATION_EXPIRY_SLOTS)
    spec.process_slots(state, admission_slot)
    state.validator_preregistrations.append(
        _stored_preregistration(spec, FRESH_PUBKEY, expiry_slot)
    )

    deposit_request = prepare_deposit_request(
        spec,
        len(state.validators),
        spec.MIN_ACTIVATION_BALANCE,
        pubkey=FRESH_PUBKEY,
        privkey=FRESH_PRIVKEY,
        withdrawal_credentials=preregistration_withdrawal_credentials(spec, b"\x77"),
        signed=True,
    )
    requests = spec.ExecutionRequests(deposits=spec.DepositRequests([deposit_request]))
    spec.process_slots(state, expiry_slot)
    _commit_parent_requests(spec, state, requests)

    # Earlier epoch sweeps used an older bid and kept the record. The payload
    # now being applied was created exactly at the expiry slot.
    state.latest_execution_payload_bid.slot = expiry_slot
    assert len(state.validator_preregistrations) == 1

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests
    pre_pending_deposits_len = len(state.pending_deposits)

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)

    # The record is still physically present but was not enforced
    assert len(state.pending_deposits) == pre_pending_deposits_len + 1
    assert len(state.validator_preregistrations) == 1


@with_eip8205_and_later
@spec_state_test
@with_presets([MINIMAL], reason="filling the preregistration list is slow on mainnet")
def test_parent_payload_expired_records_garbage_collected(spec, state):
    """
    The epoch-boundary sweep physically removes expired records, and a
    preregistration in a later payload is admitted into the compacted list.
    """
    for index in range(spec.PREREGISTRATIONS_LIMIT):
        state.validator_preregistrations.append(
            _stored_preregistration(
                spec,
                spec.BLSPubkey(index.to_bytes(48, "little")),
                spec.PREREGISTRATION_EXPIRY_SLOTS,
            )
        )

    # The records remain protected through the transition at their deadline:
    # the outstanding bid is still from an earlier covered slot.
    spec.process_slots(state, spec.PREREGISTRATION_EXPIRY_SLOTS)
    assert len(state.validator_preregistrations) == spec.PREREGISTRATIONS_LIMIT

    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, preregistration_withdrawal_credentials(spec)
    )
    requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests([request]),
    )
    _commit_parent_requests(spec, state, requests)
    state.latest_execution_payload_bid.slot = state.slot

    # Missed slots delay the payload until the next epoch boundary, whose
    # sweep removes the now-expired records before applying the payload.
    next_epoch = spec.Epoch(spec.get_current_epoch(state) + 1)
    spec.process_slots(state, spec.compute_start_slot_at_epoch(next_epoch))
    assert len(state.validator_preregistrations) == 0

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)

    # All expired records were freed and the new preregistration was admitted
    assert len(state.validator_preregistrations) == 1
    assert state.validator_preregistrations[0].pubkey == FRESH_PUBKEY


@with_eip8205_and_later
@spec_state_test
def test_parent_payload_multiple_preregistrations_stored(spec, state):
    """
    All preregistration requests in a single payload are stored in submission
    order, up to ``MAX_PREREGISTRATION_REQUESTS_PER_PAYLOAD``.
    """
    count = spec.MAX_PREREGISTRATION_REQUESTS_PER_PAYLOAD
    key_pairs = [(pubkeys[-1 - index], privkeys[-1 - index]) for index in range(count)]
    requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests(
            [
                build_preregistration_request(
                    spec,
                    state,
                    pubkey,
                    privkey,
                    preregistration_withdrawal_credentials(spec, bytes([0x50 + index])),
                )
                for index, (pubkey, privkey) in enumerate(key_pairs)
            ]
        ),
    )
    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)

    assert [p.pubkey for p in state.validator_preregistrations] == [
        pubkey for pubkey, _ in key_pairs
    ]


@with_eip8205_and_later
@spec_state_test
def test_parent_payload_max_preregistrations(spec, state):
    requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests(
            [spec.PreregistrationRequest()] * spec.MAX_PREREGISTRATION_REQUESTS_PER_PAYLOAD
        ),
    )
    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)


@with_eip8205_and_later
@spec_state_test
def test_parent_payload_invalid_too_many_preregistrations(spec, state):
    requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests(
            [spec.PreregistrationRequest()] * (spec.MAX_PREREGISTRATION_REQUESTS_PER_PAYLOAD + 1)
        ),
    )
    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block, valid=False)
