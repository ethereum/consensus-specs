from hashlib import sha256

from eth_hash.auto import keccak
from rlp import encode
from rlp.sedes import big_endian_int, Binary, List
from trie import HexaryTrie

from eth_consensus_specs.debug.random_value import get_random_bytes_list
from eth_consensus_specs.test.helpers.forks import (
    is_post_capella,
    is_post_deneb,
    is_post_electra,
    is_post_gloas,
)
from eth_consensus_specs.test.helpers.keys import builder_privkeys, privkeys
from eth_consensus_specs.test.helpers.withdrawals import get_expected_withdrawals
from eth_consensus_specs.utils.ssz.ssz_impl import hash_tree_root


def get_execution_payload_header(spec, execution_payload):
    assert not is_post_gloas(spec)

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
        transactions_root=spec.hash_tree_root(execution_payload.transactions),
    )
    if is_post_capella(spec):
        payload_header.withdrawals_root = spec.hash_tree_root(execution_payload.withdrawals)
    if is_post_deneb(spec):
        payload_header.blob_gas_used = execution_payload.blob_gas_used
        payload_header.excess_blob_gas = execution_payload.excess_blob_gas
    return payload_header


def get_execution_payload_bid(spec, state, execution_payload):
    if not is_post_gloas(spec):
        raise ValueError("get_execution_payload_bid only available for gloas and later")

    parent_block_root = hash_tree_root(state.latest_block_header)
    kzg_list = spec.ProgressiveList[spec.KZGCommitment]()
    builder_index = spec.get_beacon_proposer_index(state)

    return spec.ExecutionPayloadBid(
        parent_block_hash=execution_payload.parent_hash,
        parent_block_root=parent_block_root,
        block_hash=execution_payload.block_hash,
        fee_recipient=execution_payload.fee_recipient,
        gas_limit=execution_payload.gas_limit,
        builder_index=builder_index,
        slot=state.slot,
        value=spec.Gwei(0),
        blob_kzg_commitments=kzg_list,
        execution_requests_root=spec.hash_tree_root(spec.ExecutionRequests()),
    )


# https://eips.ethereum.org/EIPS/eip-2718
def compute_trie_root_from_indexed_data(data):
    """
    Computes the root hash of `patriciaTrie(rlp(Index) => Data)` for a data array.
    """
    t = HexaryTrie(db={})
    for i, obj in enumerate(data):
        k = encode(i, big_endian_int)
        t.set(k, obj)  # Implicitly skipped if `obj == b''` (invalid RLP)
    return t.root_hash


# https://eips.ethereum.org/EIPS/eip-7685
def compute_requests_hash(block_requests):
    m = sha256()
    for r in block_requests:
        if len(r) > 1:
            m.update(sha256(r).digest())
    return m.digest()


# https://eips.ethereum.org/EIPS/eip-4895
# https://eips.ethereum.org/EIPS/eip-4844
def compute_el_header_block_hash(
    spec,
    payload,
    transactions_trie_root,
    withdrawals_trie_root=None,
    parent_beacon_block_root=None,
    requests_hash=None,
    block_access_list_hash=None,
):
    """
    Computes the RLP execution block hash described by an `ExecutionPayload`.
    """
    execution_payload_header_rlp = [
        # parent_hash
        (Binary(32, 32), payload.parent_hash),
        # ommers_hash
        (
            Binary(32, 32),
            bytes.fromhex("1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347"),
        ),
        # coinbase
        (Binary(20, 20), payload.fee_recipient),
        # state_root
        (Binary(32, 32), payload.state_root),
        # txs_root
        (Binary(32, 32), transactions_trie_root),
        # receipts_root
        (Binary(32, 32), payload.receipts_root),
        # logs_bloom
        (Binary(256, 256), payload.logs_bloom),
        # difficulty
        (big_endian_int, 0),
        # number
        (big_endian_int, payload.block_number),
        # gas_limit
        (big_endian_int, payload.gas_limit),
        # gas_used
        (big_endian_int, payload.gas_used),
        # timestamp
        (big_endian_int, payload.timestamp),
        # extradata
        (Binary(0, 32), payload.extra_data),
        # prev_randao
        (Binary(32, 32), payload.prev_randao),
        # nonce
        (Binary(8, 8), bytes.fromhex("0000000000000000")),
        # base_fee_per_gas
        (big_endian_int, payload.base_fee_per_gas),
    ]
    if is_post_capella(spec):
        # withdrawals_root
        execution_payload_header_rlp.append((Binary(32, 32), withdrawals_trie_root))
    if is_post_deneb(spec):
        # blob_gas_used
        execution_payload_header_rlp.append((big_endian_int, payload.blob_gas_used))
        # excess_blob_gas
        execution_payload_header_rlp.append((big_endian_int, payload.excess_blob_gas))
        # parent_beacon_root
        execution_payload_header_rlp.append((Binary(32, 32), parent_beacon_block_root))
    if is_post_electra(spec):
        # requests_hash
        execution_payload_header_rlp.append((Binary(32, 32), requests_hash))
    if is_post_gloas(spec):
        # block access list
        execution_payload_header_rlp.append((Binary(32, 32), block_access_list_hash))
        # slot number
        execution_payload_header_rlp.append((big_endian_int, payload.slot_number))

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


def get_deposit_request_rlp_bytes(deposit_request):
    deposit_request_rlp = [
        # pubkey
        (Binary(48, 48), deposit_request.pubkey),
        # withdrawal_credentials
        (Binary(32, 32), deposit_request.withdrawal_credentials),
        # amount
        (big_endian_int, deposit_request.amount),
        # pubkey
        (Binary(96, 96), deposit_request.signature),
        # index
        (big_endian_int, deposit_request.index),
    ]

    sedes = List([schema for schema, _ in deposit_request_rlp])
    values = [value for _, value in deposit_request_rlp]
    return b"\x00" + encode(values, sedes)


# https://eips.ethereum.org/EIPS/eip-7002
def get_withdrawal_request_rlp_bytes(withdrawal_request):
    withdrawal_request_rlp = [
        # source_address
        (Binary(20, 20), withdrawal_request.source_address),
        # validator_pubkey
        (Binary(48, 48), withdrawal_request.validator_pubkey),
    ]

    sedes = List([schema for schema, _ in withdrawal_request_rlp])
    values = [value for _, value in withdrawal_request_rlp]
    return b"\x01" + encode(values, sedes)


# https://eips.ethereum.org/EIPS/eip-7251
def get_consolidation_request_rlp_bytes(consolidation_request):
    consolidation_request_rlp = [
        # source_address
        (Binary(20, 20), consolidation_request.source_address),
        # source_pubkey
        (Binary(48, 48), consolidation_request.source_pubkey),
        # target_pubkey
        (Binary(48, 48), consolidation_request.target_pubkey),
    ]

    sedes = List([schema for schema, _ in consolidation_request_rlp])
    values = [value for _, value in consolidation_request_rlp]
    return b"\x02" + encode(values, sedes)


def compute_el_block_hash_with_new_fields(spec, payload, parent_beacon_block_root, requests_hash):
    if payload == spec.ExecutionPayload():
        return spec.Hash32()

    transactions_trie_root = compute_trie_root_from_indexed_data(payload.transactions)

    withdrawals_trie_root = None
    block_access_list_hash = None

    if is_post_capella(spec):
        withdrawals_encoded = [get_withdrawal_rlp(withdrawal) for withdrawal in payload.withdrawals]
        withdrawals_trie_root = compute_trie_root_from_indexed_data(withdrawals_encoded)
    if not is_post_deneb(spec):
        parent_beacon_block_root = None
    if is_post_gloas(spec):
        block_access_list_rlp = encode(bytearray(payload.block_access_list), Binary(0))
        block_access_list_hash = keccak(block_access_list_rlp)

    return compute_el_header_block_hash(
        spec,
        payload,
        transactions_trie_root,
        withdrawals_trie_root,
        parent_beacon_block_root,
        requests_hash,
        block_access_list_hash,
    )


def compute_el_block_hash(spec, payload, pre_state, execution_requests=None):
    parent_beacon_block_root = None
    requests_hash = None

    if is_post_deneb(spec):
        previous_block_header = pre_state.latest_block_header.copy()
        if previous_block_header.state_root == spec.Root():
            previous_block_header.state_root = pre_state.hash_tree_root()
        parent_beacon_block_root = previous_block_header.hash_tree_root()
    if is_post_electra(spec):
        if execution_requests is None:
            requests_list = []
        else:
            requests_list = spec.get_execution_requests_list(execution_requests)
        requests_hash = compute_requests_hash(requests_list)

    return compute_el_block_hash_with_new_fields(
        spec, payload, parent_beacon_block_root, requests_hash
    )


def compute_el_block_hash_for_block(spec, block):
    requests_hash = None

    if is_post_electra(spec):
        requests_list = spec.get_execution_requests_list(block.body.execution_requests)
        requests_hash = compute_requests_hash(requests_list)

    return compute_el_block_hash_with_new_fields(
        spec, block.body.execution_payload, block.parent_root, requests_hash
    )


def build_empty_post_gloas_execution_payload_bid(spec, state):
    if not is_post_gloas(spec):
        return
    parent_block_root = hash_tree_root(state.latest_block_header)
    kzg_list = spec.ProgressiveList[spec.KZGCommitment]()
    # Use self-build: builder_index is the same as the beacon proposer index
    builder_index = spec.BUILDER_INDEX_SELF_BUILD
    # Set block_hash to a different value than spec.Hash32(),
    # to distinguish it from the genesis block hash and have
    # is_parent_node_full correctly return False
    empty_payload_hash = spec.Hash32(b"\x01" + b"\x00" * 31)
    prev_randao = spec.get_randao_mix(state, spec.get_current_epoch(state))
    return spec.ExecutionPayloadBid(
        parent_block_hash=state.latest_block_hash,
        parent_block_root=parent_block_root,
        block_hash=empty_payload_hash,
        prev_randao=prev_randao,
        fee_recipient=spec.ExecutionAddress(),
        gas_limit=spec.uint64(0),
        builder_index=builder_index,
        slot=state.slot,
        value=spec.Gwei(0),
        blob_kzg_commitments=kzg_list,
        execution_requests_root=spec.hash_tree_root(spec.ExecutionRequests()),
    )


def sign_execution_payload_bid(spec, state, bid):
    assert is_post_gloas(spec)

    # For self-builds, use point at infinity signature as per spec
    if bid.builder_index == spec.BUILDER_INDEX_SELF_BUILD:
        signature = spec.G2_POINT_AT_INFINITY
    else:
        privkey = builder_privkeys[bid.builder_index]
        signature = spec.get_execution_payload_bid_signature(state, bid, privkey)

    return spec.SignedExecutionPayloadBid(
        message=bid,
        signature=signature,
    )


def build_empty_signed_execution_payload_bid(spec, state):
    if not is_post_gloas(spec):
        return
    message = build_empty_post_gloas_execution_payload_bid(spec, state)
    return sign_execution_payload_bid(spec, state, message)


def build_empty_execution_payload(
    spec, state, randao_mix=None, parent_payload=None, execution_requests=None
):
    """
    Assuming a pre-state of the same slot, build a valid ExecutionPayload without any transactions.
    """
    payload_bid = None
    if is_post_gloas(spec):
        payload_bid = state.latest_execution_payload_bid
    elif parent_payload is None:
        parent_payload = state.latest_execution_payload_header

    assert parent_payload is not None or payload_bid is not None

    if parent_payload is not None:
        parent_hash = parent_payload.block_hash
        gas_limit = parent_payload.gas_limit
    else:
        parent_hash = payload_bid.parent_block_hash
        gas_limit = payload_bid.gas_limit

    if randao_mix is None:
        if is_post_gloas(spec):
            randao_mix = payload_bid.prev_randao
        else:
            randao_mix = spec.get_randao_mix(state, spec.get_current_epoch(state))

    timestamp = spec.compute_time_at_slot(state, state.slot)

    payload = spec.ExecutionPayload(
        parent_hash=parent_hash,
        fee_recipient=spec.ExecutionAddress(),
        receipts_root=spec.Bytes32(
            bytes.fromhex("1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347")
        ),
        logs_bloom=spec.ByteVector[
            spec.BYTES_PER_LOGS_BLOOM
        ](),  # TODO: zeroed logs bloom for empty logs ok?
        prev_randao=randao_mix,
        gas_used=0,  # empty block, 0 gas
        gas_limit=gas_limit,
        timestamp=timestamp,
        extra_data=spec.ByteList[spec.MAX_EXTRA_DATA_BYTES](),
    )

    if parent_payload is not None:
        payload.state_root = parent_payload.state_root  # no changes to the state
        payload.block_number = parent_payload.block_number + 1
        payload.gas_limit = parent_payload.gas_limit  # retain same limit
        payload.base_fee_per_gas = parent_payload.base_fee_per_gas  # retain same base_fee

    if is_post_capella(spec):
        payload.withdrawals = get_expected_withdrawals(spec, state)
    if is_post_deneb(spec):
        payload.blob_gas_used = 0
        payload.excess_blob_gas = 0
    if is_post_gloas(spec):
        payload.block_access_list = spec.ByteList[spec.MAX_BYTES_PER_TRANSACTION]()
        payload.slot_number = state.slot

    payload.block_hash = compute_el_block_hash(spec, payload, state, execution_requests)

    return payload


def build_randomized_execution_payload(spec, state, rng):
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.fee_recipient = spec.ExecutionAddress(get_random_bytes_list(rng, 20))
    execution_payload.state_root = spec.Bytes32(get_random_bytes_list(rng, 32))
    execution_payload.receipts_root = spec.Bytes32(get_random_bytes_list(rng, 32))
    execution_payload.logs_bloom = spec.ByteVector[spec.BYTES_PER_LOGS_BLOOM](
        get_random_bytes_list(rng, spec.BYTES_PER_LOGS_BLOOM)
    )
    execution_payload.block_number = rng.randint(0, int(10e10))
    execution_payload.gas_limit = rng.randint(0, int(10e10))
    execution_payload.gas_used = rng.randint(0, int(10e10))
    extra_data_length = rng.randint(0, spec.MAX_EXTRA_DATA_BYTES)
    execution_payload.extra_data = spec.ByteList[spec.MAX_EXTRA_DATA_BYTES](
        get_random_bytes_list(rng, extra_data_length)
    )
    execution_payload.base_fee_per_gas = rng.randint(0, 2**256 - 1)

    num_transactions = rng.randint(0, 100)
    execution_payload.transactions = [get_random_tx(rng) for _ in range(num_transactions)]

    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    return execution_payload


def build_state_with_incomplete_transition(spec, state):
    if is_post_gloas(spec):
        # In Gloas, we need to set up the execution payload bid instead
        kzgs = spec.ProgressiveList[spec.KZGCommitment]()
        bid = spec.ExecutionPayloadBid(
            slot=state.slot,
            value=spec.Gwei(0),
            blob_kzg_commitments=kzgs,
        )
        state = build_state_with_execution_payload_bid(spec, state, bid)
    else:
        header = spec.ExecutionPayloadHeader()
        state = build_state_with_execution_payload_header(spec, state, header)
        if not is_post_capella(spec):
            assert not spec.is_merge_transition_complete(state)

    return state


def build_state_with_complete_transition(spec, state):
    pre_state_payload = build_empty_execution_payload(spec, state)
    if is_post_gloas(spec):
        payload_bid = get_execution_payload_bid(spec, state, pre_state_payload)
        state = build_state_with_execution_payload_bid(spec, state, payload_bid)
    else:
        payload_header = get_execution_payload_header(spec, pre_state_payload)
        state = build_state_with_execution_payload_header(spec, state, payload_header)
        if not is_post_capella(spec):
            assert spec.is_merge_transition_complete(state)

    return state


def build_state_with_execution_payload_header(spec, state, execution_payload_header):
    pre_state = state.copy()
    pre_state.latest_execution_payload_header = execution_payload_header
    return pre_state


def build_state_with_execution_payload_bid(spec, state, execution_payload_bid):
    pre_state = state.copy()
    pre_state.latest_execution_payload_bid = execution_payload_bid
    return pre_state


def sign_execution_payload_envelope(spec, state, signed_block, envelope):
    # Sign the envelope: self-builds use proposer key, external builds use builder key
    if envelope.builder_index == spec.BUILDER_INDEX_SELF_BUILD:
        privkey = privkeys[signed_block.message.proposer_index]
    else:
        privkey = builder_privkeys[envelope.builder_index]
    signature = spec.get_execution_payload_envelope_signature(state, envelope, privkey)

    return spec.SignedExecutionPayloadEnvelope(
        message=envelope,
        signature=signature,
    )


def build_signed_execution_payload_envelope(
    spec, state, block_root, signed_block, execution_requests=None
):
    # Get builder_index from the block's execution payload bid
    builder_index = signed_block.message.body.signed_execution_payload_bid.message.builder_index

    # Create execution payload with fields matching the bid's commitments
    payload = build_empty_execution_payload(spec, state)
    payload.block_hash = state.latest_execution_payload_bid.block_hash
    payload.gas_limit = state.latest_execution_payload_bid.gas_limit
    payload.parent_hash = state.latest_block_hash
    payload.withdrawals = state.payload_expected_withdrawals

    if execution_requests is None:
        execution_requests = spec.ExecutionRequests()

    # Create the execution payload envelope message
    envelope_message = spec.ExecutionPayloadEnvelope(
        payload=payload,
        execution_requests=execution_requests,
        builder_index=builder_index,
        beacon_block_root=block_root,
        parent_beacon_block_root=signed_block.message.parent_root,
    )

    return sign_execution_payload_envelope(spec, state, signed_block, envelope_message)


def compute_execution_payload_bid(spec, state, payload, execution_requests=None):
    assert is_post_gloas(spec)

    if execution_requests is None:
        execution_requests = spec.ExecutionRequests()

    parent_block_root = hash_tree_root(state.latest_block_header)
    kzg_list = spec.ProgressiveList[spec.KZGCommitment]()
    # Use self-build: builder_index is the same as the beacon proposer index
    builder_index = spec.BUILDER_INDEX_SELF_BUILD
    return spec.ExecutionPayloadBid(
        parent_block_hash=payload.parent_hash,
        parent_block_root=parent_block_root,
        block_hash=payload.block_hash,
        prev_randao=payload.prev_randao,
        fee_recipient=payload.fee_recipient,
        gas_limit=payload.gas_limit,
        builder_index=builder_index,
        slot=state.slot,
        value=spec.Gwei(0),
        blob_kzg_commitments=kzg_list,
        execution_requests_root=spec.hash_tree_root(execution_requests),
    )


def compute_and_sign_execution_payload_bid(spec, state, payload, execution_requests=None):
    assert is_post_gloas(spec)
    bid = compute_execution_payload_bid(spec, state, payload, execution_requests=execution_requests)
    return sign_execution_payload_bid(spec, state, bid)


def compute_and_sign_execution_payload_envelope(
    spec, state, block_root, signed_block, payload, execution_requests=None
):
    # Get builder_index from the block's execution payload bid
    builder_index = signed_block.message.body.signed_execution_payload_bid.message.builder_index

    if execution_requests is None:
        execution_requests = spec.ExecutionRequests()

    # Create the execution payload envelope message
    envelope = spec.ExecutionPayloadEnvelope(
        payload=payload,
        execution_requests=execution_requests,
        builder_index=builder_index,
        beacon_block_root=block_root,
        parent_beacon_block_root=signed_block.message.parent_root,
    )

    return sign_execution_payload_envelope(spec, state, signed_block, envelope)


def get_random_tx(rng):
    return get_random_bytes_list(rng, rng.randint(1, 1000))
