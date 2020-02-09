from eth2spec.test.helpers.attestations import get_valid_attestation, sign_attestation


def get_valid_attester_slashing(spec, state, signed_1=False, signed_2=False):
    attestation_1 = get_valid_attestation(spec, state, signed=signed_1)

    attestation_2 = attestation_1.copy()
    attestation_2.data.target.root = b'\x01' * 32

    if signed_2:
        sign_attestation(spec, state, attestation_2)

    return spec.AttesterSlashing(
        attestation_1=spec.get_indexed_attestation(state, attestation_1),
        attestation_2=spec.get_indexed_attestation(state, attestation_2),
    )


def get_indexed_attestation_participants(spec, indexed_att):
    """
    Wrapper around index-attestation to return the list of participant indices, regardless of spec phase.
    """
    if spec.fork == "phase1":
        return list(spec.get_indices_from_committee(
            indexed_att.committee,
            indexed_att.attestation.aggregation_bits,
        ))
    else:
        return list(indexed_att.attesting_indices)


def set_indexed_attestation_participants(spec, indexed_att, participants):
    """
    Wrapper around index-attestation to return the list of participant indices, regardless of spec phase.
    """
    if spec.fork == "phase1":
        indexed_att.attestation.aggregation_bits = [bool(i in participants) for i in indexed_att.committee]
    else:
        indexed_att.attesting_indices = participants


def get_attestation_1_data(spec, att_slashing):
    if spec.fork == "phase1":
        return att_slashing.attestation_1.attestation.data
    else:
        return att_slashing.attestation_1.data


def get_attestation_2_data(spec, att_slashing):
    if spec.fork == "phase1":
        return att_slashing.attestation_2.attestation.data
    else:
        return att_slashing.attestation_2.data
