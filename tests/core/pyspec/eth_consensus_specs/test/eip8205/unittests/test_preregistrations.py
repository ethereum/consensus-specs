from eth_consensus_specs.test.context import (
    always_bls,
    spec_state_test,
    with_eip8205_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import MINIMAL
from eth_consensus_specs.test.helpers.deposits import build_deposit_data
from eth_consensus_specs.test.helpers.keys import (
    builder_pubkey_to_privkey,
    privkeys,
    pubkeys,
)
from eth_consensus_specs.test.helpers.preregistrations import (
    build_preregistration_request,
    preregistration_withdrawal_credentials,
)

# A key pair that is not part of the genesis validator set
FRESH_PUBKEY = pubkeys[-1]
FRESH_PRIVKEY = privkeys[-1]


def _build_deposit_request(spec, pubkey, privkey, withdrawal_credentials, valid_signature=True):
    amount = spec.MIN_ACTIVATION_BALANCE
    deposit_data = build_deposit_data(
        spec, pubkey, privkey, amount, withdrawal_credentials, signed=valid_signature
    )
    return spec.DepositRequest(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        amount=amount,
        signature=deposit_data.signature,
        index=0,
    )


def _stored_preregistration(spec, pubkey, expiry_slot=None):
    if expiry_slot is None:
        expiry_slot = spec.PREREGISTRATION_EXPIRY_SLOTS
    return spec.StoredPreregistration(
        pubkey=pubkey,
        withdrawal_credentials=preregistration_withdrawal_credentials(spec),
        expiry_slot=spec.Slot(expiry_slot),
    )


def _expire_logically(spec, state, expiry_slot):
    # Make bindings with the given deadline inactive: the outstanding parent
    # payload was created exactly at their expiry slot
    state.slot = spec.Slot(expiry_slot)
    state.latest_execution_payload_bid.slot = spec.Slot(expiry_slot)


#
# process_preregistration_request
#


@with_eip8205_and_later
@spec_state_test
def test_preregistration_request_valid(spec, state):
    withdrawal_credentials = preregistration_withdrawal_credentials(spec)
    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, withdrawal_credentials
    )

    spec.process_preregistration_request(state, request)

    assert len(state.validator_preregistrations) == 1
    stored = state.validator_preregistrations[0]
    assert stored.pubkey == FRESH_PUBKEY
    assert stored.withdrawal_credentials == withdrawal_credentials
    assert stored.expiry_slot == state.slot + spec.PREREGISTRATION_EXPIRY_SLOTS


@with_eip8205_and_later
@spec_state_test
@always_bls
def test_preregistration_request_invalid_signature_ignored(spec, state):
    request = build_preregistration_request(
        spec,
        state,
        FRESH_PUBKEY,
        FRESH_PRIVKEY,
        preregistration_withdrawal_credentials(spec),
        valid_signature=False,
    )

    spec.process_preregistration_request(state, request)

    assert len(state.validator_preregistrations) == 0


@with_eip8205_and_later
@spec_state_test
@always_bls
def test_preregistration_request_signature_over_different_credentials_ignored(spec, state):
    # The signature covers the withdrawal credentials: a valid signature over
    # different credentials does not authorize this request
    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, preregistration_withdrawal_credentials(spec)
    )
    request.withdrawal_credentials = preregistration_withdrawal_credentials(spec, b"\x77")

    spec.process_preregistration_request(state, request)

    assert len(state.validator_preregistrations) == 0


@with_eip8205_and_later
@spec_state_test
@always_bls
def test_preregistration_request_wrong_genesis_validators_root_ignored(spec, state):
    # The signing domain commits to genesis_validators_root: a request signed
    # for another chain is not valid on this one
    other_state = state.copy()
    other_state.genesis_validators_root = spec.Root(b"\xaa" * 32)
    request = build_preregistration_request(
        spec, other_state, FRESH_PUBKEY, FRESH_PRIVKEY, preregistration_withdrawal_credentials(spec)
    )

    spec.process_preregistration_request(state, request)

    assert len(state.validator_preregistrations) == 0


@with_eip8205_and_later
@spec_state_test
def test_preregistration_request_active_binding_ignored(spec, state):
    withdrawal_credentials = preregistration_withdrawal_credentials(spec)
    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, withdrawal_credentials
    )
    spec.process_preregistration_request(state, request)
    pre_binding = state.validator_preregistrations[0].copy()

    # Advance within the active window so that an erroneous expiry-slot refresh
    # on a duplicate submission would be visible
    state.slot += spec.SLOTS_PER_EPOCH

    # A conflicting duplicate with different withdrawal credentials is a no-op
    conflicting_request = build_preregistration_request(
        spec,
        state,
        FRESH_PUBKEY,
        FRESH_PRIVKEY,
        preregistration_withdrawal_credentials(spec, b"\x77"),
    )
    spec.process_preregistration_request(state, conflicting_request)

    # An exact duplicate is a no-op as well
    spec.process_preregistration_request(state, request)

    assert len(state.validator_preregistrations) == 1
    assert state.validator_preregistrations[0] == pre_binding


@with_eip8205_and_later
@spec_state_test
def test_preregistration_request_overwrites_expired_binding(spec, state):
    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, preregistration_withdrawal_credentials(spec)
    )
    spec.process_preregistration_request(state, request)
    _expire_logically(spec, state, state.validator_preregistrations[0].expiry_slot)

    # A new registration with different withdrawal credentials replaces the
    # expired record in place, without waiting for the garbage-collection sweep
    new_withdrawal_credentials = preregistration_withdrawal_credentials(spec, b"\x77")
    new_request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, new_withdrawal_credentials
    )
    spec.process_preregistration_request(state, new_request)

    assert len(state.validator_preregistrations) == 1
    stored = state.validator_preregistrations[0]
    assert stored.withdrawal_credentials == new_withdrawal_credentials
    assert stored.expiry_slot == state.slot + spec.PREREGISTRATION_EXPIRY_SLOTS


@with_eip8205_and_later
@spec_state_test
def test_preregistration_request_existing_validator_ignored(spec, state):
    existing_pubkey = state.validators[0].pubkey
    request = build_preregistration_request(
        spec, state, existing_pubkey, privkeys[0], preregistration_withdrawal_credentials(spec)
    )

    spec.process_preregistration_request(state, request)

    assert len(state.validator_preregistrations) == 0


@with_eip8205_and_later
@spec_state_test
def test_preregistration_request_existing_builder_pubkey_stored(spec, state):
    # The builder registry is independent of validator preregistrations: a
    # pubkey that already belongs to a builder can still be preregistered
    builder_pubkey = state.builders[0].pubkey
    builder_privkey = builder_pubkey_to_privkey[builder_pubkey]
    request = build_preregistration_request(
        spec, state, builder_pubkey, builder_privkey, preregistration_withdrawal_credentials(spec)
    )

    spec.process_preregistration_request(state, request)

    assert len(state.validator_preregistrations) == 1
    assert state.validator_preregistrations[0].pubkey == builder_pubkey


@with_eip8205_and_later
@spec_state_test
def test_preregistration_request_pending_deposit_ignored(spec, state):
    withdrawal_credentials = preregistration_withdrawal_credentials(spec)
    deposit_request = _build_deposit_request(
        spec, FRESH_PUBKEY, FRESH_PRIVKEY, withdrawal_credentials
    )
    state.pending_deposits.append(
        spec.PendingDeposit(
            pubkey=deposit_request.pubkey,
            withdrawal_credentials=deposit_request.withdrawal_credentials,
            amount=deposit_request.amount,
            signature=deposit_request.signature,
            slot=state.slot,
        )
    )

    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, withdrawal_credentials
    )
    spec.process_preregistration_request(state, request)

    assert len(state.validator_preregistrations) == 0


@with_eip8205_and_later
@spec_state_test
@always_bls
def test_preregistration_request_invalid_pending_deposit_does_not_block(spec, state):
    # A pending deposit with an invalid signature does not bind the pubkey,
    # so the preregistration is stored
    withdrawal_credentials = preregistration_withdrawal_credentials(spec)
    deposit_request = _build_deposit_request(
        spec, FRESH_PUBKEY, FRESH_PRIVKEY, withdrawal_credentials, valid_signature=False
    )
    state.pending_deposits.append(
        spec.PendingDeposit(
            pubkey=deposit_request.pubkey,
            withdrawal_credentials=deposit_request.withdrawal_credentials,
            amount=deposit_request.amount,
            signature=deposit_request.signature,
            slot=state.slot,
        )
    )

    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, withdrawal_credentials
    )
    spec.process_preregistration_request(state, request)

    assert len(state.validator_preregistrations) == 1


@with_eip8205_and_later
@spec_state_test
@with_presets([MINIMAL], reason="filling the preregistration list is slow on mainnet")
def test_preregistration_request_state_full_ignored(spec, state):
    for index in range(spec.PREREGISTRATIONS_LIMIT):
        state.validator_preregistrations.append(
            _stored_preregistration(spec, spec.BLSPubkey(index.to_bytes(48, "little")))
        )

    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, preregistration_withdrawal_credentials(spec)
    )
    spec.process_preregistration_request(state, request)

    assert len(state.validator_preregistrations) == spec.PREREGISTRATIONS_LIMIT
    assert FRESH_PUBKEY not in [p.pubkey for p in state.validator_preregistrations]


@with_eip8205_and_later
@spec_state_test
@with_presets([MINIMAL], reason="filling the preregistration list is slow on mainnet")
def test_preregistration_request_admitted_when_full_of_expired_records(spec, state):
    # Expired records do not count against the capacity limit, so admission
    # does not have to wait for the garbage-collection sweep
    for index in range(spec.PREREGISTRATIONS_LIMIT):
        state.validator_preregistrations.append(
            _stored_preregistration(
                spec,
                spec.BLSPubkey(index.to_bytes(48, "little")),
                expiry_slot=0,
            )
        )

    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, preregistration_withdrawal_credentials(spec)
    )
    spec.process_preregistration_request(state, request)

    # The new record is appended; expired records remain until the sweep
    assert len(state.validator_preregistrations) == spec.PREREGISTRATIONS_LIMIT + 1
    assert state.validator_preregistrations[spec.PREREGISTRATIONS_LIMIT].pubkey == FRESH_PUBKEY


@with_eip8205_and_later
@spec_state_test
@with_presets([MINIMAL], reason="filling the preregistration list is slow on mainnet")
def test_preregistration_request_replacement_respects_active_limit(spec, state):
    # LIMIT - 1 active filler records plus one expired record
    for index in range(spec.PREREGISTRATIONS_LIMIT - 1):
        state.validator_preregistrations.append(
            _stored_preregistration(spec, spec.BLSPubkey(index.to_bytes(48, "little")))
        )
    expired_request = build_preregistration_request(
        spec, state, pubkeys[-2], privkeys[-2], preregistration_withdrawal_credentials(spec)
    )
    expired_index = len(state.validator_preregistrations)
    state.validator_preregistrations.append(
        _stored_preregistration(spec, pubkeys[-2], expiry_slot=0)
    )

    # A new pubkey fills the last active slot
    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, preregistration_withdrawal_credentials(spec)
    )
    spec.process_preregistration_request(state, request)
    assert len(state.validator_preregistrations) == spec.PREREGISTRATIONS_LIMIT + 1

    # Replaying the expired record must not create an active binding beyond
    # the limit: the capacity check also applies to replacements
    spec.process_preregistration_request(state, expired_request)

    assert state.validator_preregistrations[expired_index].expiry_slot == 0
    assert len(state.validator_preregistrations) == spec.PREREGISTRATIONS_LIMIT + 1


@with_eip8205_and_later
@spec_state_test
@with_presets([MINIMAL], reason="filling the preregistration list is slow on mainnet")
def test_preregistration_request_replacement_admitted_when_physically_full(spec, state):
    # LIMIT - 1 active filler records plus one expired record: the physical
    # length equals the limit, but only active records count, so replaying
    # the expired record replaces it in place
    for index in range(spec.PREREGISTRATIONS_LIMIT - 1):
        state.validator_preregistrations.append(
            _stored_preregistration(spec, spec.BLSPubkey(index.to_bytes(48, "little")))
        )
    expired_index = len(state.validator_preregistrations)
    state.validator_preregistrations.append(
        _stored_preregistration(spec, pubkeys[-2], expiry_slot=0)
    )

    request = build_preregistration_request(
        spec, state, pubkeys[-2], privkeys[-2], preregistration_withdrawal_credentials(spec)
    )
    spec.process_preregistration_request(state, request)

    assert len(state.validator_preregistrations) == spec.PREREGISTRATIONS_LIMIT
    stored = state.validator_preregistrations[expired_index]
    assert stored.pubkey == pubkeys[-2]
    assert stored.expiry_slot == state.slot + spec.PREREGISTRATION_EXPIRY_SLOTS


#
# process_deposit_request
#


@with_eip8205_and_later
@spec_state_test
def test_deposit_request_consumes_matching_binding(spec, state):
    withdrawal_credentials = preregistration_withdrawal_credentials(spec)
    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, withdrawal_credentials
    )
    spec.process_preregistration_request(state, request)

    deposit_request = _build_deposit_request(
        spec, FRESH_PUBKEY, FRESH_PRIVKEY, withdrawal_credentials
    )
    pre_deposits_len = len(state.pending_deposits)
    spec.process_deposit_request(state, deposit_request)

    assert len(state.validator_preregistrations) == 0
    assert len(state.pending_deposits) == pre_deposits_len + 1


@with_eip8205_and_later
@spec_state_test
def test_deposit_request_mismatched_credentials_discarded(spec, state):
    withdrawal_credentials = preregistration_withdrawal_credentials(spec)
    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, withdrawal_credentials
    )
    spec.process_preregistration_request(state, request)
    pre_binding = state.validator_preregistrations[0].copy()

    deposit_request = _build_deposit_request(
        spec, FRESH_PUBKEY, FRESH_PRIVKEY, preregistration_withdrawal_credentials(spec, b"\x77")
    )
    pre_deposits_len = len(state.pending_deposits)
    spec.process_deposit_request(state, deposit_request)

    # The deposit is discarded and the binding remains active and unchanged
    assert len(state.pending_deposits) == pre_deposits_len
    assert len(state.validator_preregistrations) == 1
    assert state.validator_preregistrations[0] == pre_binding


@with_eip8205_and_later
@spec_state_test
@always_bls
def test_deposit_request_invalid_signature_discarded(spec, state):
    withdrawal_credentials = preregistration_withdrawal_credentials(spec)
    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, withdrawal_credentials
    )
    spec.process_preregistration_request(state, request)
    pre_binding = state.validator_preregistrations[0].copy()

    deposit_request = _build_deposit_request(
        spec, FRESH_PUBKEY, FRESH_PRIVKEY, withdrawal_credentials, valid_signature=False
    )
    pre_deposits_len = len(state.pending_deposits)
    spec.process_deposit_request(state, deposit_request)

    # The deposit is discarded and the binding remains active and unchanged
    assert len(state.pending_deposits) == pre_deposits_len
    assert len(state.validator_preregistrations) == 1
    assert state.validator_preregistrations[0] == pre_binding


@with_eip8205_and_later
@spec_state_test
def test_deposit_request_ignores_expired_binding(spec, state):
    withdrawal_credentials = preregistration_withdrawal_credentials(spec)
    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, withdrawal_credentials
    )
    spec.process_preregistration_request(state, request)
    _expire_logically(spec, state, state.validator_preregistrations[0].expiry_slot)

    # An expired binding is not enforced: a mismatched deposit passes through
    # unconditionally and does not consume the record
    deposit_request = _build_deposit_request(
        spec, FRESH_PUBKEY, FRESH_PRIVKEY, preregistration_withdrawal_credentials(spec, b"\x77")
    )
    pre_deposits_len = len(state.pending_deposits)
    spec.process_deposit_request(state, deposit_request)

    assert len(state.pending_deposits) == pre_deposits_len + 1
    assert len(state.validator_preregistrations) == 1


@with_eip8205_and_later
@spec_state_test
def test_deposit_request_without_binding_appended(spec, state):
    # Without a binding, even a deposit with an invalid signature is appended
    # to the pending deposits queue, preserving the inherited behavior
    deposit_request = _build_deposit_request(
        spec,
        FRESH_PUBKEY,
        FRESH_PRIVKEY,
        preregistration_withdrawal_credentials(spec),
        valid_signature=False,
    )
    pre_deposits_len = len(state.pending_deposits)
    spec.process_deposit_request(state, deposit_request)

    assert len(state.pending_deposits) == pre_deposits_len + 1


@with_eip8205_and_later
@spec_state_test
def test_deposit_request_second_deposit_after_binding_consumed(spec, state):
    withdrawal_credentials = preregistration_withdrawal_credentials(spec)
    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, withdrawal_credentials
    )
    spec.process_preregistration_request(state, request)

    # The first matching deposit consumes the binding
    deposit_request = _build_deposit_request(
        spec, FRESH_PUBKEY, FRESH_PRIVKEY, withdrawal_credentials
    )
    pre_deposits_len = len(state.pending_deposits)
    spec.process_deposit_request(state, deposit_request)
    assert len(state.validator_preregistrations) == 0

    # A second deposit with different credentials is appended unconditionally,
    # since no binding is active anymore
    second_deposit_request = _build_deposit_request(
        spec, FRESH_PUBKEY, FRESH_PRIVKEY, preregistration_withdrawal_credentials(spec, b"\x77")
    )
    spec.process_deposit_request(state, second_deposit_request)

    assert len(state.pending_deposits) == pre_deposits_len + 2


@with_eip8205_and_later
@spec_state_test
def test_deposit_request_removes_binding_from_middle_and_final_index(spec, state):
    pubkey_a, pubkey_b, pubkey_c = pubkeys[-1], pubkeys[-2], pubkeys[-3]
    privkey_b, privkey_c = privkeys[-2], privkeys[-3]
    withdrawal_credentials = preregistration_withdrawal_credentials(spec)
    for pubkey, privkey in [
        (pubkey_a, privkeys[-1]),
        (pubkey_b, privkey_b),
        (pubkey_c, privkey_c),
    ]:
        request = build_preregistration_request(
            spec, state, pubkey, privkey, withdrawal_credentials
        )
        spec.process_preregistration_request(state, request)
    assert len(state.validator_preregistrations) == 3

    # Consume the middle binding; the remaining order is preserved
    deposit_request = _build_deposit_request(spec, pubkey_b, privkey_b, withdrawal_credentials)
    spec.process_deposit_request(state, deposit_request)
    assert [p.pubkey for p in state.validator_preregistrations] == [pubkey_a, pubkey_c]

    # Consume the final binding
    deposit_request = _build_deposit_request(spec, pubkey_c, privkey_c, withdrawal_credentials)
    spec.process_deposit_request(state, deposit_request)
    assert [p.pubkey for p in state.validator_preregistrations] == [pubkey_a]


#
# process_preregistration_expiry
#


@with_eip8205_and_later
@spec_state_test
def test_preregistration_expiry(spec, state):
    state.validator_preregistrations.append(
        _stored_preregistration(
            spec,
            FRESH_PUBKEY,
            expiry_slot=spec.PREREGISTRATION_EXPIRY_SLOTS,
        )
    )
    state.validator_preregistrations.append(
        _stored_preregistration(
            spec,
            pubkeys[-2],
            expiry_slot=spec.PREREGISTRATION_EXPIRY_SLOTS + 1,
        )
    )

    # The outstanding parent payload was created exactly at the expiry
    # boundary of the first record
    _expire_logically(spec, state, spec.PREREGISTRATION_EXPIRY_SLOTS)

    spec.process_preregistration_expiry(state)

    assert len(state.validator_preregistrations) == 1
    assert state.validator_preregistrations[0].pubkey == pubkeys[-2]


@with_eip8205_and_later
@spec_state_test
def test_preregistration_expiry_multiple_expired(spec, state):
    for pubkey in [pubkeys[-1], pubkeys[-2], pubkeys[-3]]:
        state.validator_preregistrations.append(
            _stored_preregistration(
                spec,
                pubkey,
                expiry_slot=spec.PREREGISTRATION_EXPIRY_SLOTS,
            )
        )
    state.validator_preregistrations.append(
        _stored_preregistration(
            spec,
            pubkeys[-4],
            expiry_slot=spec.PREREGISTRATION_EXPIRY_SLOTS + 1,
        )
    )

    _expire_logically(spec, state, spec.PREREGISTRATION_EXPIRY_SLOTS)
    spec.process_preregistration_expiry(state)

    assert len(state.validator_preregistrations) == 1
    assert state.validator_preregistrations[0].pubkey == pubkeys[-4]


@with_eip8205_and_later
@spec_state_test
def test_preregistration_expiry_independent_of_finality(spec, state):
    # Expiry is keyed to the outstanding parent bid and continues to operate
    # without any finality progress
    state.validator_preregistrations.append(_stored_preregistration(spec, FRESH_PUBKEY))
    assert state.finalized_checkpoint.epoch == 0
    _expire_logically(spec, state, spec.PREREGISTRATION_EXPIRY_SLOTS)

    spec.process_preregistration_expiry(state)

    assert len(state.validator_preregistrations) == 0


@with_eip8205_and_later
@spec_state_test
def test_preregistration_replay_after_expiry(spec, state):
    withdrawal_credentials = preregistration_withdrawal_credentials(spec)
    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, withdrawal_credentials
    )
    spec.process_preregistration_request(state, request)
    assert len(state.validator_preregistrations) == 1

    # Make the binding expire logically; no sweep is needed for replay
    _expire_logically(spec, state, state.validator_preregistrations[0].expiry_slot)

    # The same signed request establishes a fresh binding in place
    spec.process_preregistration_request(state, request)
    assert len(state.validator_preregistrations) == 1
    assert state.validator_preregistrations[0].expiry_slot == (
        state.slot + spec.PREREGISTRATION_EXPIRY_SLOTS
    )
