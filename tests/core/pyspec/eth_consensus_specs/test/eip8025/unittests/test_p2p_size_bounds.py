import pytest
from ssz.exceptions import SSZValueError

from eth_consensus_specs.test.context import (
    single_phase,
    spec_test,
    with_eip8025_and_later,
)
from eth_consensus_specs.test.helpers.p2p_size_bounds import (
    build_max_size_signed_execution_proof,
    get_max_signed_execution_proof_size,
)


@with_eip8025_and_later
@spec_test
@single_phase
def test_max_signed_execution_proof_envelope_size(spec):
    encoded = build_max_size_signed_execution_proof(spec).encode_bytes()
    assert len(encoded) == get_max_signed_execution_proof_size(spec)
    assert len(encoded) <= spec.config.MAX_PAYLOAD_SIZE


@with_eip8025_and_later
@spec_test
@single_phase
def test_signed_execution_proof_envelope_rejects_oversize_proof_data(spec):
    signed_proof = build_max_size_signed_execution_proof(spec)
    encoded = signed_proof.encode_bytes()
    oversized = encoded + b"\x00"
    assert len(oversized) == get_max_signed_execution_proof_size(spec) + 1

    with pytest.raises(SSZValueError):
        type(signed_proof).decode_bytes(oversized)
