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
    4. Accumulate three additional slots of attestations to B.
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


def _run_empty_slot_discount_with_pending_and_payload_votes(spec, state, parent_full):
    fcr = FCRTest(spec, seed=1)
    store, fcr_store = fcr.initialize(state)

    # Put P at the end of epoch 0 so some of its own-slot voters are also
    # assigned to the two skipped slots in epoch 1 and can retain PENDING votes.
    parent_slot = spec.Slot(spec.SLOTS_PER_EPOCH - 1)
    fcr.run_slots_with_blocks_and_fast_confirmation(parent_slot, participation_rate=100)
    # Both cases need P's payload available to accept FULL attestations.
    parent_root = fcr.add_and_apply_block()

    pending_voters = set(spec.get_slot_committee(store, parent_slot))
    fcr.attest(block_root=parent_root, attester_indices=pending_voters)
    fcr.next_slot()
    fcr.run_fast_confirmation()

    skipped_voters = set()
    for slot in range(fcr.current_slot(), fcr.current_slot() + 2):
        skipped_voters.update(spec.get_slot_committee(store, spec.Slot(slot)))
    pending_voters &= skipped_voters
    voters = sorted(skipped_voters - pending_voters)
    # Give the selected branch a majority, with the pending votes deciding
    # confirmation after five slots of votes for B.
    split = 3 * len(voters) // 4
    selected_voters = set(voters[:split])
    opposite_voters = set(voters[split:])
    full_voters = selected_voters if parent_full else opposite_voters
    empty_voters = opposite_voters if parent_full else selected_voters
    for _ in range(2):
        fcr.attest(block_root=parent_root, attester_indices=full_voters, payload_index=1)
        fcr.attest(block_root=parent_root, attester_indices=empty_voters, payload_index=0)
        fcr.next_slot()
        fcr.run_fast_confirmation()

    # Explicitly select the payload branch, independently of availability and
    # voting weight. Leave the latest messages unchanged when adding B.
    block_b = fcr.add_and_apply_block(
        parent_root=parent_root, include_atts=False, parent_full=parent_full
    )
    expected_status = spec.PAYLOAD_STATUS_FULL if parent_full else spec.PAYLOAD_STATUS_EMPTY
    assert spec.get_parent_payload_status(store, store.blocks[block_b]) == expected_status
    assert spec.get_ancestor(
        store, spec.get_node_for_root(block_b), parent_slot
    ) == spec.ForkChoiceNode(root=parent_root, payload_status=expected_status)

    for voters, status in (
        (pending_voters, spec.PAYLOAD_STATUS_PENDING),
        (full_voters, spec.PAYLOAD_STATUS_FULL),
        (empty_voters, spec.PAYLOAD_STATUS_EMPTY),
    ):
        assert voters
        for index in voters:
            assert spec.get_supported_node(
                store, store.latest_messages[index]
            ) == spec.ForkChoiceNode(root=parent_root, payload_status=status)

    balance_source = spec.get_current_balance_source(fcr_store)
    weights = [
        sum(balance_source.validators[index].effective_balance for index in voters)
        for voters in (pending_voters, full_voters, empty_voters)
    ]
    pending_weight, full_weight, empty_weight = weights
    assert full_weight != empty_weight
    adversarial_weight = spec.compute_adversarial_weight(
        store, balance_source, spec.Slot(parent_slot + 1), spec.Slot(fcr.current_slot() - 1)
    )
    selected_weight = full_weight if parent_full else empty_weight
    expected_discount = pending_weight + selected_weight - adversarial_weight
    # Keep the result above the zero floor so missing pending support is visible.
    assert expected_discount > pending_weight > 0
    assert not spec.is_one_confirmed(store, balance_source, block_b)
    for _ in range(4):
        fcr.attest_and_next_slot_with_fast_confirmation(block_root=block_b)
        assert not spec.is_one_confirmed(store, balance_source, block_b)
        assert fcr_store.confirmed_root != block_b

    fcr.attest(block_root=block_b)
    fcr.next_slot()

    support = spec.get_attestation_score(store, spec.get_node_for_root(block_b), balance_source)
    maximum_support = spec.compute_committee_weight_between_slots(
        store, balance_source, spec.Slot(parent_slot + 1), spec.Slot(fcr.current_slot() - 1)
    )
    proposer_score = spec.compute_proposer_score(balance_source)
    adversarial_weight_b = spec.get_adversarial_weight(store, balance_source, block_b)
    # The old rule counted only FULL/EMPTY parent support, omitting PENDING.
    old_discount = max(selected_weight - adversarial_weight, 0)
    old_threshold = (
        maximum_support + proposer_score + 2 * adversarial_weight_b - old_discount
    ) // 2
    assert support <= old_threshold
    assert spec.is_one_confirmed(store, balance_source, block_b)
    fcr.run_fast_confirmation()
    assert fcr_store.confirmed_root == block_b
    assert (
        spec.compute_empty_slot_support_discount(store, balance_source, block_b)
        == expected_discount
    )

    yield from fcr.get_test_artefacts()


@with_gloas_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
@never_bls
def test_empty_slot_discount_pending_and_full_parent(spec, state):
    yield from _run_empty_slot_discount_with_pending_and_payload_votes(
        spec, state, parent_full=True
    )


@with_gloas_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
@never_bls
def test_empty_slot_discount_pending_and_empty_parent(spec, state):
    yield from _run_empty_slot_discount_with_pending_and_payload_votes(
        spec, state, parent_full=False
    )
