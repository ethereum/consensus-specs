"""
Gloas optimistic sync: the execution engine judges payloads, and fork choice removes the ``full``
node of an ``INVALIDATED`` payload with everything that descends from it.

``X-FULL`` and ``X-EMPTY`` are the two nodes of block ``X``. The payload a ``latestValidHash``
names is already ``VALID``, since the spec does not say whether naming it validates it.
"""

from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.gloas_optimistic_sync import (
    accepted,
    invalid,
    INVALIDATED,
    NOT_VALIDATED,
    start,
    syncing,
    VALID,
    valid,
)

# Far enough ahead that no payload decision is from the previous slot and no block is timely.
LATE_SLOT = 40


def _setup(spec, state, slot=LATE_SLOT):
    test_steps = []
    rig = start(spec, state, test_steps, slot)
    return rig, test_steps


def _add(rig, block, status):
    yield from rig.add_block(block, expect_valid=True)
    assert (yield from rig.add_envelope(block, status))


def _anchor(rig):
    yield "anchor_state", rig.anchor_state
    yield "anchor_block", rig.anchor_block


@with_gloas_and_later
@spec_state_test
def test_invalid_payload_keeps_its_empty_node(spec, state):
    """
    A -> B -> C on full nodes. C's payload is INVALID with the latest valid hash A, so B's payload
    is the first invalid one. B-FULL and C go, B-EMPTY becomes the head.
    """
    rig, test_steps = _setup(spec, state)
    yield from _anchor(rig)
    a = rig.build(None)
    b = rig.build(a, parent_full=True)
    c = rig.build(b, parent_full=True)
    yield from _add(rig, a, valid(a.block_hash))
    yield from _add(rig, b, syncing())
    rig.assert_head(b.root, spec.PAYLOAD_STATUS_FULL)
    yield from rig.add_block(c, expect_valid=True)
    yield from rig.add_envelope(c, invalid(a.block_hash))

    assert rig.payload_status(a.block_hash) == VALID
    assert rig.payload_status(b.block_hash) == INVALIDATED
    rig.assert_head(b.root, spec.PAYLOAD_STATUS_EMPTY)
    assert not rig.is_optimistic(rig.head())
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_latest_valid_hash_is_parent_payload(spec, state):
    """
    C's payload is INVALID with the latest valid hash of its own parent payload B. Only C's
    envelope is rejected, and C-EMPTY becomes the head.
    """
    rig, test_steps = _setup(spec, state)
    yield from _anchor(rig)
    a = rig.build(None)
    b = rig.build(a, parent_full=True)
    c = rig.build(b, parent_full=True)
    yield from _add(rig, a, syncing())
    yield from _add(rig, b, valid(b.block_hash))
    yield from rig.add_block(c, expect_valid=True)
    yield from rig.add_envelope(c, invalid(b.block_hash))

    assert rig.payload_status(b.block_hash) == VALID
    rig.assert_head(c.root, spec.PAYLOAD_STATUS_EMPTY)
    assert not rig.is_optimistic(rig.head())
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_invalidation_skips_empty_gap(spec, state):
    """
    A -> E1 -> E2 -> B: E1 extends A-FULL, E2 extends E1-EMPTY and B extends E2-EMPTY, so B's
    payload builds on A's. C on B-FULL is INVALID with the latest valid hash A. Only B's payload
    is invalid: E1 and E2 stay, and B-EMPTY becomes the head. A block on B-FULL is then rejected
    and a block on B-EMPTY is accepted.
    """
    rig, test_steps = _setup(spec, state)
    yield from _anchor(rig)
    a = rig.build(None)
    e1 = rig.build(a, parent_full=True)
    e2 = rig.build(e1)
    b = rig.build(e2)
    assert b.parent_block_hash == a.block_hash
    c = rig.build(b, parent_full=True)
    yield from _add(rig, a, valid(a.block_hash))
    yield from rig.add_block(e1, expect_valid=True)
    yield from rig.add_block(e2, expect_valid=True)
    yield from _add(rig, b, syncing())
    yield from rig.add_block(c, expect_valid=True)
    yield from rig.add_envelope(c, invalid(a.block_hash))

    assert rig.payload_status(b.block_hash) == INVALIDATED
    assert not rig.is_removed(rig.empty_node(e2.root))
    rig.assert_head(b.root, spec.PAYLOAD_STATUS_EMPTY)

    on_full = rig.build(b, parent_full=True, slot=c.slot + 1)
    yield from rig.add_block(on_full, expect_valid=False)
    on_empty = rig.build(b, slot=c.slot + 1, salt=b"empty")
    yield from rig.add_block(on_empty, expect_valid=True)
    rig.assert_head(on_empty.root, spec.PAYLOAD_STATUS_EMPTY)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_invalidation_spares_revealed_payload_in_gap(spec, state):
    """
    E1 extends A-FULL and reveals its own payload. B extends E1-EMPTY, so B's payload builds on
    A's, not on E1's. C on B-FULL is INVALID with the latest valid hash A. B's payload is invalid
    and E1's sibling payload stays NOT_VALIDATED, with E1-FULL the head.
    """
    rig, test_steps = _setup(spec, state)
    yield from _anchor(rig)
    a = rig.build(None)
    e1 = rig.build(a, parent_full=True)
    b = rig.build(e1)
    assert b.parent_block_hash == a.block_hash
    c = rig.build(b, parent_full=True)
    yield from _add(rig, a, valid(a.block_hash))
    yield from _add(rig, e1, syncing())
    yield from _add(rig, b, syncing())
    yield from rig.add_block(c, expect_valid=True)
    yield from rig.add_envelope(c, invalid(a.block_hash))

    assert rig.payload_status(e1.block_hash) == NOT_VALIDATED
    assert rig.payload_status(b.block_hash) == INVALIDATED
    rig.assert_head(e1.root, spec.PAYLOAD_STATUS_FULL)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_invalidation_spares_payload_on_empty_child(spec, state):
    """
    E extends B-EMPTY and reveals its own payload, which builds on A's. C on B-FULL is INVALID
    with the latest valid hash A. B's payload is invalid, E's payload stays NOT_VALIDATED, and
    E-FULL becomes the head.
    """
    rig, test_steps = _setup(spec, state)
    yield from _anchor(rig)
    a = rig.build(None)
    b = rig.build(a, parent_full=True)
    e = rig.build(b)
    c = rig.build(b, parent_full=True, slot=e.slot + 1)
    assert e.parent_block_hash == a.block_hash
    yield from _add(rig, a, valid(a.block_hash))
    yield from _add(rig, b, syncing())
    yield from _add(rig, e, syncing())
    yield from rig.add_block(c, expect_valid=True)
    yield from rig.add_envelope(c, invalid(a.block_hash))

    assert rig.payload_status(b.block_hash) == INVALIDATED
    assert rig.payload_status(e.block_hash) == NOT_VALIDATED
    rig.assert_head(e.root, spec.PAYLOAD_STATUS_FULL)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_invalidation_removes_every_full_branch(spec, state):
    """
    C1 and C2 both extend B-FULL, C1 imported first. C2 and D2 on C2-FULL reveal their own
    payloads. C1's payload is INVALID with the latest valid hash A. B's payload is invalid, so C2
    and D2 go too and their payloads are INVALIDATED. B-EMPTY becomes the head.
    """
    rig, test_steps = _setup(spec, state)
    yield from _anchor(rig)
    a = rig.build(None)
    b = rig.build(a, parent_full=True)
    c1 = rig.build(b, parent_full=True)
    c2 = rig.build(b, parent_full=True, slot=c1.slot + 1)
    d2 = rig.build(c2, parent_full=True)
    yield from _add(rig, a, valid(a.block_hash))
    yield from _add(rig, b, syncing())
    yield from rig.add_block(c1, expect_valid=True)
    yield from _add(rig, c2, syncing())
    yield from _add(rig, d2, syncing())
    yield from rig.add_envelope(c1, invalid(a.block_hash))

    assert rig.payload_status(b.block_hash) == INVALIDATED
    assert rig.payload_status(c2.block_hash) == INVALIDATED
    assert rig.payload_status(d2.block_hash) == INVALIDATED
    rig.assert_head(b.root, spec.PAYLOAD_STATUS_EMPTY)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_block_on_empty_node_of_removed_block(spec, state):
    """
    C on B-FULL is INVALID with the latest valid hash A, so C goes with B-FULL. C-EMPTY is
    removed too, so a block on it is rejected, although its bid builds on B's payload and not on
    C's.
    """
    rig, test_steps = _setup(spec, state)
    yield from _anchor(rig)
    a = rig.build(None)
    b = rig.build(a, parent_full=True)
    c = rig.build(b, parent_full=True)
    yield from _add(rig, a, valid(a.block_hash))
    yield from _add(rig, b, syncing())
    yield from rig.add_block(c, expect_valid=True)
    yield from rig.add_envelope(c, invalid(a.block_hash))

    on_empty = rig.build(c)
    assert on_empty.parent_block_hash == b.block_hash
    yield from rig.add_block(on_empty, expect_valid=False)
    rig.assert_head(b.root, spec.PAYLOAD_STATUS_EMPTY)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_valid_payload_validates_through_empty_gap(spec, state):
    """
    A and E1's payloads are NOT_VALIDATED. B extends E1-EMPTY, so its payload builds on A's.
    C on B-FULL is VALID: C, B and A become VALID, and E1's sibling payload stays NOT_VALIDATED.
    """
    rig, test_steps = _setup(spec, state)
    yield from _anchor(rig)
    a = rig.build(None)
    e1 = rig.build(a, parent_full=True)
    b = rig.build(e1)
    c = rig.build(b, parent_full=True)
    yield from _add(rig, a, syncing())
    yield from _add(rig, e1, accepted())
    yield from _add(rig, b, syncing())
    yield from _add(rig, c, valid(c.block_hash))

    assert rig.payload_status(a.block_hash) == VALID
    assert rig.payload_status(b.block_hash) == VALID
    assert rig.payload_status(c.block_hash) == VALID
    assert rig.payload_status(e1.block_hash) == NOT_VALIDATED
    yield "steps", test_steps


def _run_rejected_payload_only(spec, state, status):
    """
    C on B-FULL gets ``status``, which names no ancestor of C's payload. Only C's envelope is
    rejected.
    """
    rig, test_steps = _setup(spec, state)
    yield from _anchor(rig)
    a = rig.build(None)
    b = rig.build(a, parent_full=True)
    c = rig.build(b, parent_full=True)
    yield from _add(rig, a, syncing())
    yield from _add(rig, b, syncing())
    yield from rig.add_block(c, expect_valid=True)
    assert not (yield from rig.add_envelope(c, status))

    assert rig.payload_status(a.block_hash) == NOT_VALIDATED
    assert rig.payload_status(b.block_hash) == NOT_VALIDATED
    rig.assert_head(c.root, spec.PAYLOAD_STATUS_EMPTY)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_latest_valid_hash_unknown(spec, state):
    yield from _run_rejected_payload_only(spec, state, invalid(spec.Hash32(b"\x42" * 32)))


@with_gloas_and_later
@spec_state_test
def test_latest_valid_hash_null(spec, state):
    yield from _run_rejected_payload_only(spec, state, invalid(None))


@with_gloas_and_later
@spec_state_test
def test_latest_valid_hash_on_other_branch(spec, state):
    """
    B1 and B2 both extend A-FULL. C on B1-FULL is INVALID with the latest valid hash B2, which is
    not in C's payload chain. Only C's envelope is rejected.
    """
    rig, test_steps = _setup(spec, state)
    yield from _anchor(rig)
    a = rig.build(None)
    b1 = rig.build(a, parent_full=True, salt=b"b1")
    b2 = rig.build(a, parent_full=True, salt=b"b2")
    c = rig.build(b1, parent_full=True)
    yield from _add(rig, a, syncing())
    yield from _add(rig, b1, syncing())
    yield from _add(rig, b2, valid(b2.block_hash))
    yield from rig.add_block(c, expect_valid=True)
    yield from rig.add_envelope(c, invalid(b2.block_hash))

    assert rig.payload_status(b1.block_hash) == NOT_VALIDATED
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_latest_valid_hash_is_anchor_payload(spec, state):
    """
    A builds on the anchor's payload. C on B-FULL is INVALID with the latest valid hash of the
    anchor's payload, so A's payload is the first invalid one. A-FULL and everything on it go and
    A-EMPTY becomes the head.
    """
    rig, test_steps = _setup(spec, state)
    yield from _anchor(rig)
    a = rig.build(None)
    assert a.parent_block_hash == rig.anchor_block_hash
    b = rig.build(a, parent_full=True)
    c = rig.build(b, parent_full=True)
    yield from _add(rig, a, syncing())
    yield from _add(rig, b, syncing())
    yield from rig.add_block(c, expect_valid=True)
    yield from rig.add_envelope(c, invalid(rig.anchor_block_hash))

    assert rig.payload_status(a.block_hash) == INVALIDATED
    assert rig.payload_status(b.block_hash) == INVALIDATED
    rig.assert_head(a.root, spec.PAYLOAD_STATUS_EMPTY)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_invalid_payload_shared_by_equivocating_blocks(spec, state):
    """
    B1 and B2 are equivocating blocks at one slot that commit to the same payload. C on B1-FULL is
    INVALID with the latest valid hash A. The shared payload is invalid, so both B1-FULL and
    B2-FULL go.
    """
    rig, test_steps = _setup(spec, state)
    yield from _anchor(rig)
    a = rig.build(None)
    b1 = rig.build(a, parent_full=True, graffiti=b"b1")
    b2 = rig.build(a, parent_full=True, graffiti=b"b2")
    assert b1.root != b2.root
    assert b1.block_hash == b2.block_hash
    c = rig.build(b1, parent_full=True)
    yield from _add(rig, a, valid(a.block_hash))
    yield from _add(rig, b1, syncing())
    yield from _add(rig, b2, syncing())
    yield from rig.add_block(c, expect_valid=True)
    yield from rig.add_envelope(c, invalid(a.block_hash))

    assert rig.is_removed(rig.full_node(b1.root))
    assert rig.is_removed(rig.full_node(b2.root))
    head = rig.head()
    assert head.root in (b1.root, b2.root)
    assert head.payload_status == spec.PAYLOAD_STATUS_EMPTY
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_invalid_envelope_for_payload_imported_by_equivocating_block(spec, state):
    """
    B1 and B2 are equivocating blocks that commit to the same payload. B1's envelope is imported
    as NOT_VALIDATED and C extends B1-FULL. B2's envelope is INVALID with the latest valid hash A,
    so the shared payload is invalid: B1-FULL and C go.
    """
    rig, test_steps = _setup(spec, state)
    yield from _anchor(rig)
    a = rig.build(None)
    b1 = rig.build(a, parent_full=True, graffiti=b"b1")
    b2 = rig.build(a, parent_full=True, graffiti=b"b2")
    assert b1.block_hash == b2.block_hash
    c = rig.build(b1, parent_full=True)
    yield from _add(rig, a, valid(a.block_hash))
    yield from _add(rig, b1, syncing())
    yield from _add(rig, c, syncing())
    yield from rig.add_block(b2, expect_valid=True)
    yield from rig.add_envelope(b2, invalid(a.block_hash))

    assert rig.payload_status(b1.block_hash) == INVALIDATED
    assert rig.payload_status(c.block_hash) == INVALIDATED
    assert rig.is_removed(rig.full_node(b1.root))
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_invalidation_stops_at_latest_valid_hash(spec, state):
    """
    A -> B -> C -> D on full nodes. E on D-FULL is INVALID with the latest valid hash B. C and D's
    payloads are invalid and B's stays VALID. C-EMPTY becomes the head.
    """
    rig, test_steps = _setup(spec, state)
    yield from _anchor(rig)
    a = rig.build(None)
    b = rig.build(a, parent_full=True)
    c = rig.build(b, parent_full=True)
    d = rig.build(c, parent_full=True)
    e = rig.build(d, parent_full=True)
    yield from _add(rig, a, syncing())
    yield from _add(rig, b, valid(b.block_hash))
    for block in (c, d):
        yield from _add(rig, block, syncing())
    yield from rig.add_block(e, expect_valid=True)
    yield from rig.add_envelope(e, invalid(b.block_hash))

    assert rig.payload_status(b.block_hash) == VALID
    assert rig.payload_status(c.block_hash) == INVALIDATED
    assert rig.payload_status(d.block_hash) == INVALIDATED
    rig.assert_head(c.root, spec.PAYLOAD_STATUS_EMPTY)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_invalidation_removes_empty_descendants_below_first_invalid(spec, state):
    """
    B extends A-FULL, C extends B-FULL and D extends C-EMPTY, so D's payload builds on B's. E on
    D-FULL is INVALID with the latest valid hash A. B's payload is the first invalid one: C and D
    descend from B-FULL and go on both nodes, even though D extends C-EMPTY. B-EMPTY becomes the
    head.
    """
    rig, test_steps = _setup(spec, state)
    yield from _anchor(rig)
    a = rig.build(None)
    b = rig.build(a, parent_full=True)
    c = rig.build(b, parent_full=True)
    d = rig.build(c)
    assert d.parent_block_hash == b.block_hash
    e = rig.build(d, parent_full=True)
    yield from _add(rig, a, valid(a.block_hash))
    yield from _add(rig, b, syncing())
    yield from _add(rig, c, syncing())
    yield from _add(rig, d, syncing())
    yield from rig.add_block(e, expect_valid=True)
    yield from rig.add_envelope(e, invalid(a.block_hash))

    for block in (b, c, d):
        assert rig.payload_status(block.block_hash) == INVALIDATED
    assert rig.is_removed(rig.empty_node(d.root))
    rig.assert_head(b.root, spec.PAYLOAD_STATUS_EMPTY)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_envelope_on_invalidated_parent_payload(spec, state):
    """
    C1 and C2 extend B-FULL. C2's payload is INVALID with the latest valid hash A, so B's payload
    is invalid. C1's envelope arrives afterwards and builds on B's payload, so it is rejected.
    """
    rig, test_steps = _setup(spec, state)
    yield from _anchor(rig)
    a = rig.build(None)
    b = rig.build(a, parent_full=True)
    c1 = rig.build(b, parent_full=True, salt=b"c1")
    c2 = rig.build(b, parent_full=True, salt=b"c2")
    yield from _add(rig, a, valid(a.block_hash))
    yield from _add(rig, b, syncing())
    yield from rig.add_block(c1, expect_valid=True)
    yield from rig.add_block(c2, expect_valid=True)
    yield from rig.add_envelope(c2, invalid(a.block_hash))
    assert not (yield from rig.add_envelope(c1, syncing()))
    rig.assert_head(b.root, spec.PAYLOAD_STATUS_EMPTY)
    yield "steps", test_steps


def _setup_forkchoice_updated_response(spec, state, response_fn, a_valid=False):
    """
    A -> B on full nodes, B NOT_VALIDATED. The execution engine's response for B's payload
    changes to ``response_fn(rig, a, b)``. D on B-FULL becomes the head, its forkchoiceUpdated
    names B's payload, and the response applies.
    """
    rig, test_steps = _setup(spec, state)
    yield from _anchor(rig)
    a = rig.build(None)
    b = rig.build(a, parent_full=True)
    d = rig.build(b, parent_full=True)
    yield from _add(rig, a, valid(a.block_hash) if a_valid else syncing())
    yield from _add(rig, b, syncing())
    rig.set_payload_info(b.block_hash, response_fn(rig, a, b))
    yield from rig.add_block(d, expect_valid=True)
    return rig, test_steps, a, b, d


@with_gloas_and_later
@spec_state_test
def test_forkchoice_updated_invalid_on_empty_head(spec, state):
    """
    The forkchoiceUpdated for D-EMPTY names B's payload and gets INVALID with the latest valid
    hash A. B's payload is invalid, D goes, and B-EMPTY becomes the head.
    """
    rig, test_steps, a, b, _ = yield from _setup_forkchoice_updated_response(
        spec, state, lambda rig, a, b: invalid(a.block_hash), a_valid=True
    )
    assert rig.payload_status(a.block_hash) == VALID
    assert rig.payload_status(b.block_hash) == INVALIDATED
    rig.assert_head(b.root, spec.PAYLOAD_STATUS_EMPTY)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_forkchoice_updated_invalid_without_latest_valid_hash(spec, state):
    """
    The forkchoiceUpdated for D-EMPTY gets INVALID with a null latest valid hash. Only the head's
    payload, B's, is invalid.
    """
    rig, test_steps, a, b, _ = yield from _setup_forkchoice_updated_response(
        spec, state, lambda rig, a, b: invalid(None)
    )
    assert rig.payload_status(a.block_hash) == NOT_VALIDATED
    assert rig.payload_status(b.block_hash) == INVALIDATED
    rig.assert_head(b.root, spec.PAYLOAD_STATUS_EMPTY)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_forkchoice_updated_invalid_with_deeper_latest_valid_hash(spec, state):
    """
    The forkchoiceUpdated for D-EMPTY gets INVALID with the latest valid hash of the anchor's
    payload. A's payload is the first invalid one, so A-EMPTY becomes the head.
    """
    rig, test_steps, a, b, _ = yield from _setup_forkchoice_updated_response(
        spec, state, lambda rig, a, b: invalid(rig.anchor_block_hash)
    )
    assert rig.payload_status(a.block_hash) == INVALIDATED
    assert rig.payload_status(b.block_hash) == INVALIDATED
    rig.assert_head(a.root, spec.PAYLOAD_STATUS_EMPTY)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_forkchoice_updated_valid_validates_ancestors(spec, state):
    """
    The forkchoiceUpdated for D-EMPTY gets VALID for B's payload, so A and B become VALID.
    """
    rig, test_steps, a, b, d = yield from _setup_forkchoice_updated_response(
        spec, state, lambda rig, a, b: valid(b.block_hash)
    )
    assert rig.payload_status(a.block_hash) == VALID
    assert rig.payload_status(b.block_hash) == VALID
    rig.assert_head(d.root, spec.PAYLOAD_STATUS_EMPTY)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_forkchoice_updated_invalid_with_unknown_latest_valid_hash(spec, state):
    """
    The forkchoiceUpdated for D-EMPTY gets INVALID with a latest valid hash that names no known
    payload. Only the head's payload, B's, is invalid.
    """
    rig, test_steps, a, b, _ = yield from _setup_forkchoice_updated_response(
        spec, state, lambda rig, a, b: invalid(spec.Hash32(b"\x42" * 32))
    )
    assert rig.payload_status(a.block_hash) == NOT_VALIDATED
    assert rig.payload_status(b.block_hash) == INVALIDATED
    rig.assert_head(b.root, spec.PAYLOAD_STATUS_EMPTY)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_forkchoice_updated_invalid_with_latest_valid_hash_on_other_branch(spec, state):
    """
    X extends A-EMPTY and B extends A-FULL, so B's branch is the head. The forkchoiceUpdated for
    D-EMPTY gets INVALID with the latest valid hash X, which is not in B's payload chain. Only B's
    payload is invalid.
    """
    rig, test_steps = _setup(spec, state)
    yield from _anchor(rig)
    a = rig.build(None)
    x = rig.build(a, salt=b"x")
    b = rig.build(a, parent_full=True, salt=b"b")
    d = rig.build(b, parent_full=True)
    yield from _add(rig, a, syncing())
    yield from _add(rig, x, valid(x.block_hash))
    yield from _add(rig, b, syncing())
    rig.set_payload_info(b.block_hash, invalid(x.block_hash))
    yield from rig.add_block(d, expect_valid=True)

    assert rig.payload_status(a.block_hash) == NOT_VALIDATED
    assert rig.payload_status(b.block_hash) == INVALIDATED
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_votes_moved_off_removed_full_node(spec, state):
    """
    B and X extend A-FULL. In epoch 0 more validators vote for B-FULL than for X, then C's INVALID
    payload removes B-FULL, so its votes stop counting and X becomes the head although B-EMPTY is
    viable. In epoch 1 the B-FULL voters move to D on B-EMPTY, so D outweighs X and becomes the
    head.
    """
    rig, test_steps = _setup(spec, state, slot=6)
    yield from _anchor(rig)
    a = rig.build(None, slot=1)
    b = rig.build(a, parent_full=True, slot=2)
    x = rig.build(a, parent_full=True, slot=3)
    c = rig.build(b, parent_full=True, slot=5)
    d = rig.build(b, slot=7, salt=b"d")
    yield from _add(rig, a, valid(a.block_hash))
    yield from _add(rig, b, syncing())
    yield from rig.add_block(x, expect_valid=True)

    committee = rig.committee(b, 4)
    full_voters = committee[: len(committee) // 2 + 1]
    x_voters = committee[len(committee) // 2 + 1 :]
    assert len(full_voters) > len(x_voters) > 0
    yield from rig.add_attestation(b, 4, full_voters, payload_present=True)
    yield from rig.add_attestation(x, 4, x_voters, payload_present=False)
    yield from rig.add_block(c, expect_valid=True)
    yield from rig.add_envelope(c, invalid(a.block_hash))
    rig.assert_head(x.root, spec.PAYLOAD_STATUS_EMPTY)

    rig.tick(2 * spec.SLOTS_PER_EPOCH)
    yield from rig.add_block(d, expect_valid=True)
    yield from rig.add_votes(d, 1, full_voters, payload_present=False)
    rig.assert_head(d.root, spec.PAYLOAD_STATUS_EMPTY)
    yield "steps", test_steps
