from eth_consensus_specs.test.context import (
    spec_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.attestations import (
    get_valid_attestation,
)
from eth_consensus_specs.test.helpers.constants import DENEB
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import get_filename, get_seen, wrap_genesis_block
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.state import transition_to


def get_correct_subnet_for_attestation(spec, state, attestation):
    committees_per_slot = spec.get_committee_count_per_slot(state, attestation.data.target.epoch)
    return spec.compute_subnet_for_attestation(
        committees_per_slot, attestation.data.slot, attestation.data.index
    )


def run_validate_beacon_attestation_gossip(
    spec, seen, store, state, attestation, subnet_id, current_time_ms
):
    try:
        spec.validate_beacon_attestation_gossip(
            seen, store, state, attestation, subnet_id, current_time_ms
        )
        return "valid", None
    except spec.GossipIgnore as e:
        return "ignore", str(e)
    except spec.GossipReject as e:
        return "reject", str(e)


def build_unaggregated_attestation(spec, state, beacon_block_root):
    attestation = get_valid_attestation(
        spec, state, signed=False, beacon_block_root=beacon_block_root
    )
    committee = spec.get_beacon_committee(state, attestation.data.slot, attestation.data.index)
    single_bit = [False] * len(committee)
    single_bit[0] = True
    attestation.aggregation_bits = spec.Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE](*single_bit)
    attestation.signature = spec.get_attestation_signature(
        state, attestation.data, privkeys[committee[0]]
    )
    return attestation


def prepare_attestation(spec, state, slot):
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    transition_to(spec, state, slot)
    attestation = build_unaggregated_attestation(spec, state, anchor_root)

    return store, signed_anchor, attestation


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


def build_message(attestation, subnet_id, current_time_ms, offset_ms, expected, reason=None):
    message = {
        "subnet_id": int(subnet_id),
        "offset_ms": int(offset_ms),
        "message": get_filename(attestation),
        "expected": expected,
    }
    if reason is not None:
        message["reason"] = reason
    return message


@with_phases([DENEB])
@spec_state_test
def test_gossip_beacon_attestation__accepts_one_millisecond_before_slot_start(spec, state):
    """Test that an attestation is accepted one millisecond before its slot starts."""
    yield "topic", "meta", "beacon_attestation"

    store, signed_anchor, attestation = prepare_attestation(spec, state, spec.Slot(1))
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    yield "state", state
    yield get_filename(attestation), attestation

    current_time_ms = spec.compute_time_at_slot_ms(state, attestation.data.slot) - 1
    yield "current_time_ms", "meta", int(current_time_ms)

    subnet_id = get_correct_subnet_for_attestation(spec, state, attestation)
    seen = get_seen(spec)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, current_time_ms
    )
    assert result == "valid"
    assert reason is None

    yield "messages", "meta", [build_message(attestation, subnet_id, current_time_ms, 0, "valid")]


@with_phases([DENEB])
@spec_state_test
def test_gossip_beacon_attestation__accepts_at_slot_start(spec, state):
    """Test that an attestation is accepted exactly at its slot start."""
    yield "topic", "meta", "beacon_attestation"

    store, signed_anchor, attestation = prepare_attestation(spec, state, spec.Slot(1))
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    yield "state", state
    yield get_filename(attestation), attestation

    current_time_ms = spec.compute_time_at_slot_ms(state, attestation.data.slot)
    yield "current_time_ms", "meta", int(current_time_ms)

    subnet_id = get_correct_subnet_for_attestation(spec, state, attestation)
    seen = get_seen(spec)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, current_time_ms
    )
    assert result == "valid"
    assert reason is None

    yield "messages", "meta", [build_message(attestation, subnet_id, current_time_ms, 0, "valid")]


@with_phases([DENEB])
@spec_state_test
def test_gossip_beacon_attestation__ignores_first_slot_before_epoch_window_opens(spec, state):
    """
    Test that a first-slot attestation is ignored just before the Deneb epoch
    window opens, with the future-slot check taking precedence.
    """
    yield "topic", "meta", "beacon_attestation"

    attestation_epoch = spec.Epoch(2)
    store, signed_anchor, attestation = prepare_attestation(
        spec, state, spec.compute_start_slot_at_epoch(attestation_epoch)
    )
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    yield "state", state
    yield get_filename(attestation), attestation

    current_time_ms = epoch_window_open_time(spec, state, attestation_epoch) - 1
    yield "current_time_ms", "meta", int(current_time_ms)

    subnet_id = get_correct_subnet_for_attestation(spec, state, attestation)
    seen = get_seen(spec)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, current_time_ms
    )
    assert result == "ignore"
    assert reason == "attestation slot is from a future slot"

    yield (
        "messages",
        "meta",
        [build_message(attestation, subnet_id, current_time_ms, 0, "ignore", reason)],
    )


@with_phases([DENEB])
@spec_state_test
def test_gossip_beacon_attestation__accepts_first_slot_when_epoch_window_opens(spec, state):
    """Test that a first-slot attestation is accepted when the Deneb epoch window opens."""
    yield "topic", "meta", "beacon_attestation"

    attestation_epoch = spec.Epoch(2)
    store, signed_anchor, attestation = prepare_attestation(
        spec, state, spec.compute_start_slot_at_epoch(attestation_epoch)
    )
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    yield "state", state
    yield get_filename(attestation), attestation

    current_time_ms = epoch_window_open_time(spec, state, attestation_epoch)
    yield "current_time_ms", "meta", int(current_time_ms)

    subnet_id = get_correct_subnet_for_attestation(spec, state, attestation)
    seen = get_seen(spec)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, current_time_ms
    )
    assert result == "valid"
    assert reason is None

    yield "messages", "meta", [build_message(attestation, subnet_id, current_time_ms, 0, "valid")]


@with_phases([DENEB])
@spec_state_test
def test_gossip_beacon_attestation__accepts_first_slot_when_epoch_window_closes(spec, state):
    """Test that a first-slot attestation is accepted at the last valid Deneb epoch time."""
    yield "topic", "meta", "beacon_attestation"

    attestation_epoch = spec.Epoch(2)
    store, signed_anchor, attestation = prepare_attestation(
        spec, state, spec.compute_start_slot_at_epoch(attestation_epoch)
    )
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    yield "state", state
    yield get_filename(attestation), attestation

    current_time_ms = epoch_window_close_time(spec, state, attestation_epoch)
    yield "current_time_ms", "meta", int(current_time_ms)

    subnet_id = get_correct_subnet_for_attestation(spec, state, attestation)
    seen = get_seen(spec)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, current_time_ms
    )
    assert result == "valid"
    assert reason is None

    yield "messages", "meta", [build_message(attestation, subnet_id, current_time_ms, 0, "valid")]


@with_phases([DENEB])
@spec_state_test
def test_gossip_beacon_attestation__ignores_first_slot_after_epoch_window_closes(spec, state):
    """Test that a first-slot attestation is ignored after the Deneb epoch window closes."""
    yield "topic", "meta", "beacon_attestation"

    attestation_epoch = spec.Epoch(2)
    store, signed_anchor, attestation = prepare_attestation(
        spec, state, spec.compute_start_slot_at_epoch(attestation_epoch)
    )
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    yield "state", state
    yield get_filename(attestation), attestation

    current_time_ms = epoch_window_close_time(spec, state, attestation_epoch) + 1
    yield "current_time_ms", "meta", int(current_time_ms)

    subnet_id = get_correct_subnet_for_attestation(spec, state, attestation)
    seen = get_seen(spec)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, current_time_ms
    )
    assert result == "ignore"
    assert reason == "attestation epoch is not previous or current epoch"

    yield (
        "messages",
        "meta",
        [build_message(attestation, subnet_id, current_time_ms, 0, "ignore", reason)],
    )


@with_phases([DENEB])
@spec_state_test
def test_gossip_beacon_attestation__accepts_last_slot_one_millisecond_before_slot_start(
    spec, state
):
    """
    Test that a last-slot attestation is accepted one millisecond before its
    slot starts.
    """
    yield "topic", "meta", "beacon_attestation"

    attestation_epoch = spec.Epoch(2)
    attestation_slot = (
        spec.compute_start_slot_at_epoch(attestation_epoch) + spec.SLOTS_PER_EPOCH - 1
    )
    store, signed_anchor, attestation = prepare_attestation(spec, state, attestation_slot)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    yield "state", state
    yield get_filename(attestation), attestation

    current_time_ms = spec.compute_time_at_slot_ms(state, attestation.data.slot) - 1
    yield "current_time_ms", "meta", int(current_time_ms)

    subnet_id = get_correct_subnet_for_attestation(spec, state, attestation)
    seen = get_seen(spec)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, current_time_ms
    )
    assert result == "valid"
    assert reason is None

    yield "messages", "meta", [build_message(attestation, subnet_id, current_time_ms, 0, "valid")]


@with_phases([DENEB])
@spec_state_test
def test_gossip_beacon_attestation__accepts_last_slot_at_slot_start(spec, state):
    """Test that a last-slot attestation is accepted exactly at its slot start."""
    yield "topic", "meta", "beacon_attestation"

    attestation_epoch = spec.Epoch(2)
    attestation_slot = (
        spec.compute_start_slot_at_epoch(attestation_epoch) + spec.SLOTS_PER_EPOCH - 1
    )
    store, signed_anchor, attestation = prepare_attestation(spec, state, attestation_slot)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    yield "state", state
    yield get_filename(attestation), attestation

    current_time_ms = spec.compute_time_at_slot_ms(state, attestation.data.slot)
    yield "current_time_ms", "meta", int(current_time_ms)

    subnet_id = get_correct_subnet_for_attestation(spec, state, attestation)
    seen = get_seen(spec)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, current_time_ms
    )
    assert result == "valid"
    assert reason is None

    yield "messages", "meta", [build_message(attestation, subnet_id, current_time_ms, 0, "valid")]


@with_phases([DENEB])
@spec_state_test
def test_gossip_beacon_attestation__accepts_last_slot_when_epoch_window_closes(spec, state):
    """Test that a last-slot attestation is accepted at the last valid Deneb epoch time."""
    yield "topic", "meta", "beacon_attestation"

    attestation_epoch = spec.Epoch(2)
    attestation_slot = (
        spec.compute_start_slot_at_epoch(attestation_epoch) + spec.SLOTS_PER_EPOCH - 1
    )
    store, signed_anchor, attestation = prepare_attestation(spec, state, attestation_slot)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    yield "state", state
    yield get_filename(attestation), attestation

    current_time_ms = epoch_window_close_time(spec, state, attestation_epoch)
    yield "current_time_ms", "meta", int(current_time_ms)

    subnet_id = get_correct_subnet_for_attestation(spec, state, attestation)
    seen = get_seen(spec)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, current_time_ms
    )
    assert result == "valid"
    assert reason is None

    yield "messages", "meta", [build_message(attestation, subnet_id, current_time_ms, 0, "valid")]


@with_phases([DENEB])
@spec_state_test
def test_gossip_beacon_attestation__ignores_last_slot_after_epoch_window_closes(spec, state):
    """Test that a last-slot attestation is ignored after the Deneb epoch window closes."""
    yield "topic", "meta", "beacon_attestation"

    attestation_epoch = spec.Epoch(2)
    attestation_slot = (
        spec.compute_start_slot_at_epoch(attestation_epoch) + spec.SLOTS_PER_EPOCH - 1
    )
    store, signed_anchor, attestation = prepare_attestation(spec, state, attestation_slot)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    yield "state", state
    yield get_filename(attestation), attestation

    current_time_ms = epoch_window_close_time(spec, state, attestation_epoch) + 1
    yield "current_time_ms", "meta", int(current_time_ms)

    subnet_id = get_correct_subnet_for_attestation(spec, state, attestation)
    seen = get_seen(spec)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, current_time_ms
    )
    assert result == "ignore"
    assert reason == "attestation epoch is not previous or current epoch"

    yield (
        "messages",
        "meta",
        [build_message(attestation, subnet_id, current_time_ms, 0, "ignore", reason)],
    )
