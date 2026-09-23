from eth_consensus_specs.test.context import (
    single_phase,
    spec_state_test,
    spec_test,
    with_eip9999_and_later,
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
        requests_hash=spec.Hash32(b"\xee" * 32),
    )


@with_eip9999_and_later
@spec_test
@single_phase
def test_commitment_binds_every_field(spec):
    """Mutating any commitment field must change the payload request root."""
    base = build_request_commitment(spec, build_payload_commitment(spec))
    base_root = spec.hash_tree_root(base)

    for field, value in (
        ("parent_hash", spec.Hash32(b"\x01" * 32)),
        ("prev_randao", spec.Bytes32(b"\x02" * 32)),
        ("gas_limit", spec.Uint64(29999999)),
        ("timestamp", spec.Uint64(1700000001)),
        ("block_hash", spec.Hash32(b"\x03" * 32)),
        ("slot_number", spec.Uint64(43)),
    ):
        mutated_payload = base.execution_payload.copy()
        setattr(mutated_payload, field, value)
        mutated = base.copy()
        mutated.execution_payload = mutated_payload
        assert spec.hash_tree_root(mutated) != base_root, field

    for field, value in (
        ("parent_beacon_block_root", spec.Root(b"\x04" * 32)),
        ("requests_hash", spec.Hash32(b"\x05" * 32)),
        (
            "versioned_hashes",
            spec.VersionedHashes(data=[spec.VersionedHash(b"\x01" + b"\xee" * 31)]),
        ),
    ):
        mutated = base.copy()
        setattr(mutated, field, value)
        assert spec.hash_tree_root(mutated) != base_root, field


@with_eip9999_and_later
@spec_state_test
def test_chain_root_is_computable_without_the_payload(spec, state):
    """
    The consensus layer derives the commitment from the bid, beacon state and
    block body, and the execution layer from the payload it holds. Both must
    reach the same root, and the consensus path must never touch a payload.
    """
    requests = spec.ExecutionRequests()
    state.payload_expected_withdrawals = spec.Withdrawals(
        data=[
            spec.Withdrawal(
                index=spec.WithdrawalIndex(1),
                validator_index=spec.ValidatorIndex(2),
                address=spec.ExecutionAddress(b"\x99" * 20),
                amount=spec.Gwei(42),
            )
        ]
    )
    state.payload_request_chain_root = spec.Bytes32()

    bid = state.latest_execution_payload_bid.copy()
    bid.parent_block_hash = spec.Hash32(b"\xaa" * 32)
    bid.block_hash = spec.Hash32(b"\x66" * 32)
    bid.prev_randao = spec.Bytes32(b"\xbb" * 32)
    bid.gas_limit = spec.Uint64(30000000)
    bid.slot = state.slot
    bid.blob_kzg_commitments = spec.BlobKZGCommitments()

    chain_root = spec.compute_payload_request_chain_root(state, bid, requests)

    # The execution layer builds the same commitment from the payload it
    # executed, and from the requests_hash its header already carries.
    payload = spec.ExecutionPayload(
        parent_hash=bid.parent_block_hash,
        fee_recipient=spec.ExecutionAddress(),
        state_root=spec.Bytes32(b"\x11" * 32),
        receipts_root=spec.Bytes32(b"\x22" * 32),
        logs_bloom=spec.LogsBloom(b"\x33" * 256),
        prev_randao=bid.prev_randao,
        block_number=spec.Uint64(7),
        gas_limit=bid.gas_limit,
        gas_used=spec.Uint64(21000),
        timestamp=spec.compute_time_at_slot(state, bid.slot),
        extra_data=spec.ExtraData(data=[]),
        base_fee_per_gas=spec.Uint256(1),
        block_hash=bid.block_hash,
        transactions=spec.Transactions(),
        withdrawals=state.payload_expected_withdrawals,
        blob_gas_used=spec.Uint64(0),
        excess_blob_gas=spec.Uint64(0),
        block_access_list=spec.BlockAccessList(),
        slot_number=bid.slot,
    )
    encoded = spec.get_execution_requests_list(requests)
    el_commitment = spec.NewPayloadRequestCommitment(
        execution_payload=spec.ExecutionPayloadCommitment(
            parent_hash=payload.parent_hash,
            prev_randao=payload.prev_randao,
            gas_limit=payload.gas_limit,
            timestamp=payload.timestamp,
            block_hash=payload.block_hash,
            withdrawals=payload.withdrawals,
            slot_number=payload.slot_number,
        ),
        versioned_hashes=spec.VersionedHashes(),
        parent_beacon_block_root=state.latest_block_header.parent_root,
        requests_hash=spec.sha256(b"".join(spec.sha256(r) for r in encoded)),
    )
    el_chain_root = spec.sha256(spec.Bytes32() + spec.hash_tree_root(el_commitment))

    assert chain_root == el_chain_root


@with_eip9999_and_later
@spec_state_test
def test_chain_binds_position_not_membership(spec, state):
    """Folding the same payload twice must not be indistinguishable."""
    requests = spec.ExecutionRequests()
    state.payload_request_chain_root = spec.Bytes32()
    bid = state.latest_execution_payload_bid.copy()
    bid.slot = state.slot

    first = spec.compute_payload_request_chain_root(state, bid, requests)
    state.payload_request_chain_root = first
    second = spec.compute_payload_request_chain_root(state, bid, requests)

    assert first != spec.Bytes32()
    assert second != first
