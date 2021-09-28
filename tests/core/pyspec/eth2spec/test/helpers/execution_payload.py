def build_empty_execution_payload(spec, state):
    """
    Assuming a pre-state of the same slot, build a valid ExecutionPayload without any transactions.
    """
    return build_execution_payload(spec, state)


def build_execution_payload(spec,
                            state,
                            *,
                            parent_hash=None,
                            coinbase=None,
                            state_root=None,
                            receipt_root=None,
                            logs_bloom=None,
                            block_number=None,
                            random=None,
                            gas_limit=None,
                            gas_used=0,
                            timestamp=None,
                            extra_data=None,
                            base_fee_per_gas=None,
                            block_hash=None,
                            transactions=None):
    latest = state.latest_execution_payload_header
    # By default, assuming a pre-state of the same slot, build a valid ExecutionPayload without any transactions.
    if parent_hash is None:
        parent_hash = latest.block_hash
    if coinbase is None:
        coinbase = spec.ExecutionAddress()
    if state_root is None:
        state_root = latest.state_root
    if receipt_root is None:
        receipt_root = b"no receipts here" + b"\x00" * 16  # TODO: root of empty MPT may be better.
    if logs_bloom is None:
        logs_bloom = spec.ByteVector[spec.BYTES_PER_LOGS_BLOOM]()  # TODO: zeroed logs bloom for empty logs ok?
    if block_number is None:
        block_number = latest.block_number + 1
    if random is None:
        random = spec.get_randao_mix(state, spec.get_current_epoch(state))
    if gas_limit is None:
        gas_limit = latest.gas_limit  # retain same limit
    if timestamp is None:
        timestamp = spec.compute_timestamp_at_slot(state, state.slot)
    if extra_data is None:
        extra_data = spec.ByteList[spec.MAX_EXTRA_DATA_BYTES]()
    if base_fee_per_gas is None:
        base_fee_per_gas = latest.base_fee_per_gas  # retain same base_fee
    if transactions is None:
        transactions = spec.List[spec.Transaction, spec.MAX_TRANSACTIONS_PER_PAYLOAD]()

    payload = spec.ExecutionPayload(
        parent_hash=parent_hash,
        coinbase=coinbase,
        state_root=state_root,
        receipt_root=receipt_root,
        logs_bloom=logs_bloom,
        block_number=block_number,
        random=random,
        gas_limit=gas_limit,
        gas_used=gas_used,
        timestamp=timestamp,
        extra_data=extra_data,
        base_fee_per_gas=base_fee_per_gas,
        transactions=transactions,
    )

    # TODO: real RLP + block hash logic would be nice, requires RLP and keccak256 dependency however.
    payload.block_hash = (
        block_hash if block_hash is not None
        else spec.Hash32(spec.hash(parent_hash + b"FAKE RLP HASH"))
    )

    return payload


def get_execution_payload_header(spec, execution_payload):
    return spec.ExecutionPayloadHeader(
        parent_hash=execution_payload.parent_hash,
        coinbase=execution_payload.coinbase,
        state_root=execution_payload.state_root,
        receipt_root=execution_payload.receipt_root,
        logs_bloom=execution_payload.logs_bloom,
        random=execution_payload.random,
        block_number=execution_payload.block_number,
        gas_limit=execution_payload.gas_limit,
        gas_used=execution_payload.gas_used,
        timestamp=execution_payload.timestamp,
        extra_data=execution_payload.extra_data,
        base_fee_per_gas=execution_payload.base_fee_per_gas,
        block_hash=execution_payload.block_hash,
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
