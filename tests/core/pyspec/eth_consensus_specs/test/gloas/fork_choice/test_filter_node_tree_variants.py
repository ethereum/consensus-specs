from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.attestations import get_valid_attestation
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.constants import MINIMAL
from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    add_execution_payload,
    on_tick_and_append_step,
    output_head_check,
    setup_finalized_store,
    tick_and_add_block,
    tick_and_run_on_attestation,
)
from eth_consensus_specs.test.helpers.state import (
    next_slots,
    state_transition_and_sign_block,
)


@with_gloas_and_later
@with_presets([MINIMAL], reason="too slow")
@spec_state_test
def test_get_head_prunes_childless_unviable_full_variant(spec, state):
    """
    Reproduces issue #5496: a childless FULL payload-status variant of a block
    that fails the FFG test must not be returned by get_head.

    Block B is built on the justified checkpoint from a fork of its state, so
    its voting source is stale and B fails the FFG test. K builds on EMPTY(B)
    and pulls up justification to the store's justified checkpoint (set below,
    as in the issue's example), so EMPTY(B) is viable. FULL(B) exists because
    B's envelope is delivered, but it is childless and never passes the FFG
    test, so get_head must not return it.
    """
    store, _, test_steps = yield from setup_finalized_store(spec, state)

    justified_epoch = store.justified_checkpoint.epoch
    assert store.finalized_checkpoint.epoch == justified_epoch - 1

    justified_state = store.block_states[store.justified_checkpoint.root]

    # B is the first block of epoch `justified_epoch + 1` on a fork of the
    # justified state. The fork has no on-chain votes, so B's voting source is
    # stale and B fails the FFG test.
    b_slot = spec.compute_start_slot_at_epoch(justified_epoch + 1)
    fork_state = justified_state.copy()
    next_slots(spec, fork_state, b_slot - fork_state.slot - 1)
    b_block = build_empty_block_for_next_slot(spec, fork_state)
    assert b_block.slot == b_slot
    signed_b = state_transition_and_sign_block(spec, fork_state, b_block)
    b_root = signed_b.message.hash_tree_root()
    yield from tick_and_add_block(spec, store, signed_b, test_steps)

    # Deliver B's envelope so the FULL(B) variant exists
    b_state = store.block_states[b_root]
    envelope = build_signed_execution_payload_envelope(spec, b_state, b_root, signed_b)
    yield from add_execution_payload(spec, store, envelope, test_steps)
    assert spec.is_payload_verified(store, b_root)

    # Tick to the start of the next epoch so attestations for B's epoch can be
    # processed
    k_slot = spec.compute_start_slot_at_epoch(justified_epoch + 2)
    on_tick_and_append_step(
        spec, store, store.genesis_time + k_slot * spec.config.SLOT_DURATION_MS // 1000, test_steps
    )

    # Attest B's FULL variant with all committees of B's epoch, so the B branch
    # outweighs the main chain in the LMD-GHOST walk
    committees_per_slot = spec.get_committee_count_per_slot(b_state, justified_epoch + 1)
    for slot in range(b_slot + 1, k_slot):
        att_state = b_state.copy()
        next_slots(spec, att_state, slot - att_state.slot)
        for index in range(committees_per_slot):
            attestation = get_valid_attestation(
                spec,
                att_state,
                slot=slot,
                index=index,
                payload_index=1,
                beacon_block_root=b_root,
                signed=True,
            )
            yield from tick_and_run_on_attestation(spec, store, attestation, test_steps)

    # K builds on EMPTY(B) at the start of the next epoch
    k_state = b_state.copy()
    next_slots(spec, k_state, k_slot - k_state.slot - 1)
    k_block = build_empty_block_for_next_slot(spec, k_state)
    assert k_block.slot == k_slot
    signed_k = state_transition_and_sign_block(spec, k_state, k_block)
    k_root = signed_k.message.hash_tree_root()
    yield from tick_and_add_block(spec, store, signed_k, test_steps)
    # K must claim an EMPTY parent for the B branch to stay viable
    assert spec.get_parent_payload_status(store, signed_k.message) == spec.PAYLOAD_STATUS_EMPTY

    # Simulate K's chain having pulled up justification to the store's justified
    # checkpoint, while B's justification remains stale
    store.unrealized_justifications[k_root] = store.justified_checkpoint

    # Advance to the next epoch so that B is more than two epochs behind the
    # voting source required by the FFG test
    next_epoch_slot = spec.compute_start_slot_at_epoch(justified_epoch + 3)
    on_tick_and_append_step(
        spec,
        store,
        store.genesis_time + next_epoch_slot * spec.config.SLOT_DURATION_MS // 1000,
        test_steps,
    )

    full_b_variant = (b_root, spec.PAYLOAD_STATUS_FULL)
    empty_b_variant = (b_root, spec.PAYLOAD_STATUS_EMPTY)

    # B fails the FFG test while K passes it
    assert spec.get_voting_source(store, b_root).epoch + 2 < spec.get_current_store_epoch(store)
    assert spec.get_voting_source(store, b_root).epoch != store.justified_checkpoint.epoch
    assert spec.get_voting_source(store, k_root).epoch == store.justified_checkpoint.epoch

    # The childless FULL(B) variant is not viable and must not be the head
    head = spec.get_head(store)
    assert (head.root, head.payload_status) != full_b_variant
    assert head.root == k_root
    assert head.payload_status == spec.PAYLOAD_STATUS_EMPTY

    filtered_tree = spec.get_filtered_node_tree(store)
    assert full_b_variant not in filtered_tree
    assert empty_b_variant in filtered_tree

    output_head_check(spec, store, test_steps)
    yield "steps", test_steps
