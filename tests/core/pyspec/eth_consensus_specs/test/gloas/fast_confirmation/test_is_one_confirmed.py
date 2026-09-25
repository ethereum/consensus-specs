from eth_consensus_specs.test.context import (
    MINIMAL,
    never_bls,
    only_generator,
    spec_state_test,
    with_gloas_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.fast_confirmation import (
    FCRTest,
)

"""
Test is_one_confirmed for Gloas
"""


@only_generator("too slow")
@with_gloas_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
@never_bls
def test_is_one_confirmed_delayed_with_mixed_payload_votes_in_empty_slot(spec, state):
    """
    1. Build chain through epoch 1 with 100% participation.
    2. Empty slot: split attesters for the parent block into two groups:
       - half vote with payload_present=True (index=1)
       - half vote with payload_present=False (index=0)
    3. Propose block B after the empty slot.
    4. Accumulate two additional slots of attestations to B.
    5. Evaluate is_one_confirmed after the last accumulation slot.
    """
    fcr = FCRTest(spec, seed=1)
    store, fcr_store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # Build through epoch 1 to establish balance source
    fcr.run_slots_with_blocks_and_fast_confirmation(1 * S, participation_rate=100)

    parent_root = fcr.head_root()

    # --- Empty slot: split attesters between full and empty payload votes ---
    empty_slot = fcr.current_slot()
    attesters = spec.get_slot_committee(store, empty_slot)
    half = len(attesters) // 2
    full_voters = list(attesters)[:half]
    empty_voters = list(attesters)[half:]

    # Full payload votes
    fcr.attest(
        block_root=parent_root, slot=empty_slot, attester_indices=full_voters, payload_index=1
    )
    # Empty payload votes
    fcr.attest(
        block_root=parent_root, slot=empty_slot, attester_indices=empty_voters, payload_index=0
    )
    # Advance slot
    fcr.next_slot()
    fcr.run_fast_confirmation()

    # Verify latest messages reflect the split correctly
    for idx in full_voters:
        assert store.latest_messages[idx].root == parent_root
        assert store.latest_messages[idx].payload_present is True
    for idx in empty_voters:
        assert store.latest_messages[idx].root == parent_root
        assert store.latest_messages[idx].payload_present is False

    # --- Block B after the empty slot ---
    block_b = fcr.next_slot_with_block_and_fast_confirmation(
        parent_root=parent_root, participation_rate=100
    )

    # --- Accumulate more slots of support for B ---
    fcr.attest_and_next_slot_with_fast_confirmation(block_root=block_b, participation_rate=100)
    fcr.attest_and_next_slot_with_fast_confirmation(block_root=block_b, participation_rate=100)
    fcr.attest_and_next_slot_with_fast_confirmation(block_root=block_b, participation_rate=100)

    assert fcr_store.confirmed_root == block_b

    yield from fcr.get_test_artefacts()
