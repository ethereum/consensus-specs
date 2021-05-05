
def build_empty_execution_payload(spec, state):
    """
    Assuming a pre-state of the same slot, build a valid ExecutionPayload without any transactions.
    """
    latest = state.latest_execution_payload_header
    timestamp = spec.compute_time_at_slot(state, state.slot)
    empty_txs = spec.List[spec.OpaqueTransaction, spec.MAX_EXECUTION_TRANSACTIONS]()

    payload = spec.ExecutionPayload(
        block_hash=spec.Hash32(),
        parent_hash=latest.block_hash,
        coinbase=spec.Bytes20(),
        state_root=latest.state_root,  # no changes to the state
        number=latest.number + 1,
        gas_limit=latest.gas_limit,  # retain same limit
        gas_used=0,  # empty block, 0 gas
        timestamp=timestamp,
        receipt_root=b"no receipts here" + b"\x00"*16,  # TODO: root of empty MPT may be better.
        logs_bloom=spec.ByteVector[spec.BYTES_PER_LOGS_BLOOM](),  # TODO: zeroed logs bloom for empty logs ok?
        transactions=empty_txs,
    )
    # TODO: real RLP + block hash logic would be nice, requires RLP and keccak256 dependency however.
    payload.block_hash = spec.Hash32(spec.hash(payload.hash_tree_root() + b"FAKE RLP HASH"))

    return payload
