import random

from frozendict import frozendict

from eth_consensus_specs.test.context import (
    spec_configured_state_test,
    with_fulu_and_later,
)
from eth_consensus_specs.test.helpers.blob import get_block_with_blob, get_max_blob_count
from eth_consensus_specs.test.helpers.execution_payload import (
    build_state_with_complete_transition,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.forks import (
    is_post_gloas,
)
from eth_consensus_specs.test.helpers.gossip import (
    get_filename,
    get_seen,
    run_validate_gossip,
    wrap_genesis_block,
)
from eth_consensus_specs.test.helpers.state import (
    state_transition_and_sign_block,
)


@with_fulu_and_later
@spec_configured_state_test(
    {
        "BLOB_SCHEDULE": (frozendict({"EPOCH": 0, "MAX_BLOBS_PER_BLOCK": 12}),),
    },
    activate_at_genesis=True,
)
def test_gossip_beacon_block__valid_at_blob_parameters_limit(spec, state):
    """
    Test that a block carrying exactly ``get_blob_parameters().max_blobs_per_block``
    blob kzg commitments passes gossip validation under EIP-7892.
    """
    yield "topic", "meta", "beacon_block"

    state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    yield "state", anchor_state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    rng = random.Random(1234)
    max_blobs = get_max_blob_count(spec, state)
    # Sanity check: the BLOB_SCHEDULE override should be exercising the Fulu
    # code path (`get_blob_parameters`), not the Electra fallback. A client that
    # forgets EIP-7892 and uses MAX_BLOBS_PER_BLOCK_ELECTRA would reject this block.
    assert max_blobs > spec.config.MAX_BLOBS_PER_BLOCK_ELECTRA
    block, _, _, _ = get_block_with_blob(spec, state, rng=rng, blob_count=max_blobs)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield get_filename(signed_block), signed_block

    block_time_ms = spec.compute_time_at_slot_ms(state, signed_block.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    kwargs = {}
    if not is_post_gloas(spec):
        kwargs["block_payload_statuses"] = {}
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_beacon_block=signed_block,
        current_time_ms=block_time_ms + 500,
        **kwargs,
    )
    assert result == "valid"
    assert reason is None

    yield (
        "messages",
        "meta",
        [{"offset_ms": 500, "message": get_filename(signed_block), "expected": "valid"}],
    )
