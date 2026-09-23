from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block,
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.constants import MINIMAL
from eth_consensus_specs.test.helpers.fork_choice import (
    add_proposer_slashing,
    output_store_checks,
    setup_finalized_store,
    tick_and_add_block,
    tick_store_to_slot,
)
from eth_consensus_specs.test.helpers.proposer_slashings import (
    get_proposer_slashing_for_blocks,
)
from eth_consensus_specs.test.helpers.state import (
    state_transition_and_sign_block,
)


def _setup_equivocating_head(spec, state, with_slashing):
    """
    Build a finalized store with a weak, timely `head` and a same-slot
    same-proposer sibling that is never imported, then move into the next slot so
    the proposer boost has worn off. The equivocation is only visible to the
    store when `with_slashing` delivers the ProposerSlashing.

    The head is added on time, so `is_head_late` is False and the ordinary re-org
    branch of `get_proposer_head` cannot fire. Only the equivocation branch can.
    """
    store, state, test_steps = yield from setup_finalized_store(spec, state)

    head_pre_state = state.copy()
    head_block = build_empty_block_for_next_slot(spec, state)
    signed_head = state_transition_and_sign_block(spec, state, head_block)
    head_root = signed_head.message.hash_tree_root()
    yield from tick_and_add_block(spec, store, signed_head, test_steps)

    sibling_state = head_pre_state.copy()
    sibling_block = build_empty_block(spec, sibling_state, slot=head_block.slot)
    sibling_block.body.graffiti = spec.Bytes32(b"\x2a" * 32)
    signed_sibling = state_transition_and_sign_block(spec, sibling_state, sibling_block)
    assert signed_sibling.message.proposer_index == signed_head.message.proposer_index

    # Ticking into the proposal slot also clears the proposer boost
    proposal_slot = spec.Slot(head_block.slot + 1)
    tick_store_to_slot(spec, store, proposal_slot, test_steps)
    assert store.proposer_boost_root != head_root

    if with_slashing:
        proposer_slashing = get_proposer_slashing_for_blocks(
            spec, state, signed_head, signed_sibling
        )
        yield from add_proposer_slashing(spec, store, proposer_slashing, test_steps)

    assert signed_sibling.message.hash_tree_root() not in store.blocks
    assert spec.is_head_weak(store, head_root)
    assert not spec.is_head_late(store, head_root)

    return store, signed_head.message, proposal_slot, test_steps


@with_gloas_and_later
@with_presets([MINIMAL], reason="too slow")
@spec_state_test
def test_get_proposer_head_equivocation_from_slashing(spec, state):
    """
    The head equivocated, but the equivocating block was never imported: only the
    ProposerSlashing proves it. The proposer re-orgs the weak head by building on
    its parent. A client that derives equivocations from its block tree alone
    finds none here and builds on the head instead.
    """
    store, head_block, proposal_slot, test_steps = yield from _setup_equivocating_head(
        spec, state, with_slashing=True
    )
    head_root = head_block.hash_tree_root()

    head_node = spec.get_head(store)
    assert head_node.root == head_root
    assert spec.is_proposer_equivocation(store, head_root)

    parent_node = spec.ForkChoiceNode(
        root=head_block.parent_root,
        payload_status=spec.get_parent_payload_status(store, head_block),
    )
    assert spec.get_proposer_head(store, head_node, proposal_slot) == parent_node

    output_store_checks(spec, store, test_steps)
    yield "steps", test_steps


@with_gloas_and_later
@with_presets([MINIMAL], reason="too slow")
@spec_state_test
def test_get_proposer_head_no_equivocation(spec, state):
    """
    Same scenario without the ProposerSlashing: the store has no evidence of an
    equivocation, so the proposer builds on the head.
    """
    store, head_block, proposal_slot, test_steps = yield from _setup_equivocating_head(
        spec, state, with_slashing=False
    )
    head_root = head_block.hash_tree_root()

    head_node = spec.get_head(store)
    assert head_node.root == head_root
    assert not spec.is_proposer_equivocation(store, head_root)
    assert spec.get_proposer_head(store, head_node, proposal_slot) == head_node

    output_store_checks(spec, store, test_steps)
    yield "steps", test_steps
