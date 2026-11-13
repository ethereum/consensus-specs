from eth_consensus_specs.test.context import (
    always_bls,
    expect_assertion_error,
    spec_state_test_with_matching_config,
    with_gloas_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import MINIMAL
from eth_consensus_specs.test.helpers.keys import privkeys


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
        expect_assertion_error(lambda: spec.process_payload_attestation(state, payload_attestation))
        return

    spec.process_payload_attestation(state, payload_attestation)
    yield "post", state


@with_gloas_and_later
@spec_state_test_with_matching_config
@with_presets([MINIMAL], reason="minimal preset for fast repro")
@always_bls
def test_c3_a_duplicate_ptc_validator_both_bits_rejected(spec, state):
    """
    C3-A: Pin a PTC with one duplicate (validator 0 at positions 0 and 1),
    aggregate literally per original validator.md (bits at both positions, signature once)
    -> is_valid_indexed_payload_attestation returns False, block rejected.
    """
    spec.process_slots(state, state.slot + 1)
    slot = state.slot - 1

    # Pin PTC with duplicate: validator 0 at positions 0 and 1
    epoch = spec.compute_epoch_at_slot(slot)
    state_epoch = spec.get_current_epoch(state)
    offset = spec.Uint64(epoch - state_epoch + 1) * spec.SLOTS_PER_EPOCH
    ptc_window_index = offset + slot % spec.SLOTS_PER_EPOCH

    ptc_members = list(state.ptc_window[ptc_window_index])
    ptc_members[0] = spec.ValidatorIndex(0)
    ptc_members[1] = spec.ValidatorIndex(0)
    state.ptc_window[ptc_window_index] = spec.PayloadTimelinessCommittee(data=ptc_members)

    # Set bits at both positions where validator 0 appears
    aggregation_bits = spec.PayloadTimelinessCommitteeBits()
    aggregation_bits[0] = True
    aggregation_bits[1] = True

    data = spec.PayloadAttestationData(
        beacon_block_root=state.latest_block_header.parent_root,
        slot=slot,
        payload_present=True,
        blob_data_available=False,
    )

    domain = spec.get_domain(state, spec.DOMAIN_PTC_ATTESTER, spec.compute_epoch_at_slot(slot))
    signing_root = spec.compute_signing_root(data, domain)

    # Single signature from validator 0 (received over gossip)
    signature = spec.bls.Sign(privkeys[0], signing_root)

    payload_attestation = spec.PayloadAttestation(
        aggregation_bits=aggregation_bits,
        data=data,
        signature=signature,
    )

    indexed = spec.get_indexed_payload_attestation(state, payload_attestation)
    assert not spec.is_valid_indexed_payload_attestation(state, indexed)

    yield from run_payload_attestation_processing(spec, state, payload_attestation, valid=False)


@with_gloas_and_later
@spec_state_test_with_matching_config
@with_presets([MINIMAL], reason="minimal preset for fast repro")
@always_bls
def test_c3_b_duplicate_ptc_validator_one_bit_accepted(spec, state):
    """
    C3-B: Pin a PTC with one duplicate (validator 0 at positions 0 and 1),
    aggregate with one bit per distinct validator -> accepted.
    """
    spec.process_slots(state, state.slot + 1)
    slot = state.slot - 1

    # Pin PTC with duplicate: validator 0 at positions 0 and 1
    epoch = spec.compute_epoch_at_slot(slot)
    state_epoch = spec.get_current_epoch(state)
    offset = spec.Uint64(epoch - state_epoch + 1) * spec.SLOTS_PER_EPOCH
    ptc_window_index = offset + slot % spec.SLOTS_PER_EPOCH

    ptc_members = list(state.ptc_window[ptc_window_index])
    ptc_members[0] = spec.ValidatorIndex(0)
    ptc_members[1] = spec.ValidatorIndex(0)
    state.ptc_window[ptc_window_index] = spec.PayloadTimelinessCommittee(data=ptc_members)

    # Set at most one bit per distinct validator
    aggregation_bits = spec.PayloadTimelinessCommitteeBits()
    aggregation_bits[0] = True

    data = spec.PayloadAttestationData(
        beacon_block_root=state.latest_block_header.parent_root,
        slot=slot,
        payload_present=True,
        blob_data_available=False,
    )

    domain = spec.get_domain(state, spec.DOMAIN_PTC_ATTESTER, spec.compute_epoch_at_slot(slot))
    signing_root = spec.compute_signing_root(data, domain)

    # Single signature from validator 0
    signature = spec.bls.Sign(privkeys[0], signing_root)

    payload_attestation = spec.PayloadAttestation(
        aggregation_bits=aggregation_bits,
        data=data,
        signature=signature,
    )

    indexed = spec.get_indexed_payload_attestation(state, payload_attestation)
    assert spec.is_valid_indexed_payload_attestation(state, indexed)

    yield from run_payload_attestation_processing(spec, state, payload_attestation, valid=True)
