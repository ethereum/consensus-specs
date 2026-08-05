from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.attestations import (
    get_valid_attestations_at_slot,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block,
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.constants import MINIMAL
from eth_consensus_specs.test.helpers.fork_choice import (
    add_block,
    on_tick_and_append_step,
    output_store_checks,
    setup_finalized_store,
    tick_and_add_block,
    tick_and_run_on_attestation,
)
from eth_consensus_specs.test.helpers.state import (
    next_slot,
    state_transition_and_sign_block,
)


def _setup_boost_scenario(spec, state, adjacent, weak, sibling):
    """
    Build a finalized store, a weak/strong re-org target `parent`, an optional
    same-slot same-proposer `sibling`, then a boosted `block` on that parent.
    Returns after `block` is added while the store is still in `block`'s slot, so
    `store.proposer_boost_root == block`.

    `sibling` selects the sibling's timeliness:
      - None      : no sibling
      - "timely"  : added before the PTC deadline -> counts as an early equivocation
      - "late"    : added after the PTC deadline -> a head competitor that is NOT
                    an equivocation (fails the block_timeliness[PTC] filter)

    The sibling doubles as the head-flip competitor. With a weak (zero-weight)
    parent, parent-subtree and sibling tie on weight, so the head is decided by the
    fork-choice root tiebreak. The sibling is regenerated (via graffiti) until its
    root sorts ABOVE the parent's, so:
      - boost withheld -> tie -> sibling wins            -> head == sibling
      - boost applied  -> parent gains get_proposer_score -> head == block
    This flips `get_head`, the field clients actually check (weights are not
    universally validated).
    """
    store, state, test_steps = yield from setup_finalized_store(spec, state)

    # --- parent (the re-org target) ---
    parent_pre_state = state.copy()
    parent_block = build_empty_block_for_next_slot(spec, state)
    signed_parent = state_transition_and_sign_block(spec, state, parent_block)
    parent_root = signed_parent.message.hash_tree_root()
    # Timely add: ticks to parent.slot start, so it is PTC-timely and attestation-timely
    yield from tick_and_add_block(spec, store, signed_parent, test_steps)

    # --- same-slot same-proposer sibling (competitor, tuned to outrank on tiebreak) ---
    sibling_root = None
    if sibling is not None:
        # Orient the sibling root above the parent root so it wins the fork-choice
        # tiebreak on a weight tie. Graffiti only perturbs the block root; bounded
        # so a helper change can never spin forever.
        for graffiti_seed in range(256):
            sibling_state = parent_pre_state.copy()
            sibling_block = build_empty_block(spec, sibling_state, slot=parent_block.slot)
            sibling_block.body.graffiti = spec.Bytes32(graffiti_seed.to_bytes(32, "little"))
            signed_sibling = state_transition_and_sign_block(spec, sibling_state, sibling_block)
            sibling_root = signed_sibling.message.hash_tree_root()
            if sibling_root > parent_root:
                break
        else:
            raise AssertionError("could not orient sibling root above parent root")
        # Equivocation match depends on same proposer at the same slot; assert the
        # invariant so a future helper change cannot silently break discrimination.
        assert signed_sibling.message.proposer_index == signed_parent.message.proposer_index
        if sibling == "timely":
            # Added within the PTC window -> block_timeliness[PTC] True -> early equivocation
            yield from tick_and_add_block(spec, store, signed_sibling, test_steps)
        else:
            # Added past the PTC deadline -> block_timeliness[PTC] False -> NOT an
            # equivocation, but still a viable head competitor
            ptc_due_s = spec.get_payload_attestation_due_ms() // 1000
            late_time = (
                parent_block.slot * spec.config.SLOT_DURATION_MS // 1000
                + store.genesis_time
                + ptc_due_s
                + 1
            )
            on_tick_and_append_step(spec, store, late_time, test_steps)
            yield from add_block(spec, store, signed_sibling, test_steps)

    # --- make the parent strong if the row requires weak == False ---
    # Attest the whole parent-slot committee to the parent so its weight exceeds
    # calculate_committee_fraction(justified_state, REORG_HEAD_WEIGHT_THRESHOLD).
    # (When strong, the parent wins on weight regardless of boost, so this row is
    # not head-discriminating by construction; the should_apply assertion still
    # pins the branch.)
    if not weak:
        attestations = get_valid_attestations_at_slot(
            state, spec, slot_to_attest=parent_block.slot, beacon_block_root=parent_root
        )
        for attestation in attestations:
            yield from tick_and_run_on_attestation(spec, store, attestation, test_steps)

    # --- boosted block on the parent ---
    if not adjacent:
        # Leave parent.slot + 1 empty so the boosted block lands two slots after
        # the parent: parent.slot + 1 < block.slot -> "not adjacent" escape.
        next_slot(spec, state)

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    block_root = signed_block.message.hash_tree_root()
    # Timely add in the current slot -> sets store.proposer_boost_root = block
    yield from tick_and_add_block(spec, store, signed_block, test_steps)

    assert store.blocks[block_root].parent_root == parent_root
    assert store.proposer_boost_root == block_root

    roots = {"block": block_root, "parent": parent_root, "sibling": sibling_root}
    return store, state, roots, test_steps


def _assert_weight_reflects_boost(spec, store, block_root, boost_applied):
    """
    Extra (non-head) proof that the gate drives the weight: the boosted leaf's
    `get_weight` includes `get_proposer_score()` iff the boost is applied. This is
    emitted in `viable_for_head_roots_and_weights` for clients that validate it.
    """
    justified_state = store.checkpoint_states[store.justified_checkpoint]
    boost_node = spec.ForkChoiceNode(root=block_root, payload_status=spec.PAYLOAD_STATUS_PENDING)
    attestation_score = spec.get_attestation_score(store, boost_node, justified_state)
    proposer_score = spec.get_proposer_score(store)
    assert proposer_score > 0
    expected = attestation_score + (proposer_score if boost_applied else 0)
    assert spec.get_weight(store, boost_node) == expected


@with_gloas_and_later
@with_presets([MINIMAL], reason="too slow")
@spec_state_test
def test_should_apply_proposer_boost_parent_not_adjacent(spec, state):
    """
    Parent is two slots back and weak -> the "not adjacent" escape applies the
    boost. (has_equiv is not applicable: the equivocation filter looks for a block
    at block.slot - 1 with the parent's proposer, which does not exist when the
    parent is two slots back, and adjacency is checked first anyway.)

    Head-discriminating: a client that wrongly withholds here lets the weak parent
    tie with the higher-rooted sibling and flips the head to the sibling.
    """
    store, state, roots, test_steps = yield from _setup_boost_scenario(
        spec, state, adjacent=False, weak=True, sibling="late"
    )

    assert spec.should_apply_proposer_boost(store) is True
    _assert_weight_reflects_boost(spec, store, roots["block"], boost_applied=True)
    # Boost applied -> parent subtree outweighs the sibling -> head is the block
    assert spec.get_head(store).root == roots["block"]

    output_store_checks(spec, store, test_steps, with_viable_for_head_weights=True)
    yield "steps", test_steps


@with_gloas_and_later
@with_presets([MINIMAL], reason="too slow")
@spec_state_test
def test_should_apply_proposer_boost_parent_not_weak(spec, state):
    """
    Parent is adjacent and has an equivocation but is strongly supported -> the
    "not weak" escape applies the boost. NOT head-discriminating: a strong parent
    wins on weight regardless of boost, so no zero-weight tiebreak flips the head.
    The should_apply/weight assertions pin the branch at generation time.
    """
    store, state, roots, test_steps = yield from _setup_boost_scenario(
        spec, state, adjacent=True, weak=False, sibling="timely"
    )

    assert spec.should_apply_proposer_boost(store) is True
    _assert_weight_reflects_boost(spec, store, roots["block"], boost_applied=True)
    assert spec.get_head(store).root == roots["block"]

    output_store_checks(spec, store, test_steps, with_viable_for_head_weights=True)
    yield "steps", test_steps


@with_gloas_and_later
@with_presets([MINIMAL], reason="too slow")
@spec_state_test
def test_should_apply_proposer_boost_no_equivocation(spec, state):
    """
    Parent is adjacent and weak, with a same-slot same-proposer sibling that
    arrived AFTER the PTC deadline -> it fails the block_timeliness[PTC] filter, so
    the equivocation set is empty and the boost applies.

    Head-discriminating: a client that wrongly withholds here (treating the late
    sibling as an equivocation) flips the head to that sibling.
    """
    store, state, roots, test_steps = yield from _setup_boost_scenario(
        spec, state, adjacent=True, weak=True, sibling="late"
    )

    assert spec.should_apply_proposer_boost(store) is True
    _assert_weight_reflects_boost(spec, store, roots["block"], boost_applied=True)
    assert spec.get_head(store).root == roots["block"]

    output_store_checks(spec, store, test_steps, with_viable_for_head_weights=True)
    yield "steps", test_steps


@with_gloas_and_later
@with_presets([MINIMAL], reason="too slow")
@spec_state_test
def test_should_apply_proposer_boost_withheld(spec, state):
    """
    Parent is adjacent, weak, and has a PTC-timely equivocating sibling -> the
    boost is WITHHELD. The sibling was tuned to sort above the parent, so with the
    boost withheld the head flips to the sibling. A client that wrongly applies
    the boost (e.g. unconditional pre-gloas behavior) keeps the block as head and
    fails this vector on the `head` check.
    """
    store, state, roots, test_steps = yield from _setup_boost_scenario(
        spec, state, adjacent=True, weak=True, sibling="timely"
    )

    assert spec.should_apply_proposer_boost(store) is False
    _assert_weight_reflects_boost(spec, store, roots["block"], boost_applied=False)
    # Boost withheld -> weight tie broken by root -> head flips to the sibling
    assert spec.get_head(store).root == roots["sibling"]
    assert spec.get_head(store).root != roots["block"]

    output_store_checks(spec, store, test_steps, with_viable_for_head_weights=True)
    yield "steps", test_steps
