from eth_hash.auto import keccak
from trie import HexaryTrie
from rlp import encode
from rlp.sedes import big_endian_int, Binary, List

from eth2spec.debug.random_value import get_random_bytes_list
from eth2spec.test.helpers.forks import (
    is_post_capella,
    is_post_deneb,
    is_post_eip6110,
    is_post_eip7002,
)


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
    if is_post_deneb(spec):
        payload_header.blob_gas_used = execution_payload.blob_gas_used
        payload_header.excess_blob_gas = execution_payload.excess_blob_gas
    if is_post_eip6110(spec):
        payload_header.deposit_receipts_root = spec.hash_tree_root(execution_payload.deposit_receipts)
    if is_post_eip7002(spec):
        payload_header.exits_root = spec.hash_tree_root(execution_payload.exits)
    return payload_header


# https://eips.ethereum.org/EIPS/eip-2718
def compute_trie_root_from_indexed_data(data):
    """
    Computes the root hash of `patriciaTrie(rlp(Index) => Data)` for a data array.
    """
    t = HexaryTrie(db={})
    for i, obj in enumerate(data):
        k = encode(i, big_endian_int)
        t.set(k, obj)
    return t.root_hash


# https://eips.ethereum.org/EIPS/eip-4895
# https://eips.ethereum.org/EIPS/eip-4844
def compute_el_header_block_hash(spec,
                                 payload_header,
                                 transactions_trie_root,
                                 withdrawals_trie_root=None,
                                 deposit_receipts_trie_root=None,
                                 exits_trie_root=None):
    """
    Computes the RLP execution block hash described by an `ExecutionPayloadHeader`.
    """
    execution_payload_header_rlp = [
        # parent_hash
        (Binary(32, 32), payload_header.parent_hash),
        # ommers_hash
        (Binary(32, 32), bytes.fromhex("1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347")),
        # coinbase
        (Binary(20, 20), payload_header.fee_recipient),
        # state_root
        (Binary(32, 32), payload_header.state_root),
        # txs_root
        (Binary(32, 32), transactions_trie_root),
        # receipts_root
        (Binary(32, 32), payload_header.receipts_root),
        # logs_bloom
        (Binary(256, 256), payload_header.logs_bloom),
        # difficulty
        (big_endian_int, 0),
        # number
        (big_endian_int, payload_header.block_number),
        # gas_limit
        (big_endian_int, payload_header.gas_limit),
        # gas_used
        (big_endian_int, payload_header.gas_used),
        # timestamp
        (big_endian_int, payload_header.timestamp),
        # extradata
        (Binary(0, 32), payload_header.extra_data),
        # prev_randao
        (Binary(32, 32), payload_header.prev_randao),
        # nonce
        (Binary(8, 8), bytes.fromhex("0000000000000000")),
        # base_fee_per_gas
        (big_endian_int, payload_header.base_fee_per_gas),
    ]
    if is_post_capella(spec):
        # withdrawals_root
        execution_payload_header_rlp.append((Binary(32, 32), withdrawals_trie_root))
    if is_post_deneb(spec):
        # excess_blob_gas
        execution_payload_header_rlp.append((big_endian_int, payload_header.blob_gas_used))
        execution_payload_header_rlp.append((big_endian_int, payload_header.excess_blob_gas))
    if is_post_eip6110(spec):
        # deposit_receipts_root
        assert deposit_receipts_trie_root is not None
        execution_payload_header_rlp.append((Binary(32, 32), deposit_receipts_trie_root))
    if is_post_eip7002(spec):
        # exits_trie_root
        execution_payload_header_rlp.append((Binary(32, 32), exits_trie_root))

    sedes = List([schema for schema, _ in execution_payload_header_rlp])
    values = [value for _, value in execution_payload_header_rlp]
    encoded = encode(values, sedes)

    return spec.Hash32(keccak(encoded))


# https://eips.ethereum.org/EIPS/eip-4895
def get_withdrawal_rlp(withdrawal):
    withdrawal_rlp = [
        # index
        (big_endian_int, withdrawal.index),
        # validator_index
        (big_endian_int, withdrawal.validator_index),
        # address
        (Binary(20, 20), withdrawal.address),
        # amount
        (big_endian_int, withdrawal.amount),
    ]

    sedes = List([schema for schema, _ in withdrawal_rlp])
    values = [value for _, value in withdrawal_rlp]
    return encode(values, sedes)


# https://eips.ethereum.org/EIPS/eip-7002
def get_exit_rlp(exit):
    exit_rlp = [
        # source_address
        (Binary(20, 20), exit.source_address),
        # validator_pubkey
        (Binary(48, 48), exit.validator_pubkey),
    ]

    sedes = List([schema for schema, _ in exit_rlp])
    values = [value for _, value in exit_rlp]
    return encode(values, sedes)


def get_deposit_receipt_rlp(spec, deposit_receipt):
    deposit_receipt_rlp = [
        # pubkey
        (Binary(48, 48), deposit_receipt.pubkey),
        # withdrawal_credentials
        (Binary(32, 32), deposit_receipt.withdrawal_credentials),
        # amount
        (big_endian_int, deposit_receipt.amount),
        # pubkey
        (Binary(96, 96), deposit_receipt.signature),
        # index
        (big_endian_int, deposit_receipt.index),
    ]

    sedes = List([schema for schema, _ in deposit_receipt_rlp])
    values = [value for _, value in deposit_receipt_rlp]
    return encode(values, sedes)


def compute_el_block_hash(spec, payload):
    transactions_trie_root = compute_trie_root_from_indexed_data(payload.transactions)

    withdrawals_trie_root = None
    deposit_receipts_trie_root = None
    exits_trie_root = None

    if is_post_capella(spec):
        withdrawals_encoded = [get_withdrawal_rlp(withdrawal) for withdrawal in payload.withdrawals]
        withdrawals_trie_root = compute_trie_root_from_indexed_data(withdrawals_encoded)
    if is_post_eip6110(spec):
        deposit_receipts_encoded = [get_deposit_receipt_rlp(spec, receipt) for receipt in payload.deposit_receipts]
        deposit_receipts_trie_root = compute_trie_root_from_indexed_data(deposit_receipts_encoded)
    if is_post_eip7002(spec):
        exits_encoded = [get_exit_rlp(exit) for exit in payload.exits]
        exits_trie_root = compute_trie_root_from_indexed_data(exits_encoded)

    payload_header = get_execution_payload_header(spec, payload)

    return compute_el_header_block_hash(
        spec,
        payload_header,
        transactions_trie_root,
        withdrawals_trie_root,
        deposit_receipts_trie_root,
        exits_trie_root,
    )


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
        receipts_root=spec.Bytes32(bytes.fromhex("1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347")),
        logs_bloom=spec.ByteVector[spec.BYTES_PER_LOGS_BLOOM](),  # TODO: zeroed logs bloom for empty logs ok?
        block_number=latest.block_number + 1,
        prev_randao=randao_mix,
        gas_limit=latest.gas_limit,  # retain same limit
        gas_used=0,  # empty block, 0 gas
        timestamp=timestamp,
        extra_data=spec.ByteList[spec.MAX_EXTRA_DATA_BYTES](),
        base_fee_per_gas=latest.base_fee_per_gas,  # retain same base_fee
        transactions=empty_txs,
    )
    if is_post_capella(spec):
        payload.withdrawals = spec.get_expected_withdrawals(state)
    if is_post_deneb(spec):
        payload.blob_gas_used = 0
        payload.excess_blob_gas = 0
    if is_post_eip6110(spec):
        # just to be clear
        payload.deposit_receipts = []

    payload.block_hash = compute_el_block_hash(spec, payload)

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

    num_transactions = rng.randint(0, 100)
    execution_payload.transactions = [
        get_random_tx(rng)
        for _ in range(num_transactions)
    ]

    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload)

    return execution_payload


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


def get_random_tx(rng):
    return get_random_bytes_list(rng, rng.randint(0, 1000))
