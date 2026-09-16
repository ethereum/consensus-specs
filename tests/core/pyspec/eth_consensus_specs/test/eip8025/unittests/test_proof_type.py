from eth_consensus_specs.test.context import (
    expect_assertion_error,
    single_phase,
    spec_test,
    with_eip8025_and_later,
)

ASSIGNED_PROOF_TYPES = (1, 2, 3)
UNASSIGNED_PROOF_TYPES = (0, 4, 255)


def build_signed_execution_proof_envelope(spec, proof_type):
    return spec.SignedExecutionProofEnvelope(
        message=spec.ExecutionProofEnvelope(
            proof_data=spec.ProofData(data=[1]),
            proof_type=spec.ProofType(proof_type),
            beacon_block_root=spec.Root(),
        ),
        validator_index=spec.ValidatorIndex(0),
        signature=spec.BLSSignature(),
    )


def set_encoded_proof_type(encoded, proof_type):
    """Replace the proof type in an encoded ``SignedExecutionProofEnvelope``."""
    # The message is the only variable-size field, so its offset leads the
    # encoding, and the proof data offset leads the message.
    proof_type_index = int.from_bytes(encoded[:4], "little") + 4
    mutated = bytearray(encoded)
    mutated[proof_type_index] = proof_type
    return bytes(mutated)


@with_eip8025_and_later
@spec_test
@single_phase
def test_proof_type_admits_assigned_values(spec):
    for proof_type in ASSIGNED_PROOF_TYPES:
        assert spec.ProofType(proof_type) == proof_type


@with_eip8025_and_later
@spec_test
@single_phase
def test_proof_type_rejects_unassigned_values(spec):
    for proof_type in UNASSIGNED_PROOF_TYPES:
        expect_assertion_error(lambda proof_type=proof_type: spec.ProofType(proof_type))


@with_eip8025_and_later
@spec_test
@single_phase
def test_signed_execution_proof_envelope_admits_assigned_proof_type(spec):
    encoded = build_signed_execution_proof_envelope(spec, ASSIGNED_PROOF_TYPES[0]).encode_bytes()

    for proof_type in ASSIGNED_PROOF_TYPES:
        decoded = spec.SignedExecutionProofEnvelope.decode_bytes(
            set_encoded_proof_type(encoded, proof_type)
        )
        assert decoded.message.proof_type == spec.ProofType(proof_type)


@with_eip8025_and_later
@spec_test
@single_phase
def test_signed_execution_proof_envelope_rejects_unassigned_proof_type(spec):
    encoded = build_signed_execution_proof_envelope(spec, ASSIGNED_PROOF_TYPES[0]).encode_bytes()

    for proof_type in UNASSIGNED_PROOF_TYPES:
        mutated = set_encoded_proof_type(encoded, proof_type)
        expect_assertion_error(
            lambda mutated=mutated: spec.SignedExecutionProofEnvelope.decode_bytes(mutated)
        )
