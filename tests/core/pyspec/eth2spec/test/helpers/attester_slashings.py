from eth2spec.test.helpers.attestations import (
    get_valid_attestation,
    sign_attestation,
    sign_indexed_attestation,
)
from eth2spec.test.helpers.forks import is_post_electra, is_post_gloas


def get_valid_attester_slashing(
    spec, state, slot=None, signed_1=False, signed_2=False, filter_participant_set=None
):
    attestation_1 = get_valid_attestation(
        spec, state, slot=slot, signed=signed_1, filter_participant_set=filter_participant_set
    )

    attestation_2 = attestation_1.copy()
    attestation_2.data.target.root = b"\x01" * 32

    if signed_2:
        sign_attestation(spec, state, attestation_2)

    return spec.AttesterSlashing(
        attestation_1=spec.get_indexed_attestation(state, attestation_1),
        attestation_2=spec.get_indexed_attestation(state, attestation_2),
    )


def get_valid_attester_slashing_by_indices(
    spec, state, indices_1, indices_2=None, slot=None, signed_1=False, signed_2=False
):
    if indices_2 is None:
        indices_2 = indices_1

    assert indices_1 == sorted(indices_1)
    assert indices_2 == sorted(indices_2)

    attester_slashing = get_valid_attester_slashing(spec, state, slot=slot)

    attester_slashing.attestation_1.attesting_indices = indices_1
    attester_slashing.attestation_2.attesting_indices = indices_2

    if signed_1:
        sign_indexed_attestation(spec, state, attester_slashing.attestation_1)
    if signed_2:
        sign_indexed_attestation(spec, state, attester_slashing.attestation_2)

    return attester_slashing


def get_indexed_attestation_participants(spec, indexed_att):
    """
    Wrapper around index-attestation to return the list of participant indices, regardless of spec phase.
    """
    return list(indexed_att.attesting_indices)


def set_indexed_attestation_participants(spec, indexed_att, participants):
    """
    Wrapper around index-attestation to return the list of participant indices, regardless of spec phase.
    """
    indexed_att.attesting_indices = participants


def get_attestation_1_data(spec, att_slashing):
    return att_slashing.attestation_1.data


def get_attestation_2_data(spec, att_slashing):
    return att_slashing.attestation_2.data


def get_max_attester_slashings(spec):
    if is_post_electra(spec):
        return spec.MAX_ATTESTER_SLASHINGS_ELECTRA
    else:
        return spec.MAX_ATTESTER_SLASHINGS


def needs_upgrade_to_gloas(spec, new_spec):
    return is_post_gloas(new_spec) and not is_post_gloas(spec)


def check_indexed_attestation_equal(spec, new_spec, data, upgraded):
    assert list(data.attesting_indices) == list(upgraded.attesting_indices)
    assert data.data == upgraded.data
    assert data.signature == upgraded.signature


def upgrade_indexed_attestation_to_new_spec(spec, new_spec, data):
    upgraded = data

    if needs_upgrade_to_gloas(spec, new_spec):
        upgraded = new_spec.upgrade_indexed_attestation_to_gloas(upgraded)
        check_indexed_attestation_equal(spec, new_spec, data, upgraded)

    return upgraded


def check_attester_slashing_equal(spec, new_spec, data, upgraded):
    check_indexed_attestation_equal(spec, new_spec, data.attestation_1, upgraded.attestation_1)
    check_indexed_attestation_equal(spec, new_spec, data.attestation_2, upgraded.attestation_2)


def upgrade_attester_slashing_to_new_spec(spec, new_spec, data):
    upgraded = data

    if needs_upgrade_to_gloas(spec, new_spec):
        upgraded = new_spec.upgrade_attester_slashing_to_gloas(upgraded)
        check_attester_slashing_equal(spec, new_spec, data, upgraded)

    return upgraded
