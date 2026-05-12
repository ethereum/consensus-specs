import random

from eth_consensus_specs.test.context import (
    spec_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.blob import get_block_with_blob, get_max_blob_count
from eth_consensus_specs.test.helpers.block import sign_block
from eth_consensus_specs.test.helpers.constants import DENEB, ELECTRA
from eth_consensus_specs.test.helpers.execution_payload import (
    build_state_with_complete_transition,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import (
    get_filename,
    get_seen,
    run_validate_beacon_block_gossip,
    wrap_genesis_block,
)
from eth_consensus_specs.test.helpers.state import (
    state_transition_and_sign_block,
)


@with_phases([DENEB, ELECTRA])
@spec_state_test
def test_gossip_beacon_block__valid_with_blob_kzg_commitments(spec, state):
    """
    Test that a valid block carrying blob kzg commitments passes gossip validation.
    """
    yield "topic", "meta", "beacon_block"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    rng = random.Random(1234)
    block, _, _, _ = get_block_with_blob(spec, state, rng=rng, blob_count=1)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield get_filename(signed_block), signed_block

    block_time_ms = spec.compute_time_at_slot_ms(state, signed_block.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_block_gossip(
        spec, seen, store, state, signed_block, block_time_ms + 500
    )
    assert result == "valid"
    assert reason is None

    yield (
        "messages",
        "meta",
        [{"offset_ms": 500, "message": get_filename(signed_block), "expected": "valid"}],
    )


@with_phases([DENEB, ELECTRA])
@spec_state_test
def test_gossip_beacon_block__reject_too_many_kzg_commitments(spec, state):
    """
    Test that a block with more blob kzg commitments than MAX_BLOBS_PER_BLOCK is rejected.
    """
    yield "topic", "meta", "beacon_block"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    rng = random.Random(1234)
    block, _, _, _ = get_block_with_blob(
        spec, state, rng=rng, blob_count=get_max_blob_count(spec, state) + 1
    )
    signed_block = sign_block(spec, state, block, proposer_index=block.proposer_index)

    yield get_filename(signed_block), signed_block

    block_time_ms = spec.compute_time_at_slot_ms(state, block.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_block_gossip(
        spec, seen, store, state, signed_block, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "too many blob kzg commitments"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_block),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )
