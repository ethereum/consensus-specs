from copy import deepcopy

from eth2spec.test.helpers.attestations import get_valid_attestation, sign_attestation


def get_valid_attester_slashing(spec, state, signed_1=False, signed_2=False):
    attestation_1 = get_valid_attestation(spec, state, signed=signed_1)

    attestation_2 = deepcopy(attestation_1)
    attestation_2.data.target.root = b'\x01' * 32

    if signed_2:
        sign_attestation(spec, state, attestation_2)

    return spec.AttesterSlashing(
        attestation_1=spec.get_indexed_attestation(state, attestation_1),
        attestation_2=spec.get_indexed_attestation(state, attestation_2),
    )
