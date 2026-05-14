from eth_consensus_specs.test.context import (
    spec_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.attestations import (
    get_valid_attestation,
)
from eth_consensus_specs.test.helpers.constants import DENEB, ELECTRA
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import get_filename, get_seen, wrap_genesis_block
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.state import transition_to


def create_signed_aggregate_and_proof(spec, state, attestation):
    committee = spec.get_beacon_committee(state, attestation.data.slot, attestation.data.index)

    aggregator_index = None
    for index in committee:
        privkey = privkeys[index]
        selection_proof = spec.get_slot_signature(state, attestation.data.slot, privkey)
        if spec.is_aggregator(
            state, attestation.data.slot, attestation.data.index, selection_proof
        ):
            aggregator_index = index
            break

    if aggregator_index is None:
        aggregator_index = committee[0]

    privkey = privkeys[aggregator_index]
    aggregate_and_proof = spec.get_aggregate_and_proof(
        state, aggregator_index, attestation, privkey
    )
    signature = spec.get_aggregate_and_proof_signature(state, aggregate_and_proof, privkey)

    return spec.SignedAggregateAndProof(message=aggregate_and_proof, signature=signature)


def run_validate_beacon_aggregate_and_proof_gossip(
    spec, seen, store, state, signed_aggregate_and_proof, current_time_ms
):
    try:
        spec.validate_beacon_aggregate_and_proof_gossip(
            seen, store, state, signed_aggregate_and_proof, current_time_ms
        )
        return "valid", None
    except spec.GossipIgnore as e:
        return "ignore", str(e)
    except spec.GossipReject as e:
        return "reject", str(e)


def build_signed_aggregate_and_proof(spec, state, beacon_block_root):
    attestation = get_valid_attestation(
        spec, state, signed=True, beacon_block_root=beacon_block_root
    )
    return create_signed_aggregate_and_proof(spec, state, attestation)


def prepare_signed_aggregate_and_proof(spec, state, slot):
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    transition_to(spec, state, slot)
    signed_agg = build_signed_aggregate_and_proof(spec, state, anchor_root)

    return store, signed_anchor, signed_agg


def epoch_window_open_time(spec, state, attestation_epoch):
    return (
        spec.compute_time_at_slot_ms(state, spec.compute_start_slot_at_epoch(attestation_epoch))
        - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY
    )


def epoch_window_close_time(spec, state, attestation_epoch):
    return (
        spec.compute_time_at_slot_ms(state, spec.compute_start_slot_at_epoch(attestation_epoch + 2))
        + spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY
    )


def build_message(signed_agg, current_time_ms, offset_ms, expected, reason=None):
    message = {
        "offset_ms": int(offset_ms),
        "message": get_filename(signed_agg),
        "expected": expected,
    }
    if reason is not None:
        message["reason"] = reason
    return message


@with_phases([DENEB, ELECTRA])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__accepts_one_millisecond_before_slot_start(spec, state):
    """Test that an aggregate is accepted one millisecond before its slot starts."""
    yield "topic", "meta", "beacon_aggregate_and_proof"

    store, signed_anchor, signed_agg = prepare_signed_aggregate_and_proof(spec, state, spec.Slot(1))
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    yield "state", state
    yield get_filename(signed_agg), signed_agg

    current_time_ms = (
        spec.compute_time_at_slot_ms(state, signed_agg.message.aggregate.data.slot) - 1
    )
    yield "current_time_ms", "meta", int(current_time_ms)

    seen = get_seen(spec)
    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, current_time_ms
    )
    assert result == "valid"
    assert reason is None

    yield "messages", "meta", [build_message(signed_agg, current_time_ms, 0, "valid")]


@with_phases([DENEB, ELECTRA])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__accepts_at_slot_start(spec, state):
    """Test that an aggregate is accepted exactly at its slot start."""
    yield "topic", "meta", "beacon_aggregate_and_proof"

    store, signed_anchor, signed_agg = prepare_signed_aggregate_and_proof(spec, state, spec.Slot(1))
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    yield "state", state
    yield get_filename(signed_agg), signed_agg

    current_time_ms = spec.compute_time_at_slot_ms(state, signed_agg.message.aggregate.data.slot)
    yield "current_time_ms", "meta", int(current_time_ms)

    seen = get_seen(spec)
    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, current_time_ms
    )
    assert result == "valid"
    assert reason is None

    yield "messages", "meta", [build_message(signed_agg, current_time_ms, 0, "valid")]


@with_phases([DENEB, ELECTRA])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__ignores_first_slot_before_epoch_window_opens(
    spec, state
):
    """
    Test that a first-slot aggregate is ignored just before the Deneb epoch
    window opens, with the future-slot check taking precedence.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"

    attestation_epoch = spec.Epoch(2)
    store, signed_anchor, signed_agg = prepare_signed_aggregate_and_proof(
        spec, state, spec.compute_start_slot_at_epoch(attestation_epoch)
    )
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    yield "state", state
    yield get_filename(signed_agg), signed_agg

    current_time_ms = epoch_window_open_time(spec, state, attestation_epoch) - 1
    yield "current_time_ms", "meta", int(current_time_ms)

    seen = get_seen(spec)
    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, current_time_ms
    )
    assert result == "ignore"
    assert reason == "aggregate slot is from a future slot"

    yield "messages", "meta", [build_message(signed_agg, current_time_ms, 0, "ignore", reason)]


@with_phases([DENEB, ELECTRA])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__accepts_first_slot_when_epoch_window_opens(spec, state):
    """Test that a first-slot aggregate is accepted when the Deneb epoch window opens."""
    yield "topic", "meta", "beacon_aggregate_and_proof"

    attestation_epoch = spec.Epoch(2)
    store, signed_anchor, signed_agg = prepare_signed_aggregate_and_proof(
        spec, state, spec.compute_start_slot_at_epoch(attestation_epoch)
    )
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    yield "state", state
    yield get_filename(signed_agg), signed_agg

    current_time_ms = epoch_window_open_time(spec, state, attestation_epoch)
    yield "current_time_ms", "meta", int(current_time_ms)

    seen = get_seen(spec)
    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, current_time_ms
    )
    assert result == "valid"
    assert reason is None

    yield "messages", "meta", [build_message(signed_agg, current_time_ms, 0, "valid")]


@with_phases([DENEB, ELECTRA])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__accepts_first_slot_when_epoch_window_closes(
    spec, state
):
    """Test that a first-slot aggregate is accepted at the last valid Deneb epoch time."""
    yield "topic", "meta", "beacon_aggregate_and_proof"

    attestation_epoch = spec.Epoch(2)
    store, signed_anchor, signed_agg = prepare_signed_aggregate_and_proof(
        spec, state, spec.compute_start_slot_at_epoch(attestation_epoch)
    )
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    yield "state", state
    yield get_filename(signed_agg), signed_agg

    current_time_ms = epoch_window_close_time(spec, state, attestation_epoch)
    yield "current_time_ms", "meta", int(current_time_ms)

    seen = get_seen(spec)
    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, current_time_ms
    )
    assert result == "valid"
    assert reason is None

    yield "messages", "meta", [build_message(signed_agg, current_time_ms, 0, "valid")]


@with_phases([DENEB, ELECTRA])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__ignores_first_slot_after_epoch_window_closes(
    spec, state
):
    """Test that a first-slot aggregate is ignored after the Deneb epoch window closes."""
    yield "topic", "meta", "beacon_aggregate_and_proof"

    attestation_epoch = spec.Epoch(2)
    store, signed_anchor, signed_agg = prepare_signed_aggregate_and_proof(
        spec, state, spec.compute_start_slot_at_epoch(attestation_epoch)
    )
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    yield "state", state
    yield get_filename(signed_agg), signed_agg

    current_time_ms = epoch_window_close_time(spec, state, attestation_epoch) + 1
    yield "current_time_ms", "meta", int(current_time_ms)

    seen = get_seen(spec)
    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, current_time_ms
    )
    assert result == "ignore"
    assert reason == "aggregate epoch is not previous or current epoch"

    yield "messages", "meta", [build_message(signed_agg, current_time_ms, 0, "ignore", reason)]


@with_phases([DENEB, ELECTRA])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__accepts_last_slot_one_millisecond_before_slot_start(
    spec, state
):
    """
    Test that a last-slot aggregate is accepted one millisecond before its slot
    starts.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"

    attestation_epoch = spec.Epoch(2)
    attestation_slot = (
        spec.compute_start_slot_at_epoch(attestation_epoch) + spec.SLOTS_PER_EPOCH - 1
    )
    store, signed_anchor, signed_agg = prepare_signed_aggregate_and_proof(
        spec, state, attestation_slot
    )
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    yield "state", state
    yield get_filename(signed_agg), signed_agg

    current_time_ms = (
        spec.compute_time_at_slot_ms(state, signed_agg.message.aggregate.data.slot) - 1
    )
    yield "current_time_ms", "meta", int(current_time_ms)

    seen = get_seen(spec)
    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, current_time_ms
    )
    assert result == "valid"
    assert reason is None

    yield "messages", "meta", [build_message(signed_agg, current_time_ms, 0, "valid")]


@with_phases([DENEB, ELECTRA])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__accepts_last_slot_at_slot_start(spec, state):
    """Test that a last-slot aggregate is accepted exactly at its slot start."""
    yield "topic", "meta", "beacon_aggregate_and_proof"

    attestation_epoch = spec.Epoch(2)
    attestation_slot = (
        spec.compute_start_slot_at_epoch(attestation_epoch) + spec.SLOTS_PER_EPOCH - 1
    )
    store, signed_anchor, signed_agg = prepare_signed_aggregate_and_proof(
        spec, state, attestation_slot
    )
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    yield "state", state
    yield get_filename(signed_agg), signed_agg

    current_time_ms = spec.compute_time_at_slot_ms(state, signed_agg.message.aggregate.data.slot)
    yield "current_time_ms", "meta", int(current_time_ms)

    seen = get_seen(spec)
    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, current_time_ms
    )
    assert result == "valid"
    assert reason is None

    yield "messages", "meta", [build_message(signed_agg, current_time_ms, 0, "valid")]


@with_phases([DENEB, ELECTRA])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__accepts_last_slot_when_epoch_window_closes(spec, state):
    """Test that a last-slot aggregate is accepted at the last valid Deneb epoch time."""
    yield "topic", "meta", "beacon_aggregate_and_proof"

    attestation_epoch = spec.Epoch(2)
    attestation_slot = (
        spec.compute_start_slot_at_epoch(attestation_epoch) + spec.SLOTS_PER_EPOCH - 1
    )
    store, signed_anchor, signed_agg = prepare_signed_aggregate_and_proof(
        spec, state, attestation_slot
    )
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    yield "state", state
    yield get_filename(signed_agg), signed_agg

    current_time_ms = epoch_window_close_time(spec, state, attestation_epoch)
    yield "current_time_ms", "meta", int(current_time_ms)

    seen = get_seen(spec)
    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, current_time_ms
    )
    assert result == "valid"
    assert reason is None

    yield "messages", "meta", [build_message(signed_agg, current_time_ms, 0, "valid")]


@with_phases([DENEB, ELECTRA])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__ignores_last_slot_after_epoch_window_closes(
    spec, state
):
    """Test that a last-slot aggregate is ignored after the Deneb epoch window closes."""
    yield "topic", "meta", "beacon_aggregate_and_proof"

    attestation_epoch = spec.Epoch(2)
    attestation_slot = (
        spec.compute_start_slot_at_epoch(attestation_epoch) + spec.SLOTS_PER_EPOCH - 1
    )
    store, signed_anchor, signed_agg = prepare_signed_aggregate_and_proof(
        spec, state, attestation_slot
    )
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    yield "state", state
    yield get_filename(signed_agg), signed_agg

    current_time_ms = epoch_window_close_time(spec, state, attestation_epoch) + 1
    yield "current_time_ms", "meta", int(current_time_ms)

    seen = get_seen(spec)
    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, current_time_ms
    )
    assert result == "ignore"
    assert reason == "aggregate epoch is not previous or current epoch"

    yield "messages", "meta", [build_message(signed_agg, current_time_ms, 0, "ignore", reason)]
