from eth_utils import encode_hex

from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.attestations import (
    get_valid_attestations_at_slot,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block,
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    apply_next_epoch_with_attestations,
    apply_next_slots_with_attestations,
    on_tick_and_append_step,
    output_store_checks,
    setup_finalized_store,
    tick_and_add_block,
    tick_and_run_on_attestation,
    tick_store_to_slot,
)
from eth_consensus_specs.test.helpers.state import (
    next_slot,
    state_transition_and_sign_block,
)


def _setup_reorg_scenario(
    spec,
    state,
    late,
    attest_parent=True,
    equivocate=False,
    stall_epochs=0,
    align_boundary=False,
):
    """
    Build a finalized chain, the re-org target parent, and the head above it, then
    advance to the proposing slot.
    """
    store, state, test_steps = yield from setup_finalized_store(spec, state)

    # Insert empty epochs so finalization lags the proposing slot
    for _ in range(stall_epochs):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, fill_cur_epoch=False, fill_prev_epoch=False, test_steps=test_steps
        )

    if align_boundary:
        # Advance with attestations so the proposing slot lands on an epoch boundary,
        # with parent, head, and propose as the next three slots
        while state.slot % spec.SLOTS_PER_EPOCH != spec.SLOTS_PER_EPOCH - 3:
            state, store, _ = yield from apply_next_slots_with_attestations(
                spec,
                state,
                store,
                1,
                fill_cur_epoch=True,
                fill_prev_epoch=True,
                test_steps=test_steps,
            )
    else:
        # Make a lead-in block before the re-org target parent
        block = build_empty_block_for_next_slot(spec, state)
        signed_block = state_transition_and_sign_block(spec, state, block)
        yield from tick_and_add_block(spec, store, signed_block, test_steps)

    # Fill a slot to become the re-org target parent
    state, store, signed_parent_block = yield from apply_next_slots_with_attestations(
        spec, state, store, 1, fill_cur_epoch=True, fill_prev_epoch=True, test_steps=test_steps
    )

    # Build the head block on the parent
    block = build_empty_block_for_next_slot(spec, state)
    if attest_parent:
        block.body.attestations = get_valid_attestations_at_slot(state, spec, block.slot - 1)
    head_parent_state = state.copy() if equivocate else None
    signed_block = state_transition_and_sign_block(spec, state, block)

    if late:
        # Tick just past the attestation deadline so the head is recorded late on every preset
        late_seconds = spec.get_attestation_due_ms() // 1000 + 1
        late_time = (
            state.slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time + late_seconds
        )
        on_tick_and_append_step(spec, store, late_time, test_steps)

    yield from tick_and_add_block(spec, store, signed_block, test_steps)

    if equivocate:
        # Add a second block at the head's slot from the same proposer
        sibling = build_empty_block(spec, head_parent_state, slot=block.slot)
        sibling.body.graffiti = spec.Bytes32(b"\x01" * 32)
        signed_sibling = state_transition_and_sign_block(spec, head_parent_state, sibling)
        yield from tick_and_add_block(spec, store, signed_sibling, test_steps)

    head = spec.get_head(store)
    parent_root = store.blocks[head.root].parent_root
    assert parent_root == signed_parent_block.message.hash_tree_root()

    # Advance to the proposing slot
    next_slot(spec, state)
    return store, state, head, parent_root, state.slot, test_steps


def _emit_proposer_head_check(spec, store, proposer_head, test_steps):
    """
    Emit the store checks and the get_proposer_head oracle node.
    """
    output_store_checks(spec, store, test_steps)
    test_steps.append(
        {
            "checks": {
                "get_proposer_head": {
                    "root": encode_hex(proposer_head.root),
                    "payload_status": int(proposer_head.payload_status),
                },
            }
        }
    )


@with_gloas_and_later
@spec_state_test
def test_proposer_head_reorgs_late_head(spec, state):
    """
    Test the primary re-org decision for a late, weakly-supported head: the head is
    kept while its parent is weak, re-orged onto the parent once that parent is
    strongly supported, then kept again once the proposer is past the re-org cutoff.
    """
    store, state, head, parent_root, slot, test_steps = yield from _setup_reorg_scenario(
        spec, state, late=True
    )
    tick_store_to_slot(spec, store, slot, test_steps)

    # The late weak head is kept while its parent is not yet strong
    assert spec.is_head_late(store, head.root)
    assert spec.is_head_weak(store, head.root)
    assert not spec.is_parent_strong(store, head.root)
    proposer_head = spec.get_proposer_head(store, head, slot)
    assert proposer_head.root == head.root
    _emit_proposer_head_check(spec, store, proposer_head, test_steps)

    # Parent now strongly supported, so the proposer re-orgs onto it. Its support must
    # aggregate on the pending node, as one resolved payload status stays below threshold
    attestations = get_valid_attestations_at_slot(
        state, spec, slot_to_attest=slot - 1, beacon_block_root=parent_root
    )
    for attestation in attestations:
        yield from tick_and_run_on_attestation(spec, store, attestation, test_steps)
    assert spec.is_epoch_boundary(slot)
    assert spec.is_ffg_competitive(store, head.root, parent_root)
    assert spec.is_finalization_ok(store, slot)
    assert spec.is_proposing_on_time(store)
    assert spec.is_parent_strong(store, head.root)
    proposer_head = spec.get_proposer_head(store, head, slot)
    assert proposer_head.root == parent_root
    _emit_proposer_head_check(spec, store, proposer_head, test_steps)

    # Past the re-org cutoff the proposer is no longer on time, so the head is kept
    cutoff_seconds = spec.get_proposer_reorg_cutoff_ms() // 1000
    slot_start = slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
    on_tick_and_append_step(spec, store, slot_start + cutoff_seconds + 1, test_steps)
    assert not spec.is_proposing_on_time(store)
    proposer_head = spec.get_proposer_head(store, head, slot)
    assert proposer_head.root == head.root
    _emit_proposer_head_check(spec, store, proposer_head, test_steps)

    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_proposer_head_timely_head_no_reorg(spec, state):
    """
    Test that the proposer does not re-org a head that arrived on time, even when
    the parent is strongly supported and the head is weakly supported.
    """
    store, state, head, parent_root, slot, test_steps = yield from _setup_reorg_scenario(
        spec, state, late=False
    )
    attestations = get_valid_attestations_at_slot(
        state, spec, slot_to_attest=slot - 1, beacon_block_root=parent_root
    )
    for attestation in attestations:
        yield from tick_and_run_on_attestation(spec, store, attestation, test_steps)

    # Every condition holds except that the head is not late
    assert not spec.is_head_late(store, head.root)
    assert spec.is_epoch_boundary(slot)
    assert spec.is_ffg_competitive(store, head.root, parent_root)
    assert spec.is_finalization_ok(store, slot)
    assert spec.is_proposing_on_time(store)
    assert spec.is_head_weak(store, head.root)
    assert spec.is_parent_strong(store, head.root)

    # The on-time head's proposer boost was cleared by the proposing-slot tick, so
    # get_proposer_head's boost guard does not trip
    assert store.proposer_boost_root != head.root

    # The on-time head is kept
    proposer_head = spec.get_proposer_head(store, head, slot)
    assert proposer_head.root == head.root

    _emit_proposer_head_check(spec, store, proposer_head, test_steps)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_proposer_head_strong_head_no_reorg(spec, state):
    """
    Test that the proposer does not re-org a late head that is strongly
    supported.
    """
    store, state, head, parent_root, slot, test_steps = yield from _setup_reorg_scenario(
        spec, state, late=True
    )

    # Attest the head slot committee to the head, which also keeps the parent strong
    attestations = get_valid_attestations_at_slot(
        state, spec, slot_to_attest=slot - 1, beacon_block_root=head.root
    )
    for attestation in attestations:
        yield from tick_and_run_on_attestation(spec, store, attestation, test_steps)

    # Every condition holds except that the head is not weak
    assert spec.is_head_late(store, head.root)
    assert spec.is_epoch_boundary(slot)
    assert spec.is_ffg_competitive(store, head.root, parent_root)
    assert spec.is_finalization_ok(store, slot)
    assert spec.is_proposing_on_time(store)
    assert not spec.is_head_weak(store, head.root)
    assert spec.is_parent_strong(store, head.root)

    # The strong head is kept
    proposer_head = spec.get_proposer_head(store, head, slot)
    assert proposer_head.root == head.root

    _emit_proposer_head_check(spec, store, proposer_head, test_steps)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_proposer_head_unfinalized_no_reorg(spec, state):
    """
    Test that the proposer does not re-org a late, weakly-supported head onto its
    strongly-supported parent when finalization has fallen too far behind.
    """
    store, state, head, parent_root, slot, test_steps = yield from _setup_reorg_scenario(
        spec, state, late=True, stall_epochs=1
    )
    attestations = get_valid_attestations_at_slot(
        state, spec, slot_to_attest=slot - 1, beacon_block_root=parent_root
    )
    for attestation in attestations:
        yield from tick_and_run_on_attestation(spec, store, attestation, test_steps)

    # Every condition holds except that finalization is lagging the proposing slot
    assert spec.is_head_late(store, head.root)
    assert spec.is_epoch_boundary(slot)
    assert spec.is_ffg_competitive(store, head.root, parent_root)
    assert not spec.is_finalization_ok(store, slot)
    assert spec.is_proposing_on_time(store)
    assert spec.is_head_weak(store, head.root)
    assert spec.is_parent_strong(store, head.root)

    # The head is kept because finalization is lagging
    proposer_head = spec.get_proposer_head(store, head, slot)
    assert proposer_head.root == head.root

    _emit_proposer_head_check(spec, store, proposer_head, test_steps)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_proposer_head_epoch_boundary_no_reorg(spec, state):
    """
    Test that the proposer does not re-org a late, weakly-supported head when the
    proposing slot is the first slot of an epoch.
    """
    store, state, head, parent_root, slot, test_steps = yield from _setup_reorg_scenario(
        spec, state, late=True, align_boundary=True
    )
    attestations = get_valid_attestations_at_slot(
        state, spec, slot_to_attest=slot - 1, beacon_block_root=parent_root
    )
    for attestation in attestations:
        yield from tick_and_run_on_attestation(spec, store, attestation, test_steps)

    # Every condition holds except the boundary: is_epoch_boundary is false at a real
    # boundary (re-orgs forbidden there), so we assert its negation
    assert spec.is_head_late(store, head.root)
    assert not spec.is_epoch_boundary(slot)
    assert spec.is_ffg_competitive(store, head.root, parent_root)
    assert spec.is_finalization_ok(store, slot)
    assert spec.is_proposing_on_time(store)
    assert spec.is_head_weak(store, head.root)
    assert spec.is_parent_strong(store, head.root)

    # The head is kept because the proposing slot is an epoch boundary
    proposer_head = spec.get_proposer_head(store, head, slot)
    assert proposer_head.root == head.root

    _emit_proposer_head_check(spec, store, proposer_head, test_steps)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_proposer_head_equivocation_reorg(spec, state):
    """
    Test that the proposer re-orgs onto a weakly-supported parent via the
    equivocation branch when the head proposer equivocated, independently of
    whether the head is late.
    """
    store, state, head, parent_root, slot, test_steps = yield from _setup_reorg_scenario(
        spec, state, late=False, attest_parent=False, equivocate=True
    )

    # No extra attestations to the parent, so tick straight to the proposing slot
    tick_store_to_slot(spec, store, slot, test_steps)

    # The primary branch fails (head on time, parent weak), but the equivocation
    # branch re-orgs on its own conditions
    head_block = store.blocks[head.root]
    assert not spec.is_head_late(store, head.root)
    assert spec.is_head_weak(store, head.root)
    assert not spec.is_parent_strong(store, head.root)
    assert head_block.slot + 1 == slot
    assert spec.is_proposer_equivocation(store, head.root)

    # The proposer re-orgs onto the parent because of the equivocation
    proposer_head = spec.get_proposer_head(store, head, slot)
    assert proposer_head.root == parent_root

    _emit_proposer_head_check(spec, store, proposer_head, test_steps)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_proposer_head_equivocation_stale_head_no_reorg(spec, state):
    """
    Test that the proposer does not re-org on an equivocation when the head is two
    slots back, since the equivocation branch still requires an adjacent head.
    """
    store, state, head, parent_root, slot, test_steps = yield from _setup_reorg_scenario(
        spec, state, late=True, equivocate=True
    )

    # Propose one slot later, leaving the head two slots back
    next_slot(spec, state)
    slot = state.slot

    # Make the parent strong via the head slot committee
    head_block = store.blocks[head.root]
    attestations = get_valid_attestations_at_slot(
        state, spec, slot_to_attest=head_block.slot, beacon_block_root=parent_root
    )
    for attestation in attestations:
        yield from tick_and_run_on_attestation(spec, store, attestation, test_steps)

    # Tick to the proposing slot on time
    tick_store_to_slot(spec, store, slot, test_steps)

    # The equivocation branch holds every condition except the adjacency window
    assert spec.is_proposer_equivocation(store, head.root)
    assert spec.is_head_weak(store, head.root)
    assert head_block.slot + 1 != slot

    # The non-adjacent head is kept despite the equivocation
    proposer_head = spec.get_proposer_head(store, head, slot)
    assert proposer_head.root == head.root

    _emit_proposer_head_check(spec, store, proposer_head, test_steps)
    yield "steps", test_steps
