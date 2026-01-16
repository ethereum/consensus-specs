from eth_consensus_specs.test.context import (
    always_bls,
    default_activation_threshold,
    expect_assertion_error,
    large_validator_set,
    single_phase,
    spec_state_test,
    spec_test,
    with_custom_state,
    with_gloas_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import MINIMAL
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.state import next_epoch
from eth_consensus_specs.utils.ssz.ssz_typing import Bitvector


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


def prepare_signed_payload_attestation(
    spec,
    state,
    slot=None,
    beacon_block_root=None,
    payload_timely=True,
    attesting_indices=None,
    valid_signature=True,
    domain_epoch=None,
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

    if domain_epoch is None:
        domain_epoch = spec.compute_epoch_at_slot(slot)

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
        payload_timely=payload_timely,
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
            data, spec.get_domain(state, spec.DOMAIN_PTC_ATTESTER, domain_epoch)
        )

        signatures = []
        for validator_index in attesting_indices:
            if validator_index < len(privkeys):
                signature = spec.bls.Sign(privkeys[validator_index], signing_root)
                signatures.append(signature)

        if signatures:
            payload_attestation.signature = spec.bls.Aggregate(signatures)

    return payload_attestation


def _get_ptc_from_indices(spec, state, slot, indices):
    slot = spec.Slot(slot)
    epoch = spec.compute_epoch_at_slot(slot)
    seed = spec.hash(
        spec.get_seed(state, epoch, spec.DOMAIN_PTC_ATTESTER) + spec.uint_to_bytes(slot)
    )
    return spec.compute_balance_weighted_selection(
        state, indices, seed, size=spec.PTC_SIZE, shuffle_indices=False
    )


def _compute_selection_with_acceptance_iterations(spec, state, indices, seed, size):
    selected = []
    accepted_at = []
    total = len(indices)
    i = 0
    while len(selected) < size:
        candidate_index = indices[i % total]
        if spec.compute_balance_weighted_acceptance(state, candidate_index, seed, spec.uint64(i)):
            selected.append(candidate_index)
            accepted_at.append(i)
        i += 1
    return selected, accepted_at


#
# Valid payload attestation tests
#


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_payload_attestation_payload_timely(spec, state):
    """
    Test basic valid payload attestation processing
    """
    spec.process_slots(state, state.slot + 1)

    payload_attestation = prepare_signed_payload_attestation(spec, state, payload_timely=True)

    yield from run_payload_attestation_processing(spec, state, payload_attestation)


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_payload_attestation_payload_not_present(spec, state):
    """
    Test valid payload attestation indicating payload was not present
    """
    spec.process_slots(state, state.slot + 1)

    payload_attestation = prepare_signed_payload_attestation(spec, state, payload_timely=False)

    yield from run_payload_attestation_processing(spec, state, payload_attestation)


@with_gloas_and_later
@spec_state_test
@always_bls
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
def test_process_payload_attestation_no_attesting_indices(spec, state):
    """
    Test payload attestation with no attesting indices fails
    """
    # Advance state to slot 1 so we can attest to slot 0
    spec.process_slots(state, state.slot + 1)

    payload_attestation = prepare_signed_payload_attestation(spec, state, attesting_indices=[])

    yield from run_payload_attestation_processing(spec, state, payload_attestation, valid=False)


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_payload_attestation_cross_epoch_wrong_domain(spec, state):
    """
    Test that payload attestation signed with wrong epoch domain fails.

    The signature uses the wrong epoch's domain (epoch 1) instead of the
    attested slot's epoch domain (epoch 0). To ensure different domains,
    we set the fork boundary at epoch 1 so epochs 0 and 1 use different
    fork versions.
    """
    # Advance to first slot of next epoch, attest to last slot of previous epoch
    next_epoch(spec, state)

    attested_slot = state.slot - 1
    correct_epoch = spec.compute_epoch_at_slot(attested_slot)
    wrong_epoch = spec.get_current_epoch(state)
    assert wrong_epoch != correct_epoch

    # Set fork boundary at wrong_epoch so the two epochs use different fork versions.
    # - correct_epoch (0) < fork.epoch (1) -> uses previous_version
    # - wrong_epoch (1) >= fork.epoch (1) -> uses current_version
    state.fork.epoch = wrong_epoch
    # Ensure fork versions are different
    state.fork.previous_version = spec.Version("0x00000001")
    state.fork.current_version = spec.Version("0x00000002")

    payload_attestation = prepare_signed_payload_attestation(
        spec, state, slot=attested_slot, domain_epoch=wrong_epoch
    )

    yield from run_payload_attestation_processing(spec, state, payload_attestation, valid=False)


@with_gloas_and_later
@with_presets([MINIMAL], reason="mainnet preset requires a much larger validator set")
@with_custom_state(balances_fn=large_validator_set, threshold_fn=default_activation_threshold)
@spec_test
@always_bls
@single_phase
def test_process_payload_attestation_uses_multiple_committees(spec, state):
    """
    Ensure get_ptc includes all committees for the slot (not just committee 0).
    Builds a payload attestation signed by a validator that appears in the
    PTC only when committees are concatenated; an implementation that samples
    from committee 0 alone must reject.
    """
    committees_per_slot = spec.get_committee_count_per_slot(state, spec.get_current_epoch(state))
    assert committees_per_slot > 1

    chosen_slot = None
    chosen_index = None
    for slot in map(spec.Slot, range(spec.SLOTS_PER_EPOCH)):
        spec.process_slots(state, slot + 1)

        committees_per_slot = spec.get_committee_count_per_slot(
            state, spec.compute_epoch_at_slot(slot)
        )
        assert committees_per_slot > 1

        indices_all = []
        for i in range(committees_per_slot):
            indices_all.extend(spec.get_beacon_committee(state, slot, spec.CommitteeIndex(i)))

        indices_first = list(spec.get_beacon_committee(state, slot, spec.CommitteeIndex(0)))
        ptc_all = _get_ptc_from_indices(spec, state, slot, indices_all)
        ptc_first = _get_ptc_from_indices(spec, state, slot, indices_first)

        if ptc_all != ptc_first:
            diff_indices = [index for index in ptc_all if index not in ptc_first]
            if diff_indices:
                chosen_slot = slot
                chosen_index = diff_indices[0]
                break

    assert chosen_slot is not None
    assert chosen_index is not None

    payload_attestation = prepare_signed_payload_attestation(
        spec, state, slot=chosen_slot, attesting_indices=[chosen_index]
    )
    yield from run_payload_attestation_processing(spec, state, payload_attestation)


@with_gloas_and_later
@with_presets([MINIMAL], reason="mainnet preset requires a much larger validator set")
@with_custom_state(balances_fn=large_validator_set, threshold_fn=default_activation_threshold)
@spec_test
@always_bls
@single_phase
def test_process_payload_attestation_sampling_not_capped(spec, state):
    """
    Ensure get_ptc does not stop sampling after active_validator_count // 32
    iterations. Constructs a low-balance state and selects a validator whose
    acceptance occurs after that limit, then signs a payload attestation with it.
    Capped sampling would omit the validator and reject the attestation.
    """
    epoch = spec.get_current_epoch(state)
    active_validator_count = len(spec.get_active_validator_indices(state, epoch))
    limit = active_validator_count // spec.SLOTS_PER_EPOCH
    assert limit > 0

    low_balance = spec.EFFECTIVE_BALANCE_INCREMENT
    for validator in state.validators:
        validator.effective_balance = low_balance

    chosen_slot = None
    chosen_index = None
    for slot in map(spec.Slot, range(spec.SLOTS_PER_EPOCH)):
        spec.process_slots(state, slot + 1)

        epoch = spec.compute_epoch_at_slot(slot)
        committees_per_slot = spec.get_committee_count_per_slot(state, epoch)

        indices = []
        for i in range(committees_per_slot):
            indices.extend(spec.get_beacon_committee(state, slot, spec.CommitteeIndex(i)))

        seed = spec.hash(
            spec.get_seed(state, epoch, spec.DOMAIN_PTC_ATTESTER) + spec.uint_to_bytes(slot)
        )

        ptc_expected, accepted_at = _compute_selection_with_acceptance_iterations(
            spec, state, indices, seed, spec.PTC_SIZE
        )
        for index, accepted_i in zip(ptc_expected, accepted_at):
            if accepted_i > limit:
                chosen_slot = slot
                chosen_index = index
                break

        if chosen_index is not None:
            break

    assert chosen_slot is not None
    assert chosen_index is not None

    payload_attestation = prepare_signed_payload_attestation(
        spec, state, slot=chosen_slot, attesting_indices=[chosen_index]
    )
    yield from run_payload_attestation_processing(spec, state, payload_attestation)
