from eth_consensus_specs.test.context import (
    always_bls,
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
from eth_consensus_specs.test.helpers.deposits import (
    prepare_deposit_request,
    prepare_pending_deposit,
)
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


def run_parent_payload_processing_with_requests(spec, state, requests):
    """
    Commit ``requests`` to the parent bid and apply them through the next block.
    """
    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)


def _stored_preregistration(spec, pubkey, expiry_slot):
    return spec.StoredPreregistration(
        pubkey=pubkey,
        withdrawal_credentials=preregistration_withdrawal_credentials(spec),
        expiry_slot=spec.Slot(expiry_slot),
    )


def _fill_preregistrations(spec, state, count, expiry_slot):
    """
    Append ``count`` filler records with the given absolute expiry slot.
    """
    for index in range(count):
        state.validator_preregistrations.append(
            _stored_preregistration(spec, spec.BLSPubkey(index.to_bytes(48, "little")), expiry_slot)
        )


def _deposit_request(spec, state, withdrawal_credentials, pubkey=None, privkey=None, signed=True):
    return prepare_deposit_request(
        spec,
        len(state.validators),
        spec.MIN_ACTIVATION_BALANCE,
        pubkey=FRESH_PUBKEY if pubkey is None else pubkey,
        privkey=FRESH_PRIVKEY if privkey is None else privkey,
        withdrawal_credentials=withdrawal_credentials,
        signed=signed,
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
        preregistrations=spec.PreregistrationRequests(data=[request]),
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
        deposits=spec.DepositRequests(data=[deposit_request]),
        preregistrations=spec.PreregistrationRequests(data=[preregistration_request]),
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
        builder_deposits=spec.BuilderDepositRequests(data=[builder_deposit_request]),
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
    requests = spec.ExecutionRequests(deposits=spec.DepositRequests(data=[deposit_request]))
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
    requests = spec.ExecutionRequests(deposits=spec.DepositRequests(data=[deposit_request]))
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
def test_parent_payload_max_preregistrations(spec, state):
    """
    A payload carrying ``MAX_PREREGISTRATION_REQUESTS_PER_PAYLOAD`` requests is
    valid, and all of them are stored in submission order.
    """
    count = spec.MAX_PREREGISTRATION_REQUESTS_PER_PAYLOAD
    key_pairs = [(pubkeys[-1 - index], privkeys[-1 - index]) for index in range(count)]
    requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests(
            data=[
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
def test_parent_payload_invalid_too_many_preregistrations(spec, state):
    requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests(
            data=[spec.PreregistrationRequest()]
            * (spec.MAX_PREREGISTRATION_REQUESTS_PER_PAYLOAD + 1)
        ),
    )
    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block, valid=False)


@with_eip8205_and_later
@spec_state_test
@always_bls
def test_parent_payload_preregistration_invalid_signature_ignored(spec, state):
    """
    A preregistration request with an invalid signature is discarded.
    """
    request = build_preregistration_request(
        spec,
        state,
        FRESH_PUBKEY,
        FRESH_PRIVKEY,
        preregistration_withdrawal_credentials(spec),
        valid_signature=False,
    )
    requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests(data=[request]),
    )

    yield from run_parent_payload_processing_with_requests(spec, state, requests)

    assert len(state.validator_preregistrations) == 0


@with_eip8205_and_later
@spec_state_test
@always_bls
def test_parent_payload_preregistration_signature_over_different_credentials_ignored(spec, state):
    """
    The signature covers the withdrawal credentials: a valid signature over
    different credentials does not authorize the request.
    """
    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, preregistration_withdrawal_credentials(spec)
    )
    request.withdrawal_credentials = preregistration_withdrawal_credentials(spec, b"\x77")
    requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests(data=[request]),
    )

    yield from run_parent_payload_processing_with_requests(spec, state, requests)

    assert len(state.validator_preregistrations) == 0


@with_eip8205_and_later
@spec_state_test
@always_bls
def test_parent_payload_preregistration_wrong_genesis_validators_root_ignored(spec, state):
    """
    The signing domain commits to ``genesis_validators_root``: a request signed
    for another chain is not valid on this one.
    """
    other_state = state.copy()
    other_state.genesis_validators_root = spec.Root(b"\xaa" * 32)
    request = build_preregistration_request(
        spec, other_state, FRESH_PUBKEY, FRESH_PRIVKEY, preregistration_withdrawal_credentials(spec)
    )
    requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests(data=[request]),
    )

    yield from run_parent_payload_processing_with_requests(spec, state, requests)

    assert len(state.validator_preregistrations) == 0


@with_eip8205_and_later
@spec_state_test
def test_parent_payload_preregistration_active_binding_ignored(spec, state):
    """
    An active binding makes a new request for the same pubkey a no-op, whether
    the duplicate is conflicting or exact. The stored expiry slot is not
    refreshed.
    """
    state.validator_preregistrations.append(
        _stored_preregistration(spec, FRESH_PUBKEY, spec.PREREGISTRATION_EXPIRY_SLOTS)
    )
    pre_binding = state.validator_preregistrations[0].copy()

    conflicting_request = build_preregistration_request(
        spec,
        state,
        FRESH_PUBKEY,
        FRESH_PRIVKEY,
        preregistration_withdrawal_credentials(spec, b"\x77"),
    )
    duplicate_request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, preregistration_withdrawal_credentials(spec)
    )
    requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests(
            data=[conflicting_request, duplicate_request]
        ),
    )

    yield from run_parent_payload_processing_with_requests(spec, state, requests)

    assert len(state.validator_preregistrations) == 1
    assert state.validator_preregistrations[0] == pre_binding


@with_eip8205_and_later
@spec_state_test
def test_parent_payload_preregistration_replaces_expired_binding(spec, state):
    """
    A new request for a pubkey with an expired record replaces that record in
    place, without waiting for the garbage-collection sweep.
    """
    state.validator_preregistrations.append(_stored_preregistration(spec, FRESH_PUBKEY, 0))

    new_withdrawal_credentials = preregistration_withdrawal_credentials(spec, b"\x77")
    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, new_withdrawal_credentials
    )
    requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests(data=[request]),
    )

    yield from run_parent_payload_processing_with_requests(spec, state, requests)

    assert len(state.validator_preregistrations) == 1
    stored = state.validator_preregistrations[0]
    assert stored.withdrawal_credentials == new_withdrawal_credentials
    assert stored.expiry_slot == state.slot + spec.PREREGISTRATION_EXPIRY_SLOTS


@with_eip8205_and_later
@spec_state_test
def test_parent_payload_preregistration_existing_validator_ignored(spec, state):
    """
    A pubkey that already belongs to a validator cannot be preregistered.
    """
    request = build_preregistration_request(
        spec,
        state,
        state.validators[0].pubkey,
        privkeys[0],
        preregistration_withdrawal_credentials(spec),
    )
    requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests(data=[request]),
    )

    yield from run_parent_payload_processing_with_requests(spec, state, requests)

    assert len(state.validator_preregistrations) == 0


@with_eip8205_and_later
@spec_state_test
def test_parent_payload_preregistration_existing_builder_pubkey_stored(spec, state):
    """
    The builder registry is independent of validator preregistrations: a pubkey
    that already belongs to a builder can still be preregistered.
    """
    builder_pubkey = state.builders[0].pubkey
    builder_privkey = builder_pubkey_to_privkey[builder_pubkey]
    request = build_preregistration_request(
        spec, state, builder_pubkey, builder_privkey, preregistration_withdrawal_credentials(spec)
    )
    requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests(data=[request]),
    )

    yield from run_parent_payload_processing_with_requests(spec, state, requests)

    assert len(state.validator_preregistrations) == 1
    assert state.validator_preregistrations[0].pubkey == builder_pubkey


@with_eip8205_and_later
@spec_state_test
def test_parent_payload_preregistration_pending_deposit_ignored(spec, state):
    """
    A pubkey with a valid pending deposit cannot be preregistered.
    """
    withdrawal_credentials = preregistration_withdrawal_credentials(spec)
    state.pending_deposits.append(
        prepare_pending_deposit(
            spec,
            len(state.validators),
            spec.MIN_ACTIVATION_BALANCE,
            pubkey=FRESH_PUBKEY,
            privkey=FRESH_PRIVKEY,
            withdrawal_credentials=withdrawal_credentials,
            signed=True,
        )
    )
    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, withdrawal_credentials
    )
    requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests(data=[request]),
    )

    yield from run_parent_payload_processing_with_requests(spec, state, requests)

    assert len(state.validator_preregistrations) == 0


@with_eip8205_and_later
@spec_state_test
@always_bls
def test_parent_payload_preregistration_invalid_pending_deposit_does_not_block(spec, state):
    """
    A pending deposit with an invalid signature does not bind the pubkey, so the
    preregistration is stored.
    """
    withdrawal_credentials = preregistration_withdrawal_credentials(spec)
    state.pending_deposits.append(
        prepare_pending_deposit(
            spec,
            len(state.validators),
            spec.MIN_ACTIVATION_BALANCE,
            pubkey=FRESH_PUBKEY,
            privkey=FRESH_PRIVKEY,
            withdrawal_credentials=withdrawal_credentials,
            signed=False,
        )
    )
    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, withdrawal_credentials
    )
    requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests(data=[request]),
    )

    yield from run_parent_payload_processing_with_requests(spec, state, requests)

    assert len(state.validator_preregistrations) == 1
    assert state.validator_preregistrations[0].pubkey == FRESH_PUBKEY


@with_eip8205_and_later
@spec_state_test
@with_presets([MINIMAL], reason="filling the preregistration list is slow on mainnet")
def test_parent_payload_preregistration_state_full_ignored(spec, state):
    """
    A request is discarded when ``PREREGISTRATIONS_LIMIT`` records are active.
    """
    _fill_preregistrations(
        spec, state, spec.PREREGISTRATIONS_LIMIT, spec.PREREGISTRATION_EXPIRY_SLOTS
    )

    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, preregistration_withdrawal_credentials(spec)
    )
    requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests(data=[request]),
    )

    yield from run_parent_payload_processing_with_requests(spec, state, requests)

    assert len(state.validator_preregistrations) == spec.PREREGISTRATIONS_LIMIT
    assert FRESH_PUBKEY not in [p.pubkey for p in state.validator_preregistrations]


@with_eip8205_and_later
@spec_state_test
@with_presets([MINIMAL], reason="filling the preregistration list is slow on mainnet")
def test_parent_payload_preregistration_admitted_when_full_of_expired_records(spec, state):
    """
    Expired records do not count against the capacity limit, so admission does
    not have to wait for the garbage-collection sweep.
    """
    _fill_preregistrations(spec, state, spec.PREREGISTRATIONS_LIMIT, 0)

    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, preregistration_withdrawal_credentials(spec)
    )
    requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests(data=[request]),
    )

    yield from run_parent_payload_processing_with_requests(spec, state, requests)

    # The new record is appended; expired records remain until the sweep
    assert len(state.validator_preregistrations) == spec.PREREGISTRATIONS_LIMIT + 1
    assert state.validator_preregistrations[spec.PREREGISTRATIONS_LIMIT].pubkey == FRESH_PUBKEY


@with_eip8205_and_later
@spec_state_test
@with_presets([MINIMAL], reason="filling the preregistration list is slow on mainnet")
def test_parent_payload_preregistration_replacement_respects_active_limit(spec, state):
    """
    The capacity check applies to replacements as well: replaying an expired
    record must not create an active binding beyond the limit.
    """
    _fill_preregistrations(
        spec, state, spec.PREREGISTRATIONS_LIMIT - 1, spec.PREREGISTRATION_EXPIRY_SLOTS
    )
    expired_index = len(state.validator_preregistrations)
    state.validator_preregistrations.append(_stored_preregistration(spec, pubkeys[-2], 0))

    # The first request fills the last active slot, the replay is then rejected
    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, preregistration_withdrawal_credentials(spec)
    )
    expired_request = build_preregistration_request(
        spec, state, pubkeys[-2], privkeys[-2], preregistration_withdrawal_credentials(spec)
    )
    requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests(data=[request, expired_request]),
    )

    yield from run_parent_payload_processing_with_requests(spec, state, requests)

    assert len(state.validator_preregistrations) == spec.PREREGISTRATIONS_LIMIT + 1
    assert state.validator_preregistrations[expired_index].expiry_slot == 0
    assert state.validator_preregistrations[spec.PREREGISTRATIONS_LIMIT].pubkey == FRESH_PUBKEY


@with_eip8205_and_later
@spec_state_test
@with_presets([MINIMAL], reason="filling the preregistration list is slow on mainnet")
def test_parent_payload_preregistration_replacement_admitted_when_physically_full(spec, state):
    """
    The physical length equals the limit, but only active records count, so
    replaying the expired record replaces it in place.
    """
    _fill_preregistrations(
        spec, state, spec.PREREGISTRATIONS_LIMIT - 1, spec.PREREGISTRATION_EXPIRY_SLOTS
    )
    expired_index = len(state.validator_preregistrations)
    state.validator_preregistrations.append(_stored_preregistration(spec, pubkeys[-2], 0))

    request = build_preregistration_request(
        spec, state, pubkeys[-2], privkeys[-2], preregistration_withdrawal_credentials(spec)
    )
    requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests(data=[request]),
    )

    yield from run_parent_payload_processing_with_requests(spec, state, requests)

    assert len(state.validator_preregistrations) == spec.PREREGISTRATIONS_LIMIT
    stored = state.validator_preregistrations[expired_index]
    assert stored.pubkey == pubkeys[-2]
    assert stored.expiry_slot == state.slot + spec.PREREGISTRATION_EXPIRY_SLOTS


@with_eip8205_and_later
@spec_state_test
def test_parent_payload_deposit_consumes_matching_binding(spec, state):
    """
    A deposit matching the bound withdrawal credentials is queued and consumes
    the binding.
    """
    withdrawal_credentials = preregistration_withdrawal_credentials(spec)
    state.validator_preregistrations.append(
        _stored_preregistration(spec, FRESH_PUBKEY, spec.PREREGISTRATION_EXPIRY_SLOTS)
    )

    deposit_request = _deposit_request(spec, state, withdrawal_credentials)
    requests = spec.ExecutionRequests(deposits=spec.DepositRequests(data=[deposit_request]))
    pre_pending_deposits_len = len(state.pending_deposits)

    yield from run_parent_payload_processing_with_requests(spec, state, requests)

    assert len(state.pending_deposits) == pre_pending_deposits_len + 1
    assert len(state.validator_preregistrations) == 0


@with_eip8205_and_later
@spec_state_test
def test_parent_payload_deposit_mismatched_credentials_discarded(spec, state):
    """
    A deposit that does not match the bound withdrawal credentials is discarded
    and leaves the binding untouched.
    """
    state.validator_preregistrations.append(
        _stored_preregistration(spec, FRESH_PUBKEY, spec.PREREGISTRATION_EXPIRY_SLOTS)
    )
    pre_binding = state.validator_preregistrations[0].copy()

    deposit_request = _deposit_request(
        spec, state, preregistration_withdrawal_credentials(spec, b"\x77")
    )
    requests = spec.ExecutionRequests(deposits=spec.DepositRequests(data=[deposit_request]))
    pre_pending_deposits_len = len(state.pending_deposits)

    yield from run_parent_payload_processing_with_requests(spec, state, requests)

    assert len(state.pending_deposits) == pre_pending_deposits_len
    assert len(state.validator_preregistrations) == 1
    assert state.validator_preregistrations[0] == pre_binding


@with_eip8205_and_later
@spec_state_test
@always_bls
def test_parent_payload_deposit_invalid_signature_discarded(spec, state):
    """
    A deposit with an invalid signature is discarded while a binding is active,
    so that it cannot consume the preregistration.
    """
    withdrawal_credentials = preregistration_withdrawal_credentials(spec)
    state.validator_preregistrations.append(
        _stored_preregistration(spec, FRESH_PUBKEY, spec.PREREGISTRATION_EXPIRY_SLOTS)
    )
    pre_binding = state.validator_preregistrations[0].copy()

    deposit_request = _deposit_request(spec, state, withdrawal_credentials, signed=False)
    requests = spec.ExecutionRequests(deposits=spec.DepositRequests(data=[deposit_request]))
    pre_pending_deposits_len = len(state.pending_deposits)

    yield from run_parent_payload_processing_with_requests(spec, state, requests)

    assert len(state.pending_deposits) == pre_pending_deposits_len
    assert len(state.validator_preregistrations) == 1
    assert state.validator_preregistrations[0] == pre_binding


@with_eip8205_and_later
@spec_state_test
def test_parent_payload_deposit_without_binding_appended(spec, state):
    """
    Without a binding, even a deposit with an invalid signature is queued,
    preserving the inherited behavior.
    """
    deposit_request = _deposit_request(
        spec, state, preregistration_withdrawal_credentials(spec), signed=False
    )
    requests = spec.ExecutionRequests(deposits=spec.DepositRequests(data=[deposit_request]))
    pre_pending_deposits_len = len(state.pending_deposits)

    yield from run_parent_payload_processing_with_requests(spec, state, requests)

    assert len(state.pending_deposits) == pre_pending_deposits_len + 1


@with_eip8205_and_later
@spec_state_test
def test_parent_payload_second_deposit_after_binding_consumed(spec, state):
    """
    Once the binding is consumed by the first matching deposit, a second deposit
    with different withdrawal credentials is queued unconditionally.
    """
    withdrawal_credentials = preregistration_withdrawal_credentials(spec)
    state.validator_preregistrations.append(
        _stored_preregistration(spec, FRESH_PUBKEY, spec.PREREGISTRATION_EXPIRY_SLOTS)
    )

    deposit_request = _deposit_request(spec, state, withdrawal_credentials)
    second_deposit_request = _deposit_request(
        spec, state, preregistration_withdrawal_credentials(spec, b"\x77")
    )
    requests = spec.ExecutionRequests(
        deposits=spec.DepositRequests(data=[deposit_request, second_deposit_request]),
    )
    pre_pending_deposits_len = len(state.pending_deposits)

    yield from run_parent_payload_processing_with_requests(spec, state, requests)

    assert len(state.pending_deposits) == pre_pending_deposits_len + 2
    assert len(state.validator_preregistrations) == 0


@with_eip8205_and_later
@spec_state_test
def test_parent_payload_deposit_removes_binding_preserving_order(spec, state):
    """
    Consuming a binding from the middle of the list preserves the order of the
    remaining records, which is consensus-visible through the state root.
    """
    pubkey_a, pubkey_b, pubkey_c = pubkeys[-1], pubkeys[-2], pubkeys[-3]
    withdrawal_credentials = preregistration_withdrawal_credentials(spec)
    for pubkey in [pubkey_a, pubkey_b, pubkey_c]:
        state.validator_preregistrations.append(
            _stored_preregistration(spec, pubkey, spec.PREREGISTRATION_EXPIRY_SLOTS)
        )

    deposit_request = _deposit_request(
        spec, state, withdrawal_credentials, pubkey=pubkey_b, privkey=privkeys[-2]
    )
    requests = spec.ExecutionRequests(deposits=spec.DepositRequests(data=[deposit_request]))

    yield from run_parent_payload_processing_with_requests(spec, state, requests)

    assert [p.pubkey for p in state.validator_preregistrations] == [pubkey_a, pubkey_c]
