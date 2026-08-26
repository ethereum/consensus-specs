from eth_consensus_specs.test.context import (
    spec_state_test,
    with_eip8205_and_later,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block_for_next_slot,
    sign_block,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import (
    get_filename,
    get_seen,
    run_validate_gossip,
    wrap_genesis_block,
)


def _assert_parent_preregistrations_gossip(spec, state, count, expected, reason=None):
    """
    Build a block on the genesis anchor with an empty parent, carrying ``count``
    parent preregistration requests, and assert gossip validation returns
    ``expected`` (with ``reason`` when rejected).

    The empty-parent base is otherwise valid, so it serves both the limit (valid)
    and limit+1 (reject) count tests: only the request count differs.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "beacon_block"

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield "state", anchor_state
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    seen = get_seen(spec)
    block = build_empty_block_for_next_slot(spec, state)
    # Treat the parent as empty so no parent payload envelope is required for validity
    block.body.signed_execution_payload_bid.message.parent_block_hash = state.latest_block_hash
    block.body.parent_execution_requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests(
            data=([spec.PreregistrationRequest()] * count)
        )
    )
    signed_block = sign_block(spec, state, block, proposer_index=block.proposer_index)
    yield get_filename(signed_block), signed_block

    time_ms = spec.compute_time_at_slot_ms(store, signed_block.message.slot)
    yield "current_time_ms", "meta", int(time_ms)

    time_ms += 500
    result, reason_out = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_beacon_block=signed_block,
        current_time_ms=time_ms,
    )
    assert result == expected
    assert reason_out == reason

    message = {
        "current_time_ms": int(time_ms),
        "message": get_filename(signed_block),
        "expected": result,
    }
    if reason is not None:
        message["reason"] = reason
    yield "messages", "meta", [message]


@with_eip8205_and_later
@spec_state_test
def test_gossip_beacon_block__valid_max_parent_preregistration_requests(spec, state):
    """A block with the maximum number of parent preregistration requests is valid."""
    count = int(spec.MAX_PREREGISTRATION_REQUESTS_PER_PAYLOAD)
    yield from _assert_parent_preregistrations_gossip(spec, state, count, "valid")


@with_eip8205_and_later
@spec_state_test
def test_gossip_beacon_block__reject_too_many_parent_preregistration_requests(spec, state):
    """A block whose parent execution requests exceed the preregistration limit is rejected."""
    count = int(spec.MAX_PREREGISTRATION_REQUESTS_PER_PAYLOAD) + 1
    yield from _assert_parent_preregistrations_gossip(
        spec, state, count, "reject", "too many validator preregistration requests"
    )
