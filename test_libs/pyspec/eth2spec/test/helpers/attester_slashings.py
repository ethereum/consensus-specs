from copy import deepcopy

from eth2spec.phase0.spec import AttesterSlashing, convert_to_indexed
from eth2spec.test.helpers.attestations import get_valid_attestation, make_attestation_signature


def get_valid_attester_slashing(state):
    attestation_1 = get_valid_attestation(state)
    attestation_2 = deepcopy(attestation_1)
    attestation_2.data.target_root = b'\x01' * 32

    make_attestation_signature(state, attestation_2)

    return AttesterSlashing(
        attestation_1=convert_to_indexed(state, attestation_1),
        attestation_2=convert_to_indexed(state, attestation_2),
    )
