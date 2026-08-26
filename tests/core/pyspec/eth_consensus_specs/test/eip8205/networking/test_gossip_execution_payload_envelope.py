from eth_consensus_specs.test.context import (
    spec_state_test,
    with_eip8205_and_later,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
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
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block


def _assert_envelope_preregistrations_gossip(spec, state, count, expected, reason=None):
    """
    Assert an envelope carrying ``count`` preregistration requests returns
    ``expected`` (with ``reason`` when rejected).

    The block's bid commits to the same requests (set before the state
    transition, so the block is valid and replayable) so that the requests-root
    check passes and the request-count checks are reached.
    """
    execution_requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests(*([spec.PreregistrationRequest()] * count))
    )

    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload"

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    block = build_empty_block_for_next_slot(spec, state)
    block.body.signed_execution_payload_bid.message.execution_requests_root = (
        execution_requests.hash_tree_root()
    )
    signed_block = state_transition_and_sign_block(spec, state, block)
    block_root = signed_block.message.hash_tree_root()
    store.blocks[block_root] = signed_block.message
    store.block_states[block_root] = state.copy()
    blocks = [signed_anchor, signed_block]

    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    signed_envelope = build_signed_execution_payload_envelope(
        spec, state, block_root, signed_block, execution_requests=execution_requests
    )
    yield get_filename(signed_envelope), signed_envelope

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)

    time_ms += 100
    result, reason_out = run_validate_gossip(
        spec, seen=seen, store=store, signed_execution_payload_envelope=signed_envelope
    )
    assert result == expected
    assert reason_out == reason

    message = {
        "current_time_ms": int(time_ms),
        "message": get_filename(signed_envelope),
        "expected": result,
    }
    if reason is not None:
        message["reason"] = reason
    yield "messages", "meta", [message]


@with_eip8205_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__valid_max_preregistration_requests(spec, state):
    """An envelope with the maximum number of preregistration requests is valid."""
    count = int(spec.MAX_PREREGISTRATION_REQUESTS_PER_PAYLOAD)
    yield from _assert_envelope_preregistrations_gossip(spec, state, count, "valid")


@with_eip8205_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_too_many_preregistration_requests(spec, state):
    """An envelope whose execution requests exceed the preregistration limit is rejected."""
    count = int(spec.MAX_PREREGISTRATION_REQUESTS_PER_PAYLOAD) + 1
    yield from _assert_envelope_preregistrations_gossip(
        spec, state, count, "reject", "too many validator preregistration requests"
    )
