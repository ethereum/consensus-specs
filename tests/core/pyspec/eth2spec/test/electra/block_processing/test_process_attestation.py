from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.context import (
    always_bls,
    spec_state_test,
    with_electra_and_later,
    with_presets,
)
from eth2spec.test.helpers.attestations import (
    run_attestation_processing,
    get_valid_attestation,
    sign_attestation,
    build_attestation_data,
    get_valid_attestation_at_slot,
    get_empty_eip7549_aggregation_bits,
)
from eth2spec.test.helpers.state import (
    next_slots,
)


@with_electra_and_later
@spec_state_test
def test_invalid_attestation_data_index_not_zero(spec, state):
    """
    EIP-7549 test
    """
    committee_index = 1
    attestation = get_valid_attestation(spec, state, index=committee_index)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    # flip the attestations index to make it non-zero and invalid
    assert committee_index == spec.get_committee_indices(attestation.committee_bits)[0]
    attestation.data.index = committee_index

    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_electra_and_later
@spec_state_test
@always_bls
def test_invalid_committee_index(spec, state):
    """
    EIP-7549 test
    """
    committee_index = 0
    attestation = get_valid_attestation(spec, state, index=committee_index, signed=True)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    # flip the bits of the attestation to make it invalid
    assert attestation.committee_bits[committee_index] == 1
    attestation.committee_bits[committee_index] = 0
    attestation.committee_bits[committee_index + 1] = 1

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_electra_and_later
@spec_state_test
def test_invalid_too_many_committee_bits(spec, state):
    """
    EIP-7549 test
    """
    committee_index = 0
    attestation = get_valid_attestation(spec, state, index=committee_index, signed=True)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    attestation.committee_bits[committee_index + 1] = 1

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_electra_and_later
@spec_state_test
def test_invalid_nonset_committee_bits(spec, state):
    """
    EIP-7549 test
    """
    committee_index = 0
    attestation = get_valid_attestation(spec, state, index=committee_index, signed=True)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    attestation.committee_bits[committee_index] = 0

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_electra_and_later
@spec_state_test
@with_presets([MINIMAL], "need multiple committees per slot")
def test_invalid_nonset_multiple_committee_bits(spec, state):
    """
    EIP-7549 test
    """
    attestation_data = build_attestation_data(spec, state, slot=state.slot, index=0)
    attestation = spec.Attestation(data=attestation_data)

    # a single attestation with all committees of a slot, but with unset aggregation_bits
    committees_per_slot = spec.get_committee_count_per_slot(state, spec.get_current_epoch(state))
    for index in range(committees_per_slot):
        attestation.committee_bits[index] = True

    attestation.aggregation_bits = get_empty_eip7549_aggregation_bits(
        spec, state, attestation.committee_bits, attestation.data.slot
    )

    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_electra_and_later
@spec_state_test
@with_presets([MINIMAL], "need multiple committees per slot")
@always_bls
def test_multiple_committees(spec, state):
    """
    EIP-7549 test
    """
    attestation_data = build_attestation_data(spec, state, slot=state.slot, index=0)
    attestation = spec.Attestation(data=attestation_data)

    # a single attestation with all committees of a slot
    attestation = get_valid_attestation_at_slot(state, spec, state.slot)

    # check that all committees are presented in a single attestation
    attesting_indices = set()
    committees_per_slot = spec.get_committee_count_per_slot(state, spec.get_current_epoch(state))
    for index in range(committees_per_slot):
        attesting_indices.update(spec.get_beacon_committee(state, state.slot, index))
    assert spec.get_attesting_indices(state, attestation) == attesting_indices

    # advance a slot
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    yield from run_attestation_processing(spec, state, attestation)


@with_electra_and_later
@spec_state_test
@with_presets([MINIMAL], "need multiple committees per slot")
@always_bls
def test_one_committee_with_gap(spec, state):
    """
    EIP-7549 test
    """
    attestation = get_valid_attestation(spec, state, index=1, signed=True)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    yield from run_attestation_processing(spec, state, attestation)


@with_electra_and_later
@spec_state_test
@with_presets([MINIMAL], "need multiple committees per slot")
def test_invalid_nonset_bits_for_one_committee(spec, state):
    """
    EIP-7549 test
    """
    # Attestation with full committee participating
    committee_0 = spec.get_beacon_committee(state, state.slot, 0)
    attestation_1 = get_valid_attestation(spec, state, index=1, signed=True)

    # Create an on chain aggregate
    aggregate = spec.Attestation(data=attestation_1.data, signature=attestation_1.signature)
    aggregate.committee_bits[0] = True
    aggregate.committee_bits[1] = True
    aggregate.aggregation_bits = get_empty_eip7549_aggregation_bits(
        spec, state, aggregate.committee_bits, aggregate.data.slot
    )
    committee_offset = len(committee_0)
    for i in range(len(attestation_1.aggregation_bits)):
        aggregate.aggregation_bits[committee_offset + i] = attestation_1.aggregation_bits[i]

    # Check that only one committee is presented
    assert spec.get_attesting_indices(state, aggregate) == spec.get_attesting_indices(
        state, attestation_1
    )

    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    yield from run_attestation_processing(spec, state, aggregate, valid=False)
