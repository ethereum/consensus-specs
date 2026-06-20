from eth_consensus_specs.test.context import expect_assertion_error
from eth_consensus_specs.test.helpers.keys import builder_privkeys


def run_execution_payload_bid_processing(spec, state, block, valid=True):
    """
    Run ``process_execution_payload_bid``, yielding:
    - pre-state ('pre')
    - execution payload bid ('execution_payload_bid')
    - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    signed_bid = block.body.signed_execution_payload_bid
    yield "pre", state
    yield "execution_payload_bid", signed_bid

    if not valid:
        expect_assertion_error(lambda: spec.process_execution_payload_bid(state, signed_bid))
        yield "post", None
        return

    spec.process_execution_payload_bid(state, signed_bid)
    yield "post", state


def prepare_signed_execution_payload_bid(
    spec,
    state,
    builder_index=None,
    value=None,
    slot=None,
    parent_block_hash=None,
    parent_block_root=None,
    fee_recipient=None,
    gas_limit=None,
    block_hash=None,
    blob_kzg_commitments=None,
    prev_randao=None,
    valid_signature=True,
    valid_amount=True,
):
    """
    Helper to create a signed execution payload bid with customizable parameters.
    If slot is None, the current state slot will be used.
    """
    if slot is None:
        slot = state.slot
    assert slot >= state.slot
    spec.process_slots(state, slot)

    if builder_index is None:
        builder_index = spec.BUILDER_INDEX_SELF_BUILD

    if parent_block_hash is None:
        parent_block_hash = state.latest_block_hash

    if parent_block_root is None:
        parent_block_root = state.latest_block_header.hash_tree_root()

    if fee_recipient is None:
        fee_recipient = spec.ExecutionAddress()

    if gas_limit is None:
        gas_limit = spec.uint64(30000000)

    if block_hash is None:
        block_hash = spec.Hash32()

    if value is None:
        value = spec.Gwei(0)

    # Validation: if builder index equals proposer index, value must be 0
    if valid_amount and builder_index == spec.BUILDER_INDEX_SELF_BUILD and value != 0:
        raise ValueError(
            "Self-builder (builder_index == BUILDER_INDEX_SELF_BUILD) must use zero value"
        )

    if blob_kzg_commitments is None:
        blob_kzg_commitments = spec.ProgressiveList[spec.KZGCommitment]()

    if prev_randao is None:
        prev_randao = spec.get_randao_mix(state, spec.get_current_epoch(state))

    bid_kwargs = {
        "parent_block_hash": parent_block_hash,
        "parent_block_root": parent_block_root,
        "block_hash": block_hash,
        "prev_randao": prev_randao,
        "fee_recipient": fee_recipient,
        "gas_limit": gas_limit,
        "builder_index": builder_index,
        "slot": slot,
        "value": value,
        "blob_kzg_commitments": blob_kzg_commitments,
    }
    bid = spec.ExecutionPayloadBid(**bid_kwargs)

    if valid_signature:
        # Check if this is a self-build case
        if builder_index == spec.BUILDER_INDEX_SELF_BUILD:
            # Self-builds must use G2_POINT_AT_INFINITY
            signature = spec.bls.G2_POINT_AT_INFINITY
        else:
            # External builders use real signatures
            privkey = builder_privkeys[builder_index]
            signature = spec.get_execution_payload_bid_signature(state, bid, privkey)
    else:
        # Invalid signature
        signature = spec.BLSSignature()

    return spec.SignedExecutionPayloadBid(
        message=bid,
        signature=signature,
    )
