from eth_consensus_specs.test.context import (
    spec_state_test_with_matching_config,
    with_heze_and_later,
)
from eth_consensus_specs.test.gloas.networking.test_gossip_execution_payload_bid import (
    _seed_bid_context,
)
from eth_consensus_specs.test.helpers.gloas.bid import (
    activate_builders,
    build_signed_bid,
    get_blocks_meta,
    record_head_payload,
    setup_store_advanced_for_bid,
)
from eth_consensus_specs.test.helpers.gossip import (
    get_filename,
    run_validate_gossip,
)
from eth_consensus_specs.test.helpers.inclusion_list import (
    get_sample_signed_inclusion_list,
    run_with_inclusion_list_store,
)


def _run_bid_inclusion_list_bits_scenario(
    spec, state, mark_includer, expected_result, expected_reason
):
    """
    Seed a timely inclusion list from the first member of the preceding slot's
    inclusion list committee, then validate a bid whose inclusion_list_bits
    does (``mark_includer=True``) or does not mark that member.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    finalized_checkpoint_meta = activate_builders(spec, state, store, blocks)
    head_payload = record_head_payload(spec, state, store, blocks)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", get_blocks_meta(blocks, head_payload)
    yield "finalized_checkpoint", "meta", finalized_checkpoint_meta

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []
    seen, common_fee, parent_gas_limit, proposal_slot, parent_block_hash, time_ms = yield from (
        _seed_bid_context(spec, state, store, head_payload, messages, time_ms)
    )

    inclusion_list_slot = spec.Slot(proposal_slot - 1)
    inclusion_list_committee = spec.get_inclusion_list_committee(state, inclusion_list_slot)
    includer_index = inclusion_list_committee[0]
    signed_il = get_sample_signed_inclusion_list(
        spec, store, state, slot=inclusion_list_slot, validator_index=includer_index
    )
    yield get_filename(signed_il), signed_il

    time_ms += 10
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
        }
    )

    # includer_index may occupy more than one committee position: the
    # committee wraps around (with repeats) whenever fewer than
    # INCLUSION_LIST_COMMITTEE_SIZE distinct validators are assigned to the
    # slot's beacon committees, so every matching position must be marked.
    bits = spec.InclusionListBits(
        data=[
            mark_includer and committee_member == includer_index
            for committee_member in inclusion_list_committee
        ]
    )
    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=spec.BuilderIndex(0),
        slot=proposal_slot,
        parent_block_hash=parent_block_hash,
        parent_block_root=parent_root,
        fee_recipient=common_fee,
        gas_limit=parent_gas_limit,
        value=spec.Gwei(1),
        inclusion_list_bits=bits,
    )
    yield get_filename(signed_bid), signed_bid

    # Gossip validation of the inclusion list only checks the message; the
    # bid's check reads the inclusion list store that on_inclusion_list
    # populates at the fork-choice layer, so record it there too.
    time_ms += 40
    bid_result = bid_reason = None

    def _record_and_validate_bid():
        nonlocal bid_result, bid_reason
        spec.process_inclusion_list(spec.get_inclusion_list_store(), signed_il, timely=True)
        bid_result, bid_reason = run_validate_gossip(
            spec,
            seen=seen,
            store=store,
            signed_execution_payload_bid=signed_bid,
            current_time_ms=time_ms,
        )

    run_with_inclusion_list_store(spec, _record_and_validate_bid)

    assert bid_result == expected_result
    assert bid_reason == expected_reason
    entry = {
        "current_time_ms": int(time_ms),
        "message": get_filename(signed_bid),
        "expected": bid_result,
    }
    if expected_reason is not None:
        entry["reason"] = expected_reason
    messages.append(entry)

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_execution_payload_bid__valid_inclusion_list_bits_inclusive(spec, state):
    """A bid whose inclusion_list_bits marks the observed timely inclusion list is valid."""
    yield from _run_bid_inclusion_list_bits_scenario(
        spec,
        state,
        mark_includer=True,
        expected_result="valid",
        expected_reason=None,
    )


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_execution_payload_bid__ignore_inclusion_list_bits_not_inclusive(spec, state):
    """A bid whose inclusion_list_bits omits the observed timely inclusion list is ignored."""
    yield from _run_bid_inclusion_list_bits_scenario(
        spec,
        state,
        mark_includer=False,
        expected_result="ignore",
        expected_reason="bid's inclusion list bits is not inclusive",
    )
