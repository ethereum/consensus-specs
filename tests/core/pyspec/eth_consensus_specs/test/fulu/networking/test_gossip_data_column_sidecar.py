from frozendict import frozendict

from eth_consensus_specs.test.context import (
    always_bls,
    spec_configured_state_test,
    spec_state_test,
    with_all_phases_from_to,
    with_fulu_and_later,
)
from eth_consensus_specs.test.helpers.blob import (
    get_block_with_blob_and_sidecars,
    get_max_blob_count,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.constants import FULU, GLOAS
from eth_consensus_specs.test.helpers.execution_payload import (
    build_state_with_complete_transition,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.forks import is_post_gloas
from eth_consensus_specs.test.helpers.gossip import (
    get_filename,
    get_seen,
    run_validate_gossip,
    wrap_genesis_block,
)
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.state import (
    state_transition_and_sign_block,
    transition_to,
)


def build_signed_block_and_sidecars(spec, state, blob_count=1):
    """
    Build a signed block carrying ``blob_count`` blobs (applying the state
    transition) and return its (signed_block, data_column_sidecars).
    """
    _, _, _, signed_block, sidecars, _ = get_block_with_blob_and_sidecars(
        spec, state, blob_count=blob_count
    )
    return signed_block, list(sidecars)


def setup_store_with_anchor(spec, state):
    """Return a store seeded with the genesis anchor block."""
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    return store, anchor_block


def correct_subnet(spec, sidecar):
    return spec.compute_subnet_for_data_column_sidecar(sidecar.index)


def resign_sidecar_header(spec, state, sidecar):
    proposer_index = sidecar.signed_block_header.message.proposer_index
    domain = spec.get_domain(
        state,
        spec.DOMAIN_BEACON_PROPOSER,
        spec.compute_epoch_at_slot(sidecar.signed_block_header.message.slot),
    )
    signing_root = spec.compute_signing_root(sidecar.signed_block_header.message, domain)
    sidecar.signed_block_header.signature = spec.bls.Sign(privkeys[proposer_index], signing_root)


@with_fulu_and_later
@spec_configured_state_test(
    {
        "BLOB_SCHEDULE": (frozendict({"EPOCH": 0, "MAX_BLOBS_PER_BLOCK": 12}),),
    },
    activate_at_genesis=True,
)
def test_gossip_data_column_sidecar__valid(spec, state):
    """Test that a valid data column sidecar passes gossip validation."""
    yield "topic", "meta", "data_column_sidecar"

    if not is_post_gloas(spec):
        state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor

    max_blobs = get_max_blob_count(spec, state)
    # Sanity check: the BLOB_SCHEDULE override should be exercising the Fulu
    # code path (`get_blob_parameters`), not the Electra fallback. A client that
    # forgets EIP-7892 and uses MAX_BLOBS_PER_BLOCK_ELECTRA would reject this sidecar.
    assert max_blobs > spec.config.MAX_BLOBS_PER_BLOCK_ELECTRA
    signed_block, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=max_blobs)
    sidecar = sidecars[0]

    blocks_meta = [{"block": get_filename(signed_anchor)}]
    if is_post_gloas(spec):
        # gloas's validator requires the sidecar's referenced block to be in store.
        block_root = signed_block.message.hash_tree_root()
        store.blocks[block_root] = signed_block.message
        store.block_states[block_root] = state.copy()
        yield get_filename(signed_block), signed_block
        blocks_meta.append({"block": get_filename(signed_block)})
    yield "blocks", "meta", blocks_meta

    yield get_filename(sidecar), sidecar

    sidecar_slot = sidecar.slot if is_post_gloas(spec) else sidecar.signed_block_header.message.slot
    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar_slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, sidecar)
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=sidecar,
        current_time_ms=block_time_ms + 500,
        subnet_id=subnet_id,
    )
    assert result == "valid"
    assert reason is None

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(sidecar),
                "expected": "valid",
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_data_column_sidecar__reject_index_out_of_range(spec, state):
    """Test that a data column sidecar with index >= NUMBER_OF_COLUMNS is rejected."""
    yield "topic", "meta", "data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    sidecar.index = spec.ColumnIndex(spec.NUMBER_OF_COLUMNS)

    yield get_filename(sidecar), sidecar

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = spec.SubnetID(0)
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=sidecar,
        current_time_ms=block_time_ms + 500,
        subnet_id=subnet_id,
    )
    assert result == "reject"
    assert reason == "invalid sidecar"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(sidecar),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_data_column_sidecar__reject_too_many_commitments(spec, state):
    """Test that a data column sidecar with too many commitments is rejected."""
    yield "topic", "meta", "data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    # Pad commitments past the blob limit. The verify_data_column_sidecar
    # check is independent of the inclusion proof, so we don't need a
    # consistent block here.
    extra = get_max_blob_count(spec, state) + 1 - len(sidecar.kzg_commitments)
    sidecar.kzg_commitments = list(sidecar.kzg_commitments) + [spec.KZGCommitment()] * extra

    yield get_filename(sidecar), sidecar

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, sidecar)
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=sidecar,
        current_time_ms=block_time_ms + 500,
        subnet_id=subnet_id,
    )
    assert result == "reject"
    assert reason == "invalid sidecar"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(sidecar),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_fulu_and_later
@spec_state_test
def test_gossip_data_column_sidecar__reject_wrong_subnet(spec, state):
    """Test that a data column sidecar on the wrong subnet is rejected."""
    yield "topic", "meta", "data_column_sidecar"

    if not is_post_gloas(spec):
        state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]

    yield get_filename(sidecar), sidecar

    sidecar_slot = sidecar.slot if is_post_gloas(spec) else sidecar.signed_block_header.message.slot
    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar_slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    expected_subnet = correct_subnet(spec, sidecar)
    wrong_subnet = spec.SubnetID(
        (int(expected_subnet) + 1) % spec.config.DATA_COLUMN_SIDECAR_SUBNET_COUNT
    )
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=sidecar,
        current_time_ms=block_time_ms + 500,
        subnet_id=wrong_subnet,
    )
    assert result == "reject"
    assert reason == "sidecar is for wrong subnet"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(wrong_subnet),
                "offset_ms": 500,
                "message": get_filename(sidecar),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_fulu_and_later
@spec_state_test
def test_gossip_data_column_sidecar__ignore_future_slot(spec, state):
    """Test that a data column sidecar from a future slot is ignored."""
    yield "topic", "meta", "data_column_sidecar"

    if not is_post_gloas(spec):
        state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]

    yield get_filename(sidecar), sidecar

    sidecar_slot = sidecar.slot if is_post_gloas(spec) else sidecar.signed_block_header.message.slot
    slot_time_ms = spec.compute_time_at_slot_ms(state, sidecar_slot)
    current_time_ms = slot_time_ms - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY - 1
    yield "current_time_ms", "meta", int(current_time_ms)

    subnet_id = correct_subnet(spec, sidecar)
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=sidecar,
        current_time_ms=current_time_ms,
        subnet_id=subnet_id,
    )
    assert result == "ignore"
    assert reason == "sidecar is from a future slot"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 0,
                "message": get_filename(sidecar),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_fulu_and_later
@spec_state_test
def test_gossip_data_column_sidecar__valid_slot_within_clock_disparity(spec, state):
    """Test that a data column sidecar at the future-slot boundary is valid."""
    yield "topic", "meta", "data_column_sidecar"

    if not is_post_gloas(spec):
        state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor

    signed_block, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]

    blocks_meta = [{"block": get_filename(signed_anchor)}]
    if is_post_gloas(spec):
        # gloas's validator requires the sidecar's referenced block to be in store.
        block_root = signed_block.message.hash_tree_root()
        store.blocks[block_root] = signed_block.message
        store.block_states[block_root] = state.copy()
        yield get_filename(signed_block), signed_block
        blocks_meta.append({"block": get_filename(signed_block)})
    yield "blocks", "meta", blocks_meta

    yield get_filename(sidecar), sidecar

    sidecar_slot = sidecar.slot if is_post_gloas(spec) else sidecar.signed_block_header.message.slot
    slot_time_ms = spec.compute_time_at_slot_ms(state, sidecar_slot)
    current_time_ms = slot_time_ms - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY
    yield "current_time_ms", "meta", int(current_time_ms)

    subnet_id = correct_subnet(spec, sidecar)
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=sidecar,
        current_time_ms=current_time_ms,
        subnet_id=subnet_id,
    )
    assert result == "valid"
    assert reason is None

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 0,
                "message": get_filename(sidecar),
                "expected": "valid",
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_data_column_sidecar__ignore_not_later_than_finalized_slot(spec, state):
    """Test that a data column sidecar at the latest finalized slot is ignored."""
    yield "topic", "meta", "data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    transition_to(spec, state, spec.Slot(spec.SLOTS_PER_EPOCH - 1))
    yield "state", state

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]

    block_header = sidecar.signed_block_header.message
    sidecar_epoch = spec.compute_epoch_at_slot(block_header.slot)
    store.finalized_checkpoint = spec.Checkpoint(
        epoch=sidecar_epoch,
        root=store.finalized_checkpoint.root,
    )
    yield (
        "finalized_checkpoint",
        "meta",
        {
            "epoch": int(sidecar_epoch),
            "block": get_filename(signed_anchor),
        },
    )

    yield get_filename(sidecar), sidecar

    block_time_ms = spec.compute_time_at_slot_ms(state, block_header.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, sidecar)
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=sidecar,
        current_time_ms=block_time_ms + 500,
        subnet_id=subnet_id,
    )
    assert result == "ignore"
    assert reason == "sidecar is not from a slot greater than the latest finalized slot"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(sidecar),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_data_column_sidecar__reject_proposer_index_out_of_range(spec, state):
    """Test that a data column sidecar with proposer_index out of range is rejected."""
    yield "topic", "meta", "data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    sidecar.signed_block_header.message.proposer_index = spec.ValidatorIndex(len(state.validators))

    yield get_filename(sidecar), sidecar

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, sidecar)
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=sidecar,
        current_time_ms=block_time_ms + 500,
        subnet_id=subnet_id,
    )
    assert result == "reject"
    assert reason == "proposer index out of range"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(sidecar),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
@always_bls
def test_gossip_data_column_sidecar__reject_invalid_proposer_signature(spec, state):
    """Test that a data column sidecar with an invalid block header signature is rejected."""
    yield "topic", "meta", "data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    sidecar.signed_block_header.signature = spec.BLSSignature(b"\x00" * 96)

    yield get_filename(sidecar), sidecar

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, sidecar)
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=sidecar,
        current_time_ms=block_time_ms + 500,
        subnet_id=subnet_id,
    )
    assert result == "reject"
    assert reason == "invalid proposer signature on sidecar block header"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(sidecar),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_data_column_sidecar__ignore_parent_not_seen(spec, state):
    """Test that a data column sidecar whose parent is unknown to the store is ignored."""
    yield "topic", "meta", "data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]

    # Modify parent_root to something unknown to the store
    sidecar.signed_block_header.message.parent_root = b"\x12" * 32
    resign_sidecar_header(spec, state, sidecar)

    yield get_filename(sidecar), sidecar

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, sidecar)
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=sidecar,
        current_time_ms=block_time_ms + 500,
        subnet_id=subnet_id,
    )
    assert result == "ignore"
    assert reason == "sidecar's parent has not been seen"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(sidecar),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_data_column_sidecar__reject_parent_failed_validation(spec, state):
    """Test that a data column sidecar whose parent failed validation is rejected."""
    yield "topic", "meta", "data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor

    # Build the failed parent on a separate state copy so the yielded anchor state stays
    # at slot 0 (its `latest_block_header` points at the genesis-equivalent anchor, not at
    # `signed_parent`)
    parent_state = state.copy()
    parent_block = build_empty_block_for_next_slot(spec, parent_state)
    signed_parent = state_transition_and_sign_block(spec, parent_state, parent_block)

    yield get_filename(signed_parent), signed_parent

    # Add the parent block to store.blocks but not store.block_states, matching
    # the reference-test encoding of a failed block.
    store.blocks[signed_parent.message.hash_tree_root()] = signed_parent.message

    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_parent), "failed": True},
        ],
    )

    _, sidecars = build_signed_block_and_sidecars(spec, parent_state.copy(), blob_count=1)
    sidecar = sidecars[0]

    yield get_filename(sidecar), sidecar

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, sidecar)
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=sidecar,
        current_time_ms=block_time_ms + 500,
        subnet_id=subnet_id,
    )
    assert result == "reject"
    assert reason == "sidecar's parent failed validation"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(sidecar),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_data_column_sidecar__reject_slot_not_higher_than_parent(spec, state):
    """
    Test that a data column sidecar whose block_header.slot is not strictly greater
    than its parent's slot is rejected.
    """
    yield "topic", "meta", "data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor

    parent_state = state.copy()
    parent_block = build_empty_block_for_next_slot(spec, parent_state)
    signed_parent = state_transition_and_sign_block(spec, parent_state, parent_block)

    yield get_filename(signed_parent), signed_parent
    parent_root = signed_parent.message.hash_tree_root()
    store.blocks[parent_root] = signed_parent.message
    store.block_states[parent_root] = parent_state.copy()
    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_parent)},
        ],
    )

    _, sidecars = build_signed_block_and_sidecars(spec, parent_state.copy(), blob_count=1)
    sidecar = sidecars[0]
    sidecar.signed_block_header.message.slot = signed_parent.message.slot
    resign_sidecar_header(spec, parent_state, sidecar)

    yield get_filename(sidecar), sidecar

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, sidecar)
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=sidecar,
        current_time_ms=block_time_ms + 500,
        subnet_id=subnet_id,
    )
    assert result == "reject"
    assert reason == "sidecar is not from a higher slot than its parent"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(sidecar),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_data_column_sidecar__reject_non_ancestor_finalized_checkpoint(spec, state):
    """Test that a data column sidecar is rejected if the finalized checkpoint is not an ancestor."""
    yield "topic", "meta", "data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]

    fake_finalized_root = spec.Root(b"\xab" * 32)
    store.finalized_checkpoint = spec.Checkpoint(
        epoch=spec.Epoch(0),
        root=fake_finalized_root,
    )

    yield "finalized_checkpoint", "meta", {"epoch": 0, "root": "0x" + "ab" * 32}
    yield get_filename(sidecar), sidecar

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, sidecar)
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=sidecar,
        current_time_ms=block_time_ms + 500,
        subnet_id=subnet_id,
    )
    assert result == "reject"
    assert reason == "finalized checkpoint is not an ancestor of sidecar's block"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(sidecar),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_data_column_sidecar__reject_invalid_inclusion_proof(spec, state):
    """Test that a data column sidecar with a broken inclusion proof is rejected."""
    yield "topic", "meta", "data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    # Corrupt the inclusion proof.
    sidecar.kzg_commitments_inclusion_proof = spec.compute_merkle_proof(spec.BeaconBlockBody(), 0)

    yield get_filename(sidecar), sidecar

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, sidecar)
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=sidecar,
        current_time_ms=block_time_ms + 500,
        subnet_id=subnet_id,
    )
    assert result == "reject"
    assert reason == "invalid sidecar inclusion proof"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(sidecar),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_fulu_and_later
@spec_state_test
def test_gossip_data_column_sidecar__reject_invalid_kzg_proofs(spec, state):
    """Test that a data column sidecar with invalid KZG cell proofs is rejected."""
    yield "topic", "meta", "data_column_sidecar"

    if not is_post_gloas(spec):
        state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor

    signed_block, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    # Corrupt every KZG proof to the point at infinity, which won't verify
    # against the real commitments.
    bad_proof = spec.KZGProof(b"\xc0" + b"\x00" * 47)
    sidecar.kzg_proofs = [bad_proof for _ in sidecar.kzg_proofs]

    blocks_meta = [{"block": get_filename(signed_anchor)}]
    if is_post_gloas(spec):
        # gloas's validator requires the sidecar's referenced block to be in store.
        block_root = signed_block.message.hash_tree_root()
        store.blocks[block_root] = signed_block.message
        store.block_states[block_root] = state.copy()
        yield get_filename(signed_block), signed_block
        blocks_meta.append({"block": get_filename(signed_block)})
    yield "blocks", "meta", blocks_meta

    yield get_filename(sidecar), sidecar

    sidecar_slot = sidecar.slot if is_post_gloas(spec) else sidecar.signed_block_header.message.slot
    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar_slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, sidecar)
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=sidecar,
        current_time_ms=block_time_ms + 500,
        subnet_id=subnet_id,
    )
    assert result == "reject"
    assert reason == "invalid sidecar kzg proofs"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(sidecar),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_data_column_sidecar__ignore_already_seen(spec, state):
    """
    Test that a duplicate data column sidecar for the same
    (slot, proposer_index, index) tuple is ignored.
    """
    yield "topic", "meta", "data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    messages = []
    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]

    yield get_filename(sidecar), sidecar

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, sidecar)

    # First delivery passes.
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=sidecar,
        current_time_ms=block_time_ms + 500,
        subnet_id=subnet_id,
    )
    assert result == "valid"
    messages.append(
        {
            "subnet_id": int(subnet_id),
            "offset_ms": 500,
            "message": get_filename(sidecar),
            "expected": "valid",
        }
    )

    # Second delivery of the same sidecar is ignored.
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=sidecar,
        current_time_ms=block_time_ms + 600,
        subnet_id=subnet_id,
    )
    assert result == "ignore"
    assert reason == "already seen sidecar from this proposer for this slot and index"
    messages.append(
        {
            "subnet_id": int(subnet_id),
            "offset_ms": 600,
            "message": get_filename(sidecar),
            "expected": "ignore",
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_data_column_sidecar__reject_wrong_proposer_index(spec, state):
    """Test that a data column sidecar with the wrong proposer_index is rejected."""
    yield "topic", "meta", "data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]

    correct_proposer = sidecar.signed_block_header.message.proposer_index
    wrong_proposer = spec.ValidatorIndex((int(correct_proposer) + 1) % len(state.validators))
    sidecar.signed_block_header.message.proposer_index = wrong_proposer
    resign_sidecar_header(spec, state, sidecar)

    yield get_filename(sidecar), sidecar

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, sidecar)
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=sidecar,
        current_time_ms=block_time_ms + 500,
        subnet_id=subnet_id,
    )
    assert result == "reject"
    assert reason == "sidecar proposer_index does not match expected proposer"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(sidecar),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )
