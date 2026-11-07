"""Lock rules on a small fork, using the generated spec and real payload-status nodes."""

from dataclasses import replace
from importlib import import_module

import pytest

from eth_consensus_specs.test import context


@pytest.fixture
def spec(preset):
    return import_module(f"eth_consensus_specs.eip8453.{context.DEFAULT_TEST_PRESET}")


def at_slot(spec, slot):
    return spec.compute_time_at_slot_ms(spec.Uint64(0), spec.Slot(slot))


@pytest.fixture
def tree(spec):
    # F -- P -- A -- A1
    #       \-- B -- B1
    blocks = {}
    states = {}
    nodes = {}
    for index, (name, parent, slot) in enumerate(
        [
            ("F", None, 0),
            ("P", "F", 1),
            ("A", "P", 2),
            ("B", "P", 3),
            ("A1", "A", 4),
            ("B1", "B", 5),
        ],
        start=1,
    ):
        root = spec.Root(index.to_bytes(32, "little"))
        block = spec.BeaconBlock(
            slot=slot, parent_root=nodes[parent].root if parent else spec.Root()
        )
        # Children build on EMPTY. Payloads are absent unless a test adds one.
        block.body.signed_execution_payload_bid.message.block_hash = root
        blocks[root] = block
        states[root] = spec.BeaconState()
        nodes[name] = spec.ForkChoiceNode(root=root, payload_status=spec.PAYLOAD_STATUS_EMPTY)
    finalized = spec.HeightCheckpoint(height=0, root=nodes["F"].root)
    store = spec.Store(
        time_ms=at_slot(spec, 11) + spec.get_support_cutoff_ms(),
        genesis_time_ms=spec.Uint64(0),
        justified_checkpoint=finalized,
        finalized_checkpoint=finalized,
        proposer_boost_root=spec.Root(),
        blocks=blocks,
        block_states=states,
        latest_messages={},
        payloads={},
        payload_timeliness_vote={},
        payload_data_availability_vote={},
        payload_inclusion_list_satisfaction={},
        max_height=spec.Height(0),
        block_receipt_times=dict.fromkeys(blocks, spec.Uint64(0)),
        payload_receipt_times={},
        fast_confirmed_path=set(),
        latest_confirmed=spec.ForkChoiceNode(
            root=nodes["F"].root, payload_status=spec.PAYLOAD_STATUS_PENDING
        ),
        saved_confirmations={},
        locks=set(),
        head_vote_messages={},
        head_vote_message_receipt_times={},
        head_vote_committees={},
    )
    return store, nodes


def lock(spec, node, slot=9, fast=True, expiry=13):
    return spec.ACLock(node=node, slot=spec.Slot(slot), fast=fast, expiry_slot=spec.Slot(expiry))


def vote(spec, store, node, validator, slot=10, received=None):
    message = spec.HeadVoteMessage(
        validator_index=validator,
        data=spec.HeadVoteData(
            slot=slot, beacon_block_root=node.root, payload_status=node.payload_status
        ),
    )
    store.head_vote_messages.setdefault(spec.Slot(slot), []).append(message)
    store.head_vote_message_receipt_times[spec.hash_tree_root(message)] = (
        at_slot(spec, slot) if received is None else received
    )
    store.head_vote_committees.setdefault(
        spec.Slot(slot), spec.HeadVoteCommittee(data=list(range(spec.HEAD_VOTE_COMMITTEE_SIZE)))
    )


def vote_half(spec, store, node, slot=10):
    for validator in range(spec.HEAD_VOTE_COMMITTEE_SIZE // 2):
        vote(spec, store, node, validator, slot)


def test_fast_expiry_grows_and_is_capped(spec, tree):
    store, nodes = tree
    expiries = []
    for slot in range(10, 15):
        store.time_ms = at_slot(spec, slot + 1) + spec.get_support_cutoff_ms()
        frame = spec.get_fg_frame(store)
        expiry = spec.compute_fast_lock_expiry(store, frame, spec.Slot(slot))
        expiries.append(int(expiry))
        spec.add_locks(store, frame, {lock(spec, nodes["A"], slot=slot, expiry=expiry)})
    assert expiries == [12, 14, 16, 17, 18]


def test_fast_expiry_paper_example_and_gap(spec, tree, monkeypatch):
    store, nodes = tree
    monkeypatch.setattr(spec, "SLOW_LOCK_WINDOW", spec.Slot(6))
    expiries = []
    for slot in [10, 11, 12, 13, 14, 16]:
        store.time_ms = at_slot(spec, slot + 1)
        frame = spec.get_fg_frame(store)
        expiry = spec.compute_fast_lock_expiry(store, frame, spec.Slot(slot))
        expiries.append(int(expiry))
        spec.add_locks(store, frame, {lock(spec, nodes["A"], slot=slot, expiry=expiry)})
    assert expiries == [12, 14, 16, 18, 20, 22]


@pytest.mark.parametrize("kind", ["slow", "same_slot", "newer_slot", "expired", "outside_frame"])
def test_fast_expiry_ignores_ineligible_locks(spec, tree, kind):
    store, nodes = tree
    existing = lock(spec, nodes["A"])
    if kind == "slow":
        existing = replace(existing, fast=False)
    elif kind == "same_slot":
        existing = replace(existing, slot=spec.Slot(10))
    elif kind == "newer_slot":
        existing = replace(existing, slot=spec.Slot(11))
    elif kind == "expired":
        existing = replace(existing, expiry_slot=spec.Slot(10))
    else:
        existing = replace(existing, node=replace(nodes["A"], root=spec.Root(b"\xff" * 32)))
    store.locks = {existing}
    assert spec.compute_fast_lock_expiry(store, spec.get_fg_frame(store), spec.Slot(10)) == 12


def test_fast_expiry_counts_lock_moved_to_finalized(spec, tree):
    store, _ = tree
    frame = spec.get_fg_frame(store)
    store.locks = {lock(spec, frame.finalized_node, expiry=12)}
    assert spec.compute_fast_lock_expiry(store, frame, spec.Slot(10)) == 14


def test_fast_and_slow_locks_with_same_node_and_expiry(spec, tree):
    store, nodes = tree
    store.saved_confirmations = dict.fromkeys(range(7, 10), nodes["A"])
    store.locks = {lock(spec, nodes["A"], expiry=12)}
    vote_half(spec, store, nodes["A"])
    spec.update_confirmation(store, spec.Slot(10))
    new = {item for item in store.locks if item.slot == 10}
    assert new == {
        lock(spec, nodes["A"], slot=10, fast=True, expiry=14),
        lock(spec, nodes["A"], slot=10, fast=False, expiry=14),
    }
    assert store.latest_confirmed == nodes["A"]


def test_fast_and_slow_locks_can_have_different_nodes(spec, tree):
    store, nodes = tree
    store.saved_confirmations = dict.fromkeys(range(7, 10), nodes["P"])
    vote_half(spec, store, nodes["A"])
    spec.update_confirmation(store, spec.Slot(10))
    assert store.locks == {
        lock(spec, nodes["A"], slot=10, fast=True, expiry=12),
        lock(spec, nodes["P"], slot=10, fast=False, expiry=14),
    }


def test_veto_records_candidate_and_locks_shared_ancestor(spec, tree):
    store, nodes = tree
    store.latest_confirmed = nodes["A"]
    existing = lock(spec, nodes["A"])
    store.locks = {existing}
    store.saved_confirmations = dict.fromkeys(range(7, 10), nodes["B"])
    vote_half(spec, store, nodes["B"])
    spec.update_confirmation(store, spec.Slot(10))
    assert store.saved_confirmations[10] == nodes["B"]
    assert store.latest_confirmed == nodes["A"]
    assert store.fast_confirmed_path == set()
    assert store.locks == {
        existing,
        lock(spec, nodes["P"], slot=10, fast=True, expiry=14),
        lock(spec, nodes["P"], slot=10, fast=False, expiry=14),
    }


@pytest.mark.parametrize("missing", ["absent", "removed"])
def test_missing_candidate_breaks_slow_streak(spec, tree, missing):
    store, nodes = tree
    store.saved_confirmations = dict.fromkeys(range(7, 10), nodes["A"])
    if missing == "absent":
        del store.saved_confirmations[8]
    else:
        store.saved_confirmations[8] = replace(nodes["A"], root=spec.Root(b"\xff" * 32))
    assert (
        spec.compute_slow_lock(store, spec.get_fg_frame(store), spec.Slot(10), nodes["A"]) is None
    )


def test_no_candidate_clears_saved_slot(spec, tree):
    store, nodes = tree
    store.saved_confirmations[10] = nodes["A"]
    store.fast_confirmed_path = {nodes["A"]}
    store.head_vote_committees[10] = spec.HeadVoteCommittee(
        data=list(range(spec.HEAD_VOTE_COMMITTEE_SIZE))
    )
    spec.update_confirmation(store, spec.Slot(10))
    assert 10 not in store.saved_confirmations
    assert not store.fast_confirmed_path


def test_expiry_at_slot_start(spec, tree):
    store, nodes = tree
    store.locks = {lock(spec, nodes["A"], expiry=12)}
    frame = spec.get_fg_frame(store)
    assert len(spec.get_live_locks(store, frame, at_slot(spec, 13) - 1)) == 1
    assert not spec.get_live_locks(store, frame, at_slot(spec, 13))
    assert not spec.get_live_locks(store, frame, at_slot(spec, 13) + spec.get_head_vote_due_ms())


def test_live_locks_move_to_viable_ancestor_and_stay_there(spec, tree):
    store, nodes = tree
    original = lock(spec, nodes["A"])
    store.locks = {original}
    full_frame = spec.get_fg_frame(store)
    frame = replace(full_frame, viable_heads={nodes["B"]})
    moved = replace(original, node=nodes["P"])
    assert spec.get_live_locks(store, frame, store.time_ms) == {moved}
    assert spec.get_head_walk_anchor(store, frame) == nodes["P"]
    assert not spec.conflicts_with_lock(store, frame, nodes["B"])
    # Even an empty lock update must store the moved node.
    spec.add_locks(store, frame, set())
    assert spec.get_live_locks(store, full_frame, store.time_ms) == {moved}


def test_anchor_uses_frame_root_when_lock_is_its_ancestor(spec, tree):
    store, nodes = tree
    store.locks = {lock(spec, nodes["P"])}
    frame = replace(
        spec.get_fg_frame(store), forkchoice_root=nodes["A"], viable_heads={nodes["A1"]}
    )
    assert spec.get_head_walk_anchor(store, frame) == nodes["A"]
    assert not spec.conflicts_with_lock(store, frame, nodes["A1"])


def test_unlock_half_moves_to_common_ancestor_preserving_fields(spec, tree):
    store, nodes = tree
    original = lock(spec, nodes["A"], fast=False)
    store.locks = {original}
    vote_half(spec, store, nodes["B"])
    spec.unlock(store, spec.Slot(10), store.time_ms)
    assert store.locks == {replace(original, node=nodes["P"])}


def test_unlock_below_half_keeps_lock(spec, tree):
    store, nodes = tree
    original = lock(spec, nodes["A"])
    store.locks = {original}
    for validator in range(spec.HEAD_VOTE_COMMITTEE_SIZE // 2 - 1):
        vote(spec, store, nodes["B"], validator)
    spec.unlock(store, spec.Slot(10), store.time_ms)
    assert store.locks == {original}


@pytest.mark.parametrize("lock_slot", [10, 11])
def test_unlock_does_not_move_same_or_newer_slot_lock(spec, tree, lock_slot):
    store, nodes = tree
    original = lock(spec, nodes["A"], slot=lock_slot)
    store.locks = {original}
    vote_half(spec, store, nodes["B"])
    spec.unlock(store, spec.Slot(10), store.time_ms)
    assert store.locks == {original}


def test_unlock_equivocators_count_without_resolved_votes(spec, tree):
    store, nodes = tree
    original = lock(spec, nodes["A"])
    store.locks = {original}
    unknown_a = replace(nodes["A"], root=spec.Root(b"\xfe" * 32))
    unknown_b = replace(nodes["B"], root=spec.Root(b"\xff" * 32))
    for validator in range(spec.HEAD_VOTE_COMMITTEE_SIZE // 2):
        vote(spec, store, unknown_a, validator)
        vote(spec, store, unknown_b, validator)
    spec.unlock(store, spec.Slot(10), store.time_ms)
    # Half equivocating opposes every ancestor, including F. Use the explicit F fallback.
    assert store.locks == {replace(original, node=spec.get_fg_frame(store).finalized_node)}


def test_unlock_equivocator_not_counted_twice(spec, tree):
    store, nodes = tree
    original = lock(spec, nodes["A"])
    store.locks = {original}
    # One equivocator plus half-minus-two clean opponents is still below half.
    vote(spec, store, nodes["A"], 0)
    vote(spec, store, nodes["B"], 0)
    for validator in range(1, spec.HEAD_VOTE_COMMITTEE_SIZE // 2 - 1):
        vote(spec, store, nodes["B"], validator)
    spec.unlock(store, spec.Slot(10), store.time_ms)
    assert store.locks == {original}


def test_unlock_counts_duplicate_committee_seats(spec, tree):
    store, nodes = tree
    original = lock(spec, nodes["A"])
    store.locks = {original}
    vote(spec, store, nodes["B"], 0)
    half = spec.HEAD_VOTE_COMMITTEE_SIZE // 2
    store.head_vote_committees[10] = spec.HeadVoteCommittee(data=[0] * half + [1] * half)
    spec.unlock(store, spec.Slot(10), store.time_ms)
    assert store.locks == {replace(original, node=nodes["P"])}


def test_unlock_full_empty_conflict_moves_to_pending(spec, tree):
    store, nodes = tree
    original = lock(spec, nodes["A"])
    store.locks = {original}
    store.payloads[nodes["A"].root] = spec.ExecutionPayloadEnvelope()
    store.payload_receipt_times[nodes["A"].root] = spec.Uint64(0)
    full = replace(nodes["A"], payload_status=spec.PAYLOAD_STATUS_FULL)
    vote_half(spec, store, full)
    spec.unlock(store, spec.Slot(10), store.time_ms)
    pending = replace(nodes["A"], payload_status=spec.PAYLOAD_STATUS_PENDING)
    assert store.locks == {replace(original, node=pending)}


def test_unlock_removes_expired_locks(spec, tree):
    store, nodes = tree
    store.locks = {lock(spec, nodes["A"], expiry=10)}
    spec.unlock(store, spec.Slot(10), store.time_ms)
    assert not store.locks


def test_confirmation_tick_uses_current_time_for_lock_expiry(spec, tree):
    store, nodes = tree
    store.latest_confirmed = nodes["A"]
    store.locks = {lock(spec, nodes["A"], slot=8, expiry=10)}
    store.time_ms = at_slot(spec, 11) - 1
    vote_half(spec, store, nodes["B"])
    tick_time = at_slot(spec, 11) + spec.get_support_cutoff_ms()
    spec.on_tick(store, tick_time)
    assert store.time_ms == tick_time
    assert store.latest_confirmed == nodes["B"]
    assert store.locks == {lock(spec, nodes["B"], slot=10, expiry=12)}


def test_equivocators_do_not_supply_fast_lock_support(spec, tree):
    store, nodes = tree
    vote(spec, store, nodes["A"], 0)
    vote(spec, store, nodes["B"], 0)
    for validator in range(1, spec.HEAD_VOTE_COMMITTEE_SIZE // 2):
        vote(spec, store, nodes["A"], validator)
    spec.update_confirmation(store, spec.Slot(10))
    # The clean votes exceed half of participation, but are below half of the committee.
    assert store.latest_confirmed == nodes["A"]
    assert not store.locks


def test_slow_lock_does_not_require_fast_threshold(spec, tree):
    store, nodes = tree
    store.saved_confirmations = dict.fromkeys(range(7, 10), nodes["A"])
    vote(spec, store, nodes["A"], 0)
    spec.update_confirmation(store, spec.Slot(10))
    assert store.locks == {lock(spec, nodes["A"], slot=10, fast=False, expiry=14)}
    assert not store.fast_confirmed_path
