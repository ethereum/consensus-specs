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
def test_max_signed_execution_proof_size(spec):
    encoded = build_max_size_signed_execution_proof(spec).encode_bytes()
    assert len(encoded) == get_max_signed_execution_proof_size(spec)
    assert len(encoded) <= spec.config.MAX_PAYLOAD_SIZE
