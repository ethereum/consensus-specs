from eth_consensus_specs.test.context import (
    single_phase,
    spec_state_test,
    spec_test,
    with_eip9999_and_later,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block


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


def build_block_with_bid(spec, parent_block_hash, requests=None):
    """A block whose bid claims `parent_block_hash` as its parent payload."""
    block = spec.BeaconBlock()
    bid = block.body.signed_execution_payload_bid.message
    bid.parent_block_hash = parent_block_hash
    block.body.parent_execution_requests = (
        requests if requests is not None else spec.ExecutionRequests()
    )
    return block


@with_eip9999_and_later
@spec_state_test
def test_chain_does_not_advance_on_an_empty_parent(spec, state):
    """
    A bid is processed for every block, but its payload may never be revealed.
    The execution layer produces no block for such a slot, so the chain must
    not advance for it -- otherwise the two chains desynchronise on an
    entirely honest chain.
    """
    state.payload_request_chain_root = spec.Bytes32(b"\x07" * 32)
    before = state.payload_request_chain_root

    # Parent was EMPTY: the bid's parent_block_hash does not match the
    # committed parent bid's block_hash.
    parent_bid = state.latest_execution_payload_bid.copy()
    parent_bid.block_hash = spec.Hash32(b"\x11" * 32)
    state.latest_execution_payload_bid = parent_bid
    block = build_block_with_bid(spec, spec.Hash32(b"\x22" * 32))

    spec.process_parent_execution_payload(state, block)

    assert state.payload_request_chain_root == before


@with_eip9999_and_later
@spec_state_test
def test_chain_advances_on_a_full_parent(spec, state):
    """The mirror of the above: a revealed parent payload does advance it."""
    state.payload_request_chain_root = spec.Bytes32(b"\x07" * 32)
    before = state.payload_request_chain_root

    requests = spec.ExecutionRequests()
    parent_bid = state.latest_execution_payload_bid.copy()
    parent_bid.block_hash = spec.Hash32(b"\x11" * 32)
    parent_bid.execution_requests_root = spec.hash_tree_root(requests)
    state.latest_execution_payload_bid = parent_bid

    # Parent was FULL: the bid names the committed parent bid's block_hash.
    block = build_block_with_bid(spec, parent_bid.block_hash, requests)
    expected = spec.compute_payload_request_chain_root(state, parent_bid, requests)

    spec.process_parent_execution_payload(state, block)

    assert state.payload_request_chain_root != before
    assert state.payload_request_chain_root == expected


@with_eip9999_and_later
@spec_state_test
def test_empty_slots_are_skipped_not_reordered(spec, state):
    """
    A run of empty slots between two full payloads must produce the same chain
    as if they had not occurred. The chain is over execution blocks, not slots.
    """
    requests = spec.ExecutionRequests()
    parent_bid = state.latest_execution_payload_bid.copy()
    parent_bid.block_hash = spec.Hash32(b"\x11" * 32)
    parent_bid.execution_requests_root = spec.hash_tree_root(requests)
    state.latest_execution_payload_bid = parent_bid
    state.payload_request_chain_root = spec.Bytes32()

    # Three empty parents, then a full one.
    for _ in range(3):
        spec.process_parent_execution_payload(
            state, build_block_with_bid(spec, spec.Hash32(b"\x22" * 32))
        )
    spec.process_parent_execution_payload(
        state, build_block_with_bid(spec, parent_bid.block_hash, requests)
    )
    with_empties = state.payload_request_chain_root

    # The same full payload with no empty slots preceding it.
    state.latest_execution_payload_bid = parent_bid
    state.payload_request_chain_root = spec.Bytes32()
    spec.process_parent_execution_payload(
        state, build_block_with_bid(spec, parent_bid.block_hash, requests)
    )

    assert state.payload_request_chain_root == with_empties


@with_eip9999_and_later
@spec_state_test
def test_execution_requests_reach_the_chain_root(spec, state):
    """
    Requests are the one datum that flows from the execution layer into beacon
    state, and during sync the consensus layer applies them on a builder's word
    alone. They must therefore reach the commitment, via the EIP-7685 digest
    that the execution header carries.
    """
    state.payload_request_chain_root = spec.Bytes32()
    bid = state.latest_execution_payload_bid.copy()
    bid.slot = state.slot

    empty = spec.ExecutionRequests()
    populated = spec.ExecutionRequests(
        withdrawals=spec.WithdrawalRequests(
            data=[
                spec.WithdrawalRequest(
                    source_address=spec.ExecutionAddress(b"\x11" * 20),
                    validator_pubkey=spec.BLSPubkey(b"\x22" * 48),
                    amount=spec.Gwei(1),
                )
            ]
        )
    )

    assert spec.compute_payload_request_chain_root(
        state, bid, empty
    ) != spec.compute_payload_request_chain_root(state, bid, populated)


@with_eip9999_and_later
@spec_state_test
def test_range_sync_without_payloads(spec, state):
    """
    Range sync processes beacon blocks and no payload envelopes. Slots whose
    payload is never revealed produce no execution block, so the accumulator
    must be untouched by them -- otherwise a consensus client's value would
    diverge from an execution client that produced nothing for those slots.

    This drives full blocks through the state transition rather than calling
    the handler directly, so it covers the path a syncing client actually
    takes.
    """
    state.payload_request_chain_root = spec.Bytes32(b"\x07" * 32)
    before = state.payload_request_chain_root

    for _ in range(4):
        block = build_empty_block_for_next_slot(spec, state)
        state_transition_and_sign_block(spec, state, block)

    assert state.payload_request_chain_root == before


@with_eip9999_and_later
@spec_state_test
def test_range_sync_accumulates_over_revealed_payloads(spec, state):
    """
    The mirror of the above. Over a run of slots whose payloads were revealed,
    the accumulator must advance once per payload and arrive at the value an
    execution client reaches by folding the same roots in the same order.

    Neither side handles a payload here: the consensus layer works from the
    bids and its own state, which is what makes range sync without envelopes
    possible.
    """
    state.payload_request_chain_root = spec.Bytes32()
    requests = spec.ExecutionRequests()

    expected = state.payload_request_chain_root
    for i in range(4):
        parent_bid = state.latest_execution_payload_bid.copy()
        parent_bid.block_hash = spec.Hash32(bytes([i + 1]) + b"\x00" * 31)
        parent_bid.execution_requests_root = spec.hash_tree_root(requests)
        state.latest_execution_payload_bid = parent_bid

        # An execution client folds the same root from the block it holds.
        expected = spec.compute_payload_request_chain_root(state, parent_bid, requests)

        block = build_block_with_bid(spec, parent_bid.block_hash, requests)
        spec.process_parent_execution_payload(state, block)

        assert state.payload_request_chain_root == expected

    assert state.payload_request_chain_root != spec.Bytes32()
