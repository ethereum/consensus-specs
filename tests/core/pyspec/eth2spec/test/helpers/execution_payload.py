from eth2spec.debug.random_value import get_random_bytes_list
from eth2spec.test.context import is_post_capella


def build_empty_execution_payload(spec, state, randao_mix=None):
    """
    Assuming a pre-state of the same slot, build a valid ExecutionPayload without any transactions.
    """
    latest = state.latest_execution_payload_header
    timestamp = spec.compute_timestamp_at_slot(state, state.slot)
    empty_txs = spec.List[spec.Transaction, spec.MAX_TRANSACTIONS_PER_PAYLOAD]()

    if randao_mix is None:
        randao_mix = spec.get_randao_mix(state, spec.get_current_epoch(state))

    payload = spec.ExecutionPayload(
        parent_hash=latest.block_hash,
        fee_recipient=spec.ExecutionAddress(),
        state_root=latest.state_root,  # no changes to the state
        receipts_root=b"no receipts here" + b"\x00" * 16,  # TODO: root of empty MPT may be better.
        logs_bloom=spec.ByteVector[spec.BYTES_PER_LOGS_BLOOM](),  # TODO: zeroed logs bloom for empty logs ok?
        block_number=latest.block_number + 1,
        prev_randao=randao_mix,
        gas_limit=latest.gas_limit,  # retain same limit
        gas_used=0,  # empty block, 0 gas
        timestamp=timestamp,
        extra_data=spec.ByteList[spec.MAX_EXTRA_DATA_BYTES](),
        base_fee_per_gas=latest.base_fee_per_gas,  # retain same base_fee
        block_hash=spec.Hash32(),
        transactions=empty_txs,
    )
    if is_post_capella(spec):
        num_withdrawals = min(spec.MAX_WITHDRAWALS_PER_PAYLOAD, len(state.withdrawal_queue))
        payload.withdrawals = state.withdrawal_queue[:num_withdrawals]

    # TODO: real RLP + block hash logic would be nice, requires RLP and keccak256 dependency however.
    payload.block_hash = spec.Hash32(spec.hash(payload.hash_tree_root() + b"FAKE RLP HASH"))

    return payload


def build_randomized_execution_payload(spec, state, rng):
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.fee_recipient = spec.ExecutionAddress(get_random_bytes_list(rng, 20))
    execution_payload.state_root = spec.Bytes32(get_random_bytes_list(rng, 32))
    execution_payload.receipts_root = spec.Bytes32(get_random_bytes_list(rng, 32))
    execution_payload.logs_bloom = spec.ByteVector[spec.BYTES_PER_LOGS_BLOOM](
        get_random_bytes_list(rng, spec.BYTES_PER_LOGS_BLOOM)
    )
    execution_payload.block_number = rng.randint(0, 10e10)
    execution_payload.gas_limit = rng.randint(0, 10e10)
    execution_payload.gas_used = rng.randint(0, 10e10)
    extra_data_length = rng.randint(0, spec.MAX_EXTRA_DATA_BYTES)
    execution_payload.extra_data = spec.ByteList[spec.MAX_EXTRA_DATA_BYTES](
        get_random_bytes_list(rng, extra_data_length)
    )
    execution_payload.base_fee_per_gas = rng.randint(0, 2**256 - 1)
    execution_payload.block_hash = spec.Hash32(get_random_bytes_list(rng, 32))

    num_transactions = rng.randint(0, 100)
    execution_payload.transactions = [
        spec.Transaction(get_random_bytes_list(rng, rng.randint(0, 1000)))
        for _ in range(num_transactions)
    ]

    return execution_payload


def get_execution_payload_header(spec, execution_payload):
    payload_header = spec.ExecutionPayloadHeader(
        parent_hash=execution_payload.parent_hash,
        fee_recipient=execution_payload.fee_recipient,
        state_root=execution_payload.state_root,
        receipts_root=execution_payload.receipts_root,
        logs_bloom=execution_payload.logs_bloom,
        prev_randao=execution_payload.prev_randao,
        block_number=execution_payload.block_number,
        gas_limit=execution_payload.gas_limit,
        gas_used=execution_payload.gas_used,
        timestamp=execution_payload.timestamp,
        extra_data=execution_payload.extra_data,
        base_fee_per_gas=execution_payload.base_fee_per_gas,
        block_hash=execution_payload.block_hash,
        transactions_root=spec.hash_tree_root(execution_payload.transactions)
    )
    if is_post_capella(spec):
        payload_header.withdrawals_root = spec.hash_tree_root(execution_payload.withdrawals)
    return payload_header


def build_state_with_incomplete_transition(spec, state):
    state = build_state_with_execution_payload_header(spec, state, spec.ExecutionPayloadHeader())
    assert not spec.is_merge_transition_complete(state)

    return state


def build_state_with_complete_transition(spec, state):
    pre_state_payload = build_empty_execution_payload(spec, state)
    payload_header = get_execution_payload_header(spec, pre_state_payload)

    state = build_state_with_execution_payload_header(spec, state, payload_header)
    assert spec.is_merge_transition_complete(state)

    return state


def build_state_with_execution_payload_header(spec, state, execution_payload_header):
    pre_state = state.copy()
    pre_state.latest_execution_payload_header = execution_payload_header

    return pre_state
