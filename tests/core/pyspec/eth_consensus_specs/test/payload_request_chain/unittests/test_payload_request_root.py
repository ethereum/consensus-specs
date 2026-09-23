from hashlib import sha256

from eth_consensus_specs.test.context import (
    single_phase,
    spec_test,
    with_payload_request_chain_and_later,
)


def build_payload_commitment(spec):
    return spec.ExecutionPayloadCommitment(
        parent_hash=spec.Hash32(b"\xaa" * 32),
        prev_randao=spec.Bytes32(b"\xbb" * 32),
        gas_limit=spec.Uint64(30000000),
        timestamp=spec.Uint64(1700000000),
        block_hash=spec.Hash32(b"\x66" * 32),
        withdrawals=spec.Withdrawals(
            data=[
                spec.Withdrawal(
                    index=spec.WithdrawalIndex(3),
                    validator_index=spec.ValidatorIndex(9),
                    address=spec.ExecutionAddress(b"\x99" * 20),
                    amount=spec.Gwei(1234),
                )
            ]
        ),
        slot_number=spec.Uint64(42),
    )


def build_request_commitment(spec, payload_commitment):
    return spec.NewPayloadRequestCommitment(
        execution_payload=payload_commitment,
        versioned_hashes=spec.VersionedHashes(data=[spec.VersionedHash(b"\x01" + b"\xcc" * 31)]),
        parent_beacon_block_root=spec.Root(b"\xdd" * 32),
        requests_hash=spec.compute_requests_hash(
            spec.get_execution_requests_list(spec.ExecutionRequests())
        ),
    )


@with_payload_request_chain_and_later
@spec_test
@single_phase
def test_commitment_binds_every_field(spec):
    """Mutating any commitment field must change the payload request root."""
    base = build_request_commitment(spec, build_payload_commitment(spec))
    base_root = spec.hash_tree_root(base)

    mutations = {
        "parent_hash": spec.Hash32(b"\x01" * 32),
        "prev_randao": spec.Bytes32(b"\x02" * 32),
        "gas_limit": spec.Uint64(29999999),
        "timestamp": spec.Uint64(1700000001),
        "block_hash": spec.Hash32(b"\x03" * 32),
        "slot_number": spec.Uint64(43),
    }
    for field, value in mutations.items():
        mutated_payload = base.execution_payload.copy()
        setattr(mutated_payload, field, value)
        mutated = base.copy()
        mutated.execution_payload = mutated_payload
        assert spec.hash_tree_root(mutated) != base_root, field

    mutated = base.copy()
    mutated.parent_beacon_block_root = spec.Root(b"\x04" * 32)
    assert spec.hash_tree_root(mutated) != base_root

    mutated = base.copy()
    mutated.requests_hash = spec.Hash32(b"\x05" * 32)
    assert spec.hash_tree_root(mutated) != base_root

    mutated = base.copy()
    mutated.versioned_hashes = spec.VersionedHashes(
        data=[spec.VersionedHash(b"\x01" + b"\xee" * 31)]
    )
    assert spec.hash_tree_root(mutated) != base_root


@with_payload_request_chain_and_later
@spec_test
@single_phase
def test_block_hash_binds_the_remaining_payload_fields(spec):
    """
    Fields absent from the commitment are reached through ``block_hash``: an
    execution payload that differs in any RLP-covered field has a different
    block hash, which the commitment does bind.
    """
    commitment = build_payload_commitment(spec)
    tampered = commitment.copy()
    tampered.block_hash = spec.Hash32(b"\x77" * 32)

    assert spec.hash_tree_root(tampered) != spec.hash_tree_root(commitment)


@with_payload_request_chain_and_later
@spec_test
@single_phase
def test_nesting_keeps_groups_separable(spec):
    """The payload-derived group is reachable as a single subtree root."""
    payload_commitment = build_payload_commitment(spec)
    request = build_request_commitment(spec, payload_commitment)

    assert spec.hash_tree_root(request.execution_payload) == spec.hash_tree_root(payload_commitment)


@with_payload_request_chain_and_later
@spec_test
@single_phase
def test_payload_request_chain_root_is_order_dependent(spec):
    """Chaining must bind position, not just membership."""
    root_a = spec.Root(b"\x01" * 32)
    root_b = spec.Root(b"\x02" * 32)
    genesis = spec.PAYLOAD_REQUEST_CHAIN_ROOT_GENESIS

    forward = spec.compute_payload_request_chain_root(
        spec.compute_payload_request_chain_root(genesis, root_a), root_b
    )
    reverse = spec.compute_payload_request_chain_root(
        spec.compute_payload_request_chain_root(genesis, root_b), root_a
    )

    assert forward != reverse


@with_payload_request_chain_and_later
@spec_test
@single_phase
def test_payload_request_chain_root_extends(spec):
    """Each extension must move the chain root."""
    genesis = spec.PAYLOAD_REQUEST_CHAIN_ROOT_GENESIS
    root = spec.Root(b"\x01" * 32)

    first = spec.compute_payload_request_chain_root(genesis, root)
    second = spec.compute_payload_request_chain_root(first, root)

    assert first != genesis
    assert second != first


@with_payload_request_chain_and_later
@spec_test
@single_phase
def test_requests_hash_matches_eip7685(spec):
    """The CL re-derivation must equal the execution header's commitment."""
    requests = spec.ExecutionRequests()
    encoded = spec.get_execution_requests_list(requests)

    expected = sha256(b"".join(sha256(r).digest() for r in encoded)).digest()
    assert bytes(spec.compute_requests_hash(encoded)) == expected


@with_payload_request_chain_and_later
@spec_test
@single_phase
def test_requests_list_covers_builder_request_types(spec):
    """
    EIP-8282 builder deposits and exits are committed by the execution header's
    requests_hash, so the consensus layer's re-derivation must include them.
    """
    requests = spec.ExecutionRequests(
        builder_deposits=spec.BuilderDepositRequests(
            data=[
                spec.BuilderDepositRequest(
                    pubkey=spec.BLSPubkey(b"\x12" * 48),
                    withdrawal_credentials=spec.Bytes32(b"\x34" * 32),
                    amount=spec.Gwei(32000000000),
                    signature=spec.BLSSignature(b"\x56" * 96),
                )
            ]
        ),
    )
    encoded = spec.get_execution_requests_list(requests)

    assert len(encoded) == 1
    assert encoded[0][:1] == spec.BUILDER_DEPOSIT_REQUEST_TYPE
    assert spec.compute_requests_hash(encoded) != spec.compute_requests_hash([])
