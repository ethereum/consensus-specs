from eth2spec.test.context import (
    always_bls,
    spec_state_test,
    with_gloas_and_later,
    with_presets,
)
from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.helpers.keys import privkeys
from eth2spec.utils.ssz.ssz_typing import Bitvector


def run_payload_attestation_processing(spec, state, payload_attestation, valid=True):
    """
    Run ``process_payload_attestation``, yielding:
    - pre-state ('pre')
    - payload_attestation ('payload_attestation')
    - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    yield "pre", state
    yield "payload_attestation", payload_attestation

    if not valid:
        try:
            spec.process_payload_attestation(state, payload_attestation)
            assert False, "Expected AssertionError"
        except AssertionError:
            pass
        return

    spec.process_payload_attestation(state, payload_attestation)
    yield "post", state


def prepare_signed_payload_attestation(
    spec,
    state,
    slot=None,
    beacon_block_root=None,
    payload_present=True,
    attesting_indices=None,
    valid_signature=True,
):
    """
    Helper to create a signed payload attestation with customizable parameters.
    """
    if slot is None:
        if state.slot == 0:
            raise ValueError("Cannot attest to previous slot when state.slot is 0")
        slot = state.slot - 1  # Attest to previous slot

    if beacon_block_root is None:
        beacon_block_root = state.latest_block_header.parent_root

    # Get the PTC for the attested slot
    ptc = spec.get_ptc(state, slot)

    if attesting_indices is None:
        # Default to all PTC members attesting
        attesting_indices = ptc

    # Indices whose corresponding aggregation bits are unset,
    # to deal with duplicates indices in the PTC.
    unset_indices = list(attesting_indices)

    aggregation_bits = Bitvector[spec.PTC_SIZE]()
    for i, validator_index in enumerate(ptc):
        if validator_index in unset_indices:
            aggregation_bits[i] = True
            unset_indices.remove(validator_index)

    # Create payload attestation data
    data = spec.PayloadAttestationData(
        beacon_block_root=beacon_block_root,
        slot=slot,
        payload_present=payload_present,
    )

    # Create payload attestation
    payload_attestation = spec.PayloadAttestation(
        aggregation_bits=aggregation_bits,
        data=data,
        signature=spec.BLSSignature(),
    )

    if valid_signature and attesting_indices:
        # Sign the attestation
        signing_root = spec.compute_signing_root(
            data, spec.get_domain(state, spec.DOMAIN_PTC_ATTESTER, spec.compute_epoch_at_slot(slot))
        )

        signatures = []
        for validator_index in attesting_indices:
            if validator_index < len(privkeys):
                signature = spec.bls.Sign(privkeys[validator_index], signing_root)
                signatures.append(signature)

        if signatures:
            payload_attestation.signature = spec.bls.Aggregate(signatures)

    return payload_attestation


#
# Valid payload attestation tests
#


@with_gloas_and_later
@spec_state_test
@always_bls
@with_presets([MINIMAL], reason="broken on mainnet")
def test_process_payload_attestation_payload_present(spec, state):
    """
    Test basic valid payload attestation processing
    """
    spec.process_slots(state, state.slot + 1)

    payload_attestation = prepare_signed_payload_attestation(spec, state, payload_present=True)

    yield from run_payload_attestation_processing(spec, state, payload_attestation)


@with_gloas_and_later
@spec_state_test
@always_bls
@with_presets([MINIMAL], reason="broken on mainnet")
def test_process_payload_attestation_payload_not_present(spec, state):
    """
    Test valid payload attestation indicating payload was not present
    """
    spec.process_slots(state, state.slot + 1)

    payload_attestation = prepare_signed_payload_attestation(spec, state, payload_present=False)

    yield from run_payload_attestation_processing(spec, state, payload_attestation)


@with_gloas_and_later
@spec_state_test
@always_bls
@with_presets([MINIMAL], reason="broken on mainnet")
def test_process_payload_attestation_partial_participation(spec, state):
    """
    Test valid payload attestation with only some PTC members participating
    """
    spec.process_slots(state, state.slot + 1)

    ptc = spec.get_ptc(state, state.slot - 1)
    # Only half of the PTC members attest
    attesting_indices = ptc[: len(ptc) // 2] if ptc else []

    payload_attestation = prepare_signed_payload_attestation(
        spec, state, attesting_indices=attesting_indices
    )

    yield from run_payload_attestation_processing(spec, state, payload_attestation)


#
# Invalid beacon block root tests
#


@with_gloas_and_later
@spec_state_test
@with_presets([MINIMAL], reason="maybe broken on mainnet")
def test_process_payload_attestation_invalid_beacon_block_root(spec, state):
    """
    Test payload attestation with wrong beacon block root fails
    """
    spec.process_slots(state, state.slot + 1)

    wrong_root = spec.Root(b"\x42" * 32)
    payload_attestation = prepare_signed_payload_attestation(
        spec, state, beacon_block_root=wrong_root
    )

    yield from run_payload_attestation_processing(spec, state, payload_attestation, valid=False)


#
# Invalid slot timing tests
#


@with_gloas_and_later
@spec_state_test
@with_presets([MINIMAL], reason="maybe broken on mainnet")
def test_process_payload_attestation_future_slot(spec, state):
    """
    Test payload attestation for future slot fails
    """
    spec.process_slots(state, state.slot + 1)

    # Try to attest to current slot (should be previous slot)
    payload_attestation = prepare_signed_payload_attestation(spec, state, slot=state.slot)

    yield from run_payload_attestation_processing(spec, state, payload_attestation, valid=False)


@with_gloas_and_later
@spec_state_test
@with_presets([MINIMAL], reason="maybe broken on mainnet")
def test_process_payload_attestation_too_old_slot(spec, state):
    """
    Test payload attestation for slot too far in the past fails
    """
    # Advance state to slot 3
    spec.process_slots(state, state.slot + 3)

    # Try to attest to slot 0 (2 slots ago, should be 1 slot ago)
    payload_attestation = prepare_signed_payload_attestation(spec, state, slot=state.slot - 2)

    yield from run_payload_attestation_processing(spec, state, payload_attestation, valid=False)


@with_gloas_and_later
@spec_state_test
@with_presets([MINIMAL], reason="maybe broken on mainnet")
def test_process_payload_attestation_invalid_signature(spec, state):
    """
    Test payload attestation with invalid signature fails
    """
    # Advance state to slot 1 so we can attest to slot 0
    spec.process_slots(state, state.slot + 1)

    payload_attestation = prepare_signed_payload_attestation(spec, state, valid_signature=False)

    yield from run_payload_attestation_processing(spec, state, payload_attestation, valid=False)


@with_gloas_and_later
@spec_state_test
@with_presets([MINIMAL], reason="maybe broken on mainnet")
def test_process_payload_attestation_no_attesting_indices(spec, state):
    """
    Test payload attestation with no attesting indices fails
    """
    # Advance state to slot 1 so we can attest to slot 0
    spec.process_slots(state, state.slot + 1)

    payload_attestation = prepare_signed_payload_attestation(spec, state, attesting_indices=[])

    yield from run_payload_attestation_processing(spec, state, payload_attestation, valid=False)
