from eth_consensus_specs.test.context import (
    spec_state_test,
    with_heze_and_later,
)
from eth_consensus_specs.test.gloas.networking.test_gossip_execution_payload_envelope import (
    setup_store_with_block,
)
from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
    sign_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.gossip import (
    get_filename,
    get_seen,
    run_validate_gossip,
)


@with_heze_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_inclusion_claims_root_mismatch(spec, state):
    """An envelope whose inclusion claims root does not match the bid's is rejected."""
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload"

    store, blocks, signed_block, block_root = setup_store_with_block(spec, state)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    # The bid commits to an empty claim list, so any claim changes the root.
    envelope = build_signed_execution_payload_envelope(
        spec, state, block_root, signed_block
    ).message
    envelope.inclusion_claims = spec.InclusionListClaims(
        data=[spec.InclusionListClaim(transaction_hash=spec.Bytes32(b"\x11" * 32))]
    )
    signed_envelope = sign_execution_payload_envelope(spec, state, signed_block, envelope)
    yield get_filename(signed_envelope), signed_envelope

    time_ms = spec.compute_time_at_slot_ms(store.genesis_time_ms, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "reject"
    assert reason == "envelope's inclusion claims root does not match the bid's"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_envelope),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages
