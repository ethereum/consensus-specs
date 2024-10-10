from eth2spec.test.context import (
    always_bls,
    spec_state_test,
    with_electra_and_later,
)
from eth2spec.test.helpers.attestations import (
    run_attestation_processing,
    get_valid_attestation,
    sign_attestation,
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
def test_invalid_committe_index(spec, state):
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
def test_invalid_too_many_committe_bits(spec, state):
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
def test_correct_attestation_with_two_attestation_committees(spec, state):
    attestation = get_valid_attestation(spec, state, signed=True, index=[0, 1])
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    yield from run_attestation_processing(spec, state, attestation)


@with_electra_and_later
@spec_state_test
def test_invalid_nonset_committe_bits(spec, state):
    """
    EIP-7549 test
    """
    committee_index = 0
    attestation = get_valid_attestation(spec, state, index=committee_index, signed=True)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    attestation.committee_bits[committee_index] = 0

    yield from run_attestation_processing(spec, state, attestation, valid=False)
