from eth_consensus_specs.test.context import (
    single_phase,
    spec_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.p2p_size_bounds import (
    build_max_size_attester_slashing,
    build_max_size_data_column_sidecar,
    build_max_size_partial_data_column_sidecar,
    build_max_size_signed_aggregate_and_proof,
    build_max_size_signed_execution_payload_bid,
    get_max_attester_slashing_size,
    get_max_data_column_sidecar_size,
    get_max_partial_data_column_sidecar_size,
    get_max_signed_aggregate_and_proof_size,
    get_max_signed_execution_payload_bid_size,
)


@with_gloas_and_later
@spec_test
@single_phase
def test_max_signed_aggregate_and_proof_size(spec):
    encoded = build_max_size_signed_aggregate_and_proof(spec).encode_bytes()
    assert len(encoded) == get_max_signed_aggregate_and_proof_size(spec)
    assert len(encoded) <= spec.config.MAX_PAYLOAD_SIZE


@with_gloas_and_later
@spec_test
@single_phase
def test_max_attester_slashing_size(spec):
    encoded = build_max_size_attester_slashing(spec).encode_bytes()
    assert len(encoded) == get_max_attester_slashing_size(spec)
    assert len(encoded) <= spec.config.MAX_PAYLOAD_SIZE


@with_gloas_and_later
@spec_test
@single_phase
def test_max_data_column_sidecar_size(spec):
    encoded = build_max_size_data_column_sidecar(spec).encode_bytes()
    assert len(encoded) == get_max_data_column_sidecar_size(spec)
    assert len(encoded) <= spec.config.MAX_PAYLOAD_SIZE


@with_gloas_and_later
@spec_test
@single_phase
def test_max_partial_data_column_sidecar_size(spec):
    encoded = build_max_size_partial_data_column_sidecar(spec).encode_bytes()
    assert len(encoded) == get_max_partial_data_column_sidecar_size(spec)
    assert len(encoded) <= spec.config.MAX_PAYLOAD_SIZE


@with_gloas_and_later
@spec_test
@single_phase
def test_max_signed_execution_payload_bid_size(spec):
    encoded = build_max_size_signed_execution_payload_bid(spec).encode_bytes()
    assert len(encoded) == get_max_signed_execution_payload_bid_size(spec)
    assert len(encoded) <= spec.config.MAX_PAYLOAD_SIZE
