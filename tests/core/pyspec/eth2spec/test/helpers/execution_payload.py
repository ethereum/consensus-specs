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
        receipt_root=b"no receipts here" + b"\x00" * 16,  # TODO: root of empty MPT may be better.
        logs_bloom=spec.ByteVector[spec.BYTES_PER_LOGS_BLOOM](),  # TODO: zeroed logs bloom for empty logs ok?
        transactions=empty_txs,
    )
    # TODO: real RLP + block hash logic would be nice, requires RLP and keccak256 dependency however.
    payload.block_hash = spec.Hash32(spec.hash(payload.hash_tree_root() + b"FAKE RLP HASH"))

    return payload


def get_execution_payload_header(spec, execution_payload):
    return spec.ExecutionPayloadHeader(
        block_hash=execution_payload.block_hash,
        parent_hash=execution_payload.parent_hash,
        coinbase=execution_payload.coinbase,
        state_root=execution_payload.state_root,
        number=execution_payload.number,
        gas_limit=execution_payload.gas_limit,
        gas_used=execution_payload.gas_used,
        timestamp=execution_payload.timestamp,
        receipt_root=execution_payload.receipt_root,
        logs_bloom=execution_payload.logs_bloom,
        transactions_root=spec.hash_tree_root(execution_payload.transactions)
    )


def build_state_with_incomplete_transition(spec, state):
    return build_state_with_execution_payload_header(spec, state, spec.ExecutionPayloadHeader())


def build_state_with_complete_transition(spec, state):
    pre_state_payload = build_empty_execution_payload(spec, state)
    payload_header = get_execution_payload_header(spec, pre_state_payload)

    return build_state_with_execution_payload_header(spec, state, payload_header)


def build_state_with_execution_payload_header(spec, state, execution_payload_header):
    pre_state = state.copy()
    pre_state.latest_execution_payload_header = execution_payload_header

    return pre_state
