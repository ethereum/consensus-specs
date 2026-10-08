"""
Gloas (EIP-7732) optimistic-sync tests covering EL payload invalidation.

Gloas splits delivery of a beacon block (`on_block`) from delivery of its
execution payload (`on_execution_payload_envelope`), so a beacon block root
resolves to two distinct `ForkChoiceNode`s -- PAYLOAD_STATUS_FULL and
PAYLOAD_STATUS_EMPTY (specs/gloas/fork-choice.md). When the EL reports a
payload INVALID with `latest_valid_hash = block_hash(A)`, the first FULL
beacon block B that directly extends A's payload must have its FULL
interpretation -- and everything that descends from it -- invalidated,
while blocks between A and B (which never claimed to extend A) and any
EMPTY-branch descendants of B must remain viable. See
https://github.com/ethereum/consensus-specs/issues/5635.
"""

from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    add_block,
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
)
from eth_consensus_specs.test.helpers.optimistic_sync import (
    add_gloas_optimistic_envelope,
    add_gloas_payload_info,
    get_gloas_optimistic_head_node,
    get_optimistic_store,
    GloasMegaStore,
    is_gloas_payload_invalidated,
    PayloadStatusV1,
    PayloadStatusV1Status,
)
from eth_consensus_specs.test.helpers.state import (
    state_transition_and_sign_block,
)


def H_A(spec):
    return spec.Hash32(b"\xaa" * 32)


def H_B(spec):
    return spec.Hash32(b"\xbb" * 32)


def H_C(spec):
    return spec.Hash32(b"\xcc" * 32)


def _build_full_child(spec, state, new_el_hash, parent_el_hash):
    """
    Build, sign, and state-transition a child block that claims a FULL
    parent (its bid's ``parent_block_hash`` matches the parent's own
    committed bid hash) and itself commits to revealing ``new_el_hash``.
    """
    block = build_empty_block_for_next_slot(spec, state)
    block.body.signed_execution_payload_bid.message.parent_block_hash = parent_el_hash
    block.body.signed_execution_payload_bid.message.block_hash = new_el_hash
    return state_transition_and_sign_block(spec, state, block)


def _build_empty_child(spec, state, parent_el_hash):
    """
    Build, sign, and state-transition a child block that does not reveal a
    new payload, continuing to point at ``parent_el_hash`` as the live EL
    tip (i.e. it does not claim its immediate beacon parent as FULL).
    """
    block = build_empty_block_for_next_slot(spec, state)
    block.body.signed_execution_payload_bid.message.parent_block_hash = parent_el_hash
    return state_transition_and_sign_block(spec, state, block)


def _setup_store_and_mega_store(spec, state, test_steps):
    fc_store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    opt_store = get_optimistic_store(spec, state, anchor_block)
    mega_store = GloasMegaStore(spec, fc_store, opt_store)

    current_time_ms = spec.compute_time_at_slot_ms(
        fc_store.genesis_time_ms, spec.SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY * 10 + state.slot
    )
    on_tick_and_append_step(spec, fc_store, current_time_ms, test_steps)
    return fc_store, mega_store, anchor_block


def _add_full_block_and_envelope(spec, mega_store, state, signed_block, test_steps, status):
    """
    Deliver a FULL block's beacon block and its execution payload envelope,
    in that order -- the envelope must land before any later block that
    claims this block as its FULL parent (see `is_parent_node_full` in
    specs/gloas/fork-choice.md).
    """
    block_hash = signed_block.message.body.signed_execution_payload_bid.message.block_hash
    payload_status = PayloadStatusV1(status=status)
    if payload_status.status == PayloadStatusV1Status.VALID:
        payload_status.latest_valid_hash = block_hash
    add_gloas_payload_info(test_steps, block_hash, payload_status)
    yield from add_block(spec, mega_store.fc_store, signed_block, test_steps, is_optimistic=True)
    block_root = signed_block.message.hash_tree_root()
    envelope = build_signed_execution_payload_envelope(spec, state, block_root, signed_block)
    yield from add_gloas_optimistic_envelope(
        spec, mega_store, envelope, test_steps, payload_status=payload_status
    )
    return block_root


@with_gloas_and_later
@spec_state_test
def test_optimistic_invalidation_preserves_empty_sibling_of_head(spec, state):
    """
    B is the current (FULL) head. The EL reports B's payload INVALID with
    latest_valid_hash = block_hash(A), A being B's own FULL parent. B's FULL
    interpretation must be removed, but B is still a known beacon block, so
    the EMPTY interpretation of B must remain viable and become the new head.
    """
    test_steps = []
    _fc_store, mega_store, anchor_block = _setup_store_and_mega_store(spec, state, test_steps)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    # A: FULL, extends the anchor
    signed_a = _build_full_child(spec, state, H_A(spec), parent_el_hash=state.latest_block_hash)
    a_root = yield from _add_full_block_and_envelope(
        spec, mega_store, state, signed_a, test_steps, status=PayloadStatusV1Status.VALID
    )

    # B: FULL, extends A -- reported INVALID immediately, LVH = A
    signed_b = _build_full_child(spec, state, H_B(spec), parent_el_hash=H_A(spec))
    b_root = signed_b.message.hash_tree_root()
    invalid_status = PayloadStatusV1(
        status=PayloadStatusV1Status.INVALID,
        latest_valid_hash=H_A(spec),
        validation_error="invalid",
    )
    add_gloas_payload_info(test_steps, H_B(spec), invalid_status)
    yield from add_block(spec, mega_store.fc_store, signed_b, test_steps, is_optimistic=True)
    envelope_b = build_signed_execution_payload_envelope(spec, state, b_root, signed_b)
    yield from add_gloas_optimistic_envelope(
        spec, mega_store, envelope_b, test_steps, payload_status=invalid_status
    )

    full_b = spec.ForkChoiceNode(root=b_root, payload_status=spec.PAYLOAD_STATUS_FULL)
    empty_b = spec.ForkChoiceNode(root=b_root, payload_status=spec.PAYLOAD_STATUS_EMPTY)
    full_a = spec.ForkChoiceNode(root=a_root, payload_status=spec.PAYLOAD_STATUS_FULL)

    assert is_gloas_payload_invalidated(spec, mega_store, full_b)
    assert not is_gloas_payload_invalidated(spec, mega_store, empty_b)
    assert not is_gloas_payload_invalidated(spec, mega_store, full_a)

    head = get_gloas_optimistic_head_node(spec, mega_store)
    assert head.root == b_root
    assert head.payload_status == spec.PAYLOAD_STATUS_EMPTY

    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_optimistic_invalidation_removes_full_chain_descendants(spec, state):
    """
    Chain: anchor -> A(FULL) -> E1(EMPTY, still pointing at A) -> B(FULL,
    extends A) -> C(FULL, extends B). The EL reports C's payload INVALID
    with latest_valid_hash = block_hash(A). B is "the first Full beacon
    block descended from A-Full on the chain leading to the invalidated
    head" (issue #5635), so B-FULL and its descendant C must be invalidated,
    while A and the intermediate Empty block E1 must not be.
    """
    test_steps = []
    _fc_store, mega_store, anchor_block = _setup_store_and_mega_store(spec, state, test_steps)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    # A: FULL, extends the anchor
    signed_a = _build_full_child(spec, state, H_A(spec), parent_el_hash=state.latest_block_hash)
    a_root = yield from _add_full_block_and_envelope(
        spec, mega_store, state, signed_a, test_steps, status=PayloadStatusV1Status.VALID
    )

    # E1: EMPTY, does not claim A as its parent; the EL's view of the chain
    # tip stays at A's hash across this slot.
    signed_e1 = _build_empty_child(spec, state, parent_el_hash=H_A(spec))
    yield from add_block(spec, mega_store.fc_store, signed_e1, test_steps, is_optimistic=True)
    e1_root = signed_e1.message.hash_tree_root()

    # B: its payload directly extends A's (parent_el_hash=H_A), even though
    # its immediate beacon parent is the Empty E1 -- it attaches under
    # (E1, EMPTY) in the fork-choice tree, which is itself a PENDING child of
    # (A, FULL), so B (and anything built on B) still descends from A-FULL.
    signed_b = _build_full_child(spec, state, H_B(spec), parent_el_hash=H_A(spec))
    b_root = yield from _add_full_block_and_envelope(
        spec, mega_store, state, signed_b, test_steps, status=PayloadStatusV1Status.SYNCING
    )

    # C: FULL, extends B -- reported INVALID, LVH = A. The harness must walk
    # back from C through the known FULL-payload chain (C -> B -> A) to find
    # B, the first FULL block that directly extends A.
    signed_c = _build_full_child(spec, state, H_C(spec), parent_el_hash=H_B(spec))
    c_root = signed_c.message.hash_tree_root()
    invalid_status = PayloadStatusV1(
        status=PayloadStatusV1Status.INVALID,
        latest_valid_hash=H_A(spec),
        validation_error="invalid",
    )
    add_gloas_payload_info(test_steps, H_C(spec), invalid_status)
    yield from add_block(spec, mega_store.fc_store, signed_c, test_steps, is_optimistic=True)
    envelope_c = build_signed_execution_payload_envelope(spec, state, c_root, signed_c)
    yield from add_gloas_optimistic_envelope(
        spec, mega_store, envelope_c, test_steps, payload_status=invalid_status
    )

    assert mega_store.invalidated_full_roots == {b_root}

    full_b = spec.ForkChoiceNode(root=b_root, payload_status=spec.PAYLOAD_STATUS_FULL)
    full_c = spec.ForkChoiceNode(root=c_root, payload_status=spec.PAYLOAD_STATUS_FULL)
    empty_c = spec.ForkChoiceNode(root=c_root, payload_status=spec.PAYLOAD_STATUS_EMPTY)
    full_a = spec.ForkChoiceNode(root=a_root, payload_status=spec.PAYLOAD_STATUS_FULL)
    empty_e1 = spec.ForkChoiceNode(root=e1_root, payload_status=spec.PAYLOAD_STATUS_EMPTY)

    # B-FULL and everything that descends from it (both of C's possible
    # interpretations) are invalidated.
    assert is_gloas_payload_invalidated(spec, mega_store, full_b)
    assert is_gloas_payload_invalidated(spec, mega_store, full_c)
    assert is_gloas_payload_invalidated(spec, mega_store, empty_c)

    # A, and the Empty node between A and B, are untouched.
    assert not is_gloas_payload_invalidated(spec, mega_store, full_a)
    assert not is_gloas_payload_invalidated(spec, mega_store, empty_e1)

    # With B-FULL gone and nothing built on B-EMPTY, the head falls back to
    # B's own Empty interpretation.
    head = get_gloas_optimistic_head_node(spec, mega_store)
    assert head.root == b_root
    assert head.payload_status == spec.PAYLOAD_STATUS_EMPTY

    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_optimistic_invalidation_preserves_empty_branch_descendants(spec, state):
    """
    Chain: anchor -> A(FULL) -> B(FULL, extends A) -> D(EMPTY, does not
    claim B as its parent). The EL reports B's payload INVALID with
    latest_valid_hash = block_hash(A). B-FULL is invalidated, but D descends
    from B-EMPTY, not B-FULL, and must remain viable -- indeed it becomes
    the new head, since it is a later, uninvalidated leaf.
    """
    test_steps = []
    _fc_store, mega_store, anchor_block = _setup_store_and_mega_store(spec, state, test_steps)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    # A: FULL, extends the anchor
    signed_a = _build_full_child(spec, state, H_A(spec), parent_el_hash=state.latest_block_hash)
    yield from _add_full_block_and_envelope(
        spec, mega_store, state, signed_a, test_steps, status=PayloadStatusV1Status.VALID
    )

    # B: FULL, extends A -- added as SYNCING first (not yet known-invalid)
    signed_b = _build_full_child(spec, state, H_B(spec), parent_el_hash=H_A(spec))
    b_root = signed_b.message.hash_tree_root()
    b_state = state.copy()
    syncing_status = PayloadStatusV1(status=PayloadStatusV1Status.SYNCING)
    add_gloas_payload_info(test_steps, H_B(spec), syncing_status)
    yield from add_block(spec, mega_store.fc_store, signed_b, test_steps, is_optimistic=True)
    envelope_b = build_signed_execution_payload_envelope(spec, b_state, b_root, signed_b)
    yield from add_gloas_optimistic_envelope(
        spec, mega_store, envelope_b, test_steps, payload_status=syncing_status
    )

    # D: EMPTY child of B -- does not claim B as its parent, so it hangs off
    # B's Empty interpretation regardless of what happens to B's payload.
    signed_d = _build_empty_child(spec, state, parent_el_hash=H_A(spec))
    yield from add_block(spec, mega_store.fc_store, signed_d, test_steps, is_optimistic=True)
    d_root = signed_d.message.hash_tree_root()

    # Now the EL reports B's payload INVALID, LVH = A.
    invalid_status = PayloadStatusV1(
        status=PayloadStatusV1Status.INVALID,
        latest_valid_hash=H_A(spec),
        validation_error="invalid",
    )
    add_gloas_payload_info(test_steps, H_B(spec), invalid_status)
    yield from add_gloas_optimistic_envelope(
        spec, mega_store, envelope_b, test_steps, payload_status=invalid_status
    )

    full_b = spec.ForkChoiceNode(root=b_root, payload_status=spec.PAYLOAD_STATUS_FULL)
    empty_d = spec.ForkChoiceNode(root=d_root, payload_status=spec.PAYLOAD_STATUS_EMPTY)

    assert is_gloas_payload_invalidated(spec, mega_store, full_b)
    assert not is_gloas_payload_invalidated(spec, mega_store, empty_d)

    head = get_gloas_optimistic_head_node(spec, mega_store)
    assert head.root == d_root
    assert head.payload_status == spec.PAYLOAD_STATUS_EMPTY

    yield "steps", test_steps
