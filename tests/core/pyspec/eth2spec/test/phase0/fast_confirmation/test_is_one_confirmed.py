from eth2spec.test.context import (
    default_activation_threshold,
    default_balances,
    MINIMAL,
    single_phase,
    spec_test,
    with_altair_and_later,
    with_custom_state,
    with_presets,
)
from eth2spec.test.helpers.fast_confirmation import (
    FCRTest,
)

"""
Test is_one_confirmed
"""


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_is_one_confirmed_passes_with_full_participation(spec, state):
    """
    Test that is_one_confirmed returns True for a block with 100% participation.

    1. Build chain through epoch 1 with 100% participation to establish balance source
    2. Propose block B with 100% attestations, advance, apply, run FCR
    3. Call is_one_confirmed directly on B and verify it returns True
    4. Inspect the individual terms of the inequality
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # Build through epoch 1 to establish balance source
    fcr.run_slots_with_blocks_and_fast_confirmation(2 * S, participation_rate=100)

    # Propose block B with 100% attestations — helper handles the full flow
    block_b = fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    # Verify no empty slot gap (consecutive slots)
    block = store.blocks[block_b]
    parent_block = store.blocks[block.parent_root]
    assert parent_block.slot + 1 == block.slot, "Test requires consecutive slots"

    # Get balance source
    balance_source = spec.get_current_balance_source(store)

    # Call is_one_confirmed directly
    assert spec.is_one_confirmed(store, balance_source, block_b), (
        "is_one_confirmed should return True with 100% participation"
    )

    # Inspect the individual terms of the inequality
    current_slot = spec.get_current_slot(store)
    support = spec.get_attestation_score(store, block_b, balance_source)
    proposer_score = spec.compute_proposer_score(balance_source)
    total_active_balance = spec.get_total_active_balance(balance_source)
    maximum_support = spec.estimate_committee_weight_between_slots(
        total_active_balance, spec.Slot(parent_block.slot + 1), spec.Slot(current_slot - 1)
    )
    support_discount = spec.get_support_discount(store, balance_source, block_b)
    adversarial_weight = spec.get_adversarial_weight(store, balance_source, block_b)

    # No empty slots → discount must be 0
    assert support_discount == 0, f"Expected 0 discount, got {support_discount}"

    # Verify the integer inequality directly
    lhs = 2 * support + support_discount
    rhs = maximum_support + proposer_score + 2 * adversarial_weight
    assert lhs > rhs, f"Inequality failed: lhs={lhs} vs rhs={rhs}"

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_is_one_confirmed_fails_with_low_participation(spec, state):
    """
    Test that is_one_confirmed returns False when participation is too low.

    With β = 25%, the threshold is roughly 75-80% of committee weight.
    At 50% participation, the observed support is insufficient to rule out
    a competing sibling overtaking the branch.

    1. Build chain through epoch 1 with 100% participation to establish balance source
    2. Propose block B with only 50% attestations, advance, apply, run FCR
    3. Call is_one_confirmed directly on B and verify it returns False
    4. Inspect the terms to verify support is insufficient
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # Build through epoch 1 to establish balance source
    fcr.run_slots_with_blocks_and_fast_confirmation(2 * S, participation_rate=100)

    # Propose block B with only 50% attestations
    block_b = fcr.next_slot_with_block_and_fast_confirmation(participation_rate=50)

    # Verify no empty slot gap
    block = store.blocks[block_b]
    parent_block = store.blocks[block.parent_root]
    assert parent_block.slot + 1 == block.slot, "Test requires consecutive slots"

    # Get balance source
    balance_source = spec.get_current_balance_source(store)

    # Call is_one_confirmed directly
    assert not spec.is_one_confirmed(store, balance_source, block_b), (
        "is_one_confirmed should return False with only 50% participation"
    )

    # Inspect the individual terms
    current_slot = spec.get_current_slot(store)
    support = spec.get_attestation_score(store, block_b, balance_source)
    proposer_score = spec.compute_proposer_score(balance_source)
    total_active_balance = spec.get_total_active_balance(balance_source)
    maximum_support = spec.estimate_committee_weight_between_slots(
        total_active_balance, spec.Slot(parent_block.slot + 1), spec.Slot(current_slot - 1)
    )
    support_discount = spec.get_support_discount(store, balance_source, block_b)
    adversarial_weight = spec.get_adversarial_weight(store, balance_source, block_b)

    # Verify the inequality does NOT hold
    lhs = 2 * support + support_discount
    rhs = maximum_support + proposer_score + 2 * adversarial_weight
    assert lhs <= rhs, f"Inequality unexpectedly holds: lhs={lhs} > rhs={rhs} at 50% participation"

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_is_one_confirmed_slashing_supporters_does_not_hurt(spec, state):
    """
    Test that slashing validators who voted for block B does not break is_one_confirmed.

    Equivocators are proven Byzantine. Once identified:
    - Their votes are excluded from B's support
    - Their weight is subtracted from the adversarial budget

    For validators whose latest message points to B, the support loss and
    adversarial budget reduction largely cancel out. With sufficient initial
    margin (100% participation), slashing a moderate fraction does not flip
    is_one_confirmed from True to False.

    1. Build block B with 100% participation (is_one_confirmed = True)
    2. Slash 20% of validators randomly (at 100% participation, all are supporters)
    3. Verify is_one_confirmed remains True
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # Build through epoch 1 to establish balance source
    fcr.run_slots_with_blocks_and_fast_confirmation(2 * S, participation_rate=100)

    # Block B with 100% participation
    block_b = fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    balance_source = spec.get_current_balance_source(store)
    assert spec.is_one_confirmed(store, balance_source, block_b), (
        "Precondition: is_one_confirmed should be True at 100%"
    )

    # Slash 20% randomly — at 100% participation, these are all supporters of B
    fcr.apply_attester_slashing(slashing_percentage=20, slot=fcr.current_slot())
    assert len(store.equivocating_indices) > 0, "Slashing had no effect"

    # is_one_confirmed must still hold
    assert spec.is_one_confirmed(store, balance_source, block_b), (
        "Slashing supporters should not break is_one_confirmed"
    )

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_is_one_confirmed_slashing_non_supporters_helps(spec, state):
    """
    Test that slashing non-supporting equivocators helps is_one_confirmed pass.

    When an equivocator's latest message does not point to block B:
    - B's support is unchanged (they weren't counting toward it)
    - Their weight is subtracted from the adversarial budget

    In the inequality: LHS unchanged, RHS drops → strictly helps.

    This models the scenario where adversarial validators are detected as
    equivocators and their latest visible vote was for a competing branch.
    Detecting them reduces the adversarial budget without affecting B's
    observed support, making the safety threshold easier to meet.

    With 64 validators in MINIMAL (8 per committee), at 85% participation
    is_one_confirmed fails. Slashing non-supporters reduces the adversarial
    budget enough to flip the predicate to True.

    1. Build block B with 85% participation (is_one_confirmed = False)
    2. Identify validators whose latest message does not point to B
    3. Slash those non-supporters
    4. Verify support unchanged, adversarial budget decreased, is_one_confirmed flips to True
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # Build through epoch 1 to establish balance source
    fcr.run_slots_with_blocks_and_fast_confirmation(2 * S, participation_rate=100)

    # Block B with 85% participation — fails is_one_confirmed
    block_b = fcr.next_slot_with_block_and_fast_confirmation(participation_rate=85)

    block = store.blocks[block_b]
    parent_block = store.blocks[block.parent_root]
    assert parent_block.slot + 1 == block.slot, "Test requires consecutive slots"

    balance_source = spec.get_current_balance_source(store)

    support_before = spec.get_attestation_score(store, block_b, balance_source)
    adversarial_weight_before = spec.get_adversarial_weight(store, balance_source, block_b)

    assert not spec.is_one_confirmed(store, balance_source, block_b), (
        "Precondition: is_one_confirmed should fail at 85% participation"
    )

    # Identify non-supporters: validators whose latest message does not point to B
    non_supporters = [
        i
        for i in range(len(state.validators))
        if (i not in store.latest_messages or store.latest_messages[i].root != block_b)
        and not state.validators[i].slashed
        and i not in store.equivocating_indices
    ]
    assert len(non_supporters) > 0, "Need non-supporters to slash"

    # Slash non-supporters
    slash_count = min(len(non_supporters), len(state.validators) * 25 // 100)
    fcr.apply_attester_slashing(
        slashing_indices=non_supporters[:slash_count],
        slot=fcr.current_slot(),
    )

    # Support must be unchanged — we only slashed non-voters for B
    support_after = spec.get_attestation_score(store, block_b, balance_source)
    assert support_after == support_before, (
        f"Support changed after slashing non-voters: {support_before} -> {support_after}"
    )

    # Adversarial budget must have decreased
    adversarial_weight_after = spec.get_adversarial_weight(store, balance_source, block_b)
    assert adversarial_weight_after < adversarial_weight_before, (
        f"Adversarial weight should decrease: {adversarial_weight_before} -> {adversarial_weight_after}"
    )

    # is_one_confirmed should now pass
    assert spec.is_one_confirmed(store, balance_source, block_b), (
        "Slashing non-supporters should help is_one_confirmed pass"
    )

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_is_one_confirmed_empty_slot_discount(spec, state):
    """
    Test that the empty slot discount correctly compensates for honest
    validators in skipped-slot committees whose latest vote points to the parent.

    When a block skips slots, honest validators in the skipped committees
    voted for parent(b) — their votes can't help any sibling of b.
    The discount credits this weight (minus a conservative β correction)
    to the LHS of the safety inequality.

    This test verifies:
    1. A block in a consecutive slot has support_discount == 0
    2. A block after an empty slot has support_discount > 0
    3. The discount value equals parent support in empty slots minus
       adversarial weight in those slots (matching the formula)
    4. With accumulation, the discount contributes to is_one_confirmed
       passing for the gapped block
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # Build through epoch 1 to establish balance source
    fcr.run_slots_with_blocks_and_fast_confirmation(2 * S, participation_rate=100)

    # Block A: consecutive slot (no empty slot gap)
    block_a = fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    block_a_data = store.blocks[block_a]
    parent_a = store.blocks[block_a_data.parent_root]
    assert parent_a.slot + 1 == block_a_data.slot, "Block A must be consecutive"

    balance_source = spec.get_current_balance_source(store)

    discount_a = spec.get_support_discount(store, balance_source, block_a)
    assert discount_a == 0, f"Block A discount should be 0, got {discount_a}"

    assert spec.is_one_confirmed(store, balance_source, block_a), (
        "Block A should pass is_one_confirmed (consecutive, 100%)"
    )

    # Block B: after an empty slot gap
    head_before_empty = fcr.head()

    # Empty slot: attest 100% to current head, advance, apply, run FCR — no block
    fcr.attest_and_next_slot_with_fast_confirmation(
        block_root=head_before_empty, participation_rate=100
    )

    # Propose block after the gap
    block_b = fcr.next_slot_with_block_and_fast_confirmation(
        parent_root=head_before_empty, participation_rate=100
    )

    block_b_data = store.blocks[block_b]
    parent_b = store.blocks[block_b_data.parent_root]
    assert parent_b.slot + 1 < block_b_data.slot, "Block B must have an empty slot gap"

    balance_source = spec.get_current_balance_source(store)

    # Discount must be positive
    discount_b = int(spec.get_support_discount(store, balance_source, block_b))
    assert discount_b > 0, "Block B discount should be > 0 with empty slot gap"

    # Verify the discount matches the formula:
    # discount = parent_support_in_empty_slots - adversarial_weight_in_empty_slots
    parent_support_in_empty = int(
        spec.get_block_support_between_slots(
            store,
            balance_source,
            block_b_data.parent_root,
            spec.Slot(parent_b.slot + 1),
            spec.Slot(block_b_data.slot - 1),
        )
    )
    adv_in_empty = int(
        spec.compute_adversarial_weight(
            store,
            balance_source,
            spec.Slot(parent_b.slot + 1),
            spec.Slot(block_b_data.slot - 1),
        )
    )
    assert discount_b == parent_support_in_empty - adv_in_empty, (
        f"Discount should equal parent_support - adv in empty slots: "
        f"discount={discount_b}, parent_support={parent_support_in_empty}, adv={adv_in_empty}"
    )

    # Accumulate support to show discount contributes to confirmation
    # At this point is_one_confirmed fails for block_b (one slot + empty slot gap).
    # Accumulate one more slot of attestations to dilute proposer boost.
    fcr.attest_and_next_slot_with_fast_confirmation(block_root=block_b, participation_rate=100)

    balance_source = spec.get_current_balance_source(store)

    # With accumulation, block_b should now pass
    assert spec.is_one_confirmed(store, balance_source, block_b), (
        "Block B should pass is_one_confirmed after accumulation"
    )

    # Verify the discount is still contributing: without it, would it still pass?
    current_slot = spec.get_current_slot(store)
    support_b = int(spec.get_attestation_score(store, block_b, balance_source))
    proposer_b = int(spec.compute_proposer_score(balance_source))
    total_active_balance = spec.get_total_active_balance(balance_source)
    max_support_b = int(
        spec.estimate_committee_weight_between_slots(
            total_active_balance, spec.Slot(parent_b.slot + 1), spec.Slot(current_slot - 1)
        )
    )
    adv_b = int(spec.get_adversarial_weight(store, balance_source, block_b))
    discount_b_now = int(spec.get_support_discount(store, balance_source, block_b))

    rhs_b = max_support_b + proposer_b + 2 * adv_b
    margin_without_discount = 2 * support_b - rhs_b
    margin_with_discount = 2 * support_b + discount_b_now - rhs_b

    assert margin_with_discount > margin_without_discount, (
        "Discount should still improve the margin after accumulation"
    )

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_is_one_confirmed_support_accumulates_over_slots(spec, state):
    """
    Test that is_one_confirmed can flip from False to True as more slots
    of attestation support accumulate.

    The safety inequality compares support against maximum_support. Both
    grow as more slots elapse after parent(b), but proposer_score is a
    fixed constant that doesn't scale with slots. As more committees
    accumulate, the relative impact of proposer_score shrinks, making
    confirmation easier.

    At 85% participation with one slot of support, is_one_confirmed fails
    because the proposer boost is ~40% of one committee's weight. With
    two slots, the boost drops to ~20% of the total budget, and the
    accumulated support is enough to satisfy the inequality.

    1. Build block B with 85% attestations, advance to s+1, run FCR
    2. At s+1: verify is_one_confirmed fails (one slot, boost too large)
    3. Attest 85% to B at s+1, advance to s+2, run FCR
    4. At s+2: verify is_one_confirmed passes (boost diluted by second committee)
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # Build through epoch 1 to establish balance source
    fcr.run_slots_with_blocks_and_fast_confirmation(2 * S, participation_rate=100)

    # Propose block B with 85% participation
    block_b = fcr.next_slot_with_block_and_fast_confirmation(participation_rate=85)

    balance_source = spec.get_current_balance_source(store)

    # At s+1: one slot of support — fails due to proposer boost
    assert not spec.is_one_confirmed(store, balance_source, block_b), (
        "is_one_confirmed should fail with one slot of support at 85%"
    )

    # Attest 85% to B at s+1, advance to s+2, apply, run FCR — no new block
    fcr.attest_and_next_slot_with_fast_confirmation(block_root=block_b, participation_rate=85)

    balance_source = spec.get_current_balance_source(store)

    # At s+2: two slots of support — boost diluted, passes
    assert spec.is_one_confirmed(store, balance_source, block_b), (
        "is_one_confirmed should pass with two slots of accumulated support"
    )

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_is_one_confirmed_epoch_crossing_block(spec, state):
    """
    Test is_one_confirmed for a block that crosses an epoch boundary
    (parent in epoch e-1, block in epoch e).

    When a block crosses an epoch boundary, get_adversarial_weight uses
    the first slot of the block's epoch as the start slot instead of the
    block's own slot. This widens the adversarial budget range to include
    earlier slots in the epoch.

    1. Build a chain to the last slot of epoch 1
    2. Propose a block at the second slot of epoch 2 with parent at last slot of epoch 1
       (crossing the epoch boundary, leaving first slot of epoch 2 empty)
    3. Verify the block crosses an epoch boundary
    4. Verify adversarial weight uses epoch start, not block slot
    5. Check is_one_confirmed with accumulated support
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # Build through most of epoch 1 with full participation
    fcr.run_slots_with_blocks_and_fast_confirmation(2 * S - 1, participation_rate=100)

    # We're now at the last slot of epoch 1
    parent_root = fcr.head()

    # Skip the first slot of epoch 2 (empty slot at epoch boundary)
    fcr.attest_and_next_slot_with_fast_confirmation(block_root=parent_root, participation_rate=100)

    # Propose block at second slot of epoch 2 — crosses epoch boundary
    block_b = fcr.next_slot_with_block_and_fast_confirmation(
        parent_root=parent_root, participation_rate=100
    )

    block = store.blocks[block_b]
    block_epoch = spec.get_block_epoch(store, block_b)
    parent_block = store.blocks[block.parent_root]
    parent_block_epoch = spec.compute_epoch_at_slot(parent_block.slot)

    # Verify epoch crossing
    assert block_epoch > parent_block_epoch, (
        f"Block must cross epoch boundary: block_epoch={block_epoch}, parent_epoch={parent_block_epoch}"
    )

    balance_source = spec.get_current_balance_source(store)

    # Verify adversarial weight uses epoch start as start_slot
    current_slot = spec.get_current_slot(store)
    epoch_start = spec.compute_start_slot_at_epoch(block_epoch)

    # Adversarial weight with epoch start (what the code does for epoch-crossing)
    adv_from_epoch_start = int(
        spec.compute_adversarial_weight(
            store, balance_source, epoch_start, spec.Slot(current_slot - 1)
        )
    )

    # Adversarial weight with block slot (what the code would do without epoch-crossing logic)
    adv_from_block_slot = int(
        spec.compute_adversarial_weight(
            store, balance_source, block.slot, spec.Slot(current_slot - 1)
        )
    )

    # The actual adversarial weight used by is_one_confirmed
    adv_actual = int(spec.get_adversarial_weight(store, balance_source, block_b))

    # For epoch-crossing block, adversarial weight must use epoch start
    assert adv_actual == adv_from_epoch_start, (
        f"Adversarial weight should use epoch start: actual={adv_actual}, "
        f"from_epoch_start={adv_from_epoch_start}, from_block_slot={adv_from_block_slot}"
    )

    # Epoch start range is wider → adversarial budget should be >= block slot range
    assert adv_from_epoch_start >= adv_from_block_slot, (
        f"Epoch start range should give >= adversarial weight: "
        f"epoch_start={adv_from_epoch_start}, block_slot={adv_from_block_slot}"
    )

    # Accumulate more support to get is_one_confirmed to pass
    fcr.attest_and_next_slot_with_fast_confirmation(block_root=block_b, participation_rate=100)

    balance_source = spec.get_current_balance_source(store)

    assert spec.is_one_confirmed(store, balance_source, block_b), (
        "Epoch-crossing block should pass is_one_confirmed with accumulated support"
    )

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_is_one_confirmed_fails_with_competing_branch(spec, state):
    """
    Test that is_one_confirmed fails when support is split between competing blocks.

    This models the core adversarial scenario: two sibling blocks B1 and B2
    (both children of the same parent) compete for attestation support.
    When support is split, neither block can accumulate enough to satisfy
    the safety inequality.

    The test verifies the split is the cause by accumulating additional
    support exclusively for B1. After enough slots, B1 passes while B2
    (with no additional votes) remains failed — demonstrating that the
    fork is resolved in B1's favor once honest validators consolidate.

    1. Build chain to establish balance source
    2. Create two competing blocks B1 and B2 from the same parent
    3. Split attestations: ~50% vote for B1, ~50% for B2
    4. Verify is_one_confirmed fails for both blocks
    5. Accumulate support for B1 only until it passes
    6. Verify B2 still fails throughout
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # Build through epoch 1 to establish balance source
    fcr.run_slots_with_blocks_and_fast_confirmation(2 * S, participation_rate=100)

    parent_root = fcr.head()

    # Create two competing sibling blocks from the same parent
    block_b1 = fcr.add_and_apply_block(parent_root=parent_root)
    block_b2 = fcr.add_and_apply_block(parent_root=parent_root)

    assert store.blocks[block_b1].parent_root == store.blocks[block_b2].parent_root, (
        "B1 and B2 must be siblings (same parent)"
    )

    # Split attestations: ~50% for B1, ~50% for B2
    fcr.attest(block_root=block_b1, participation_rate=50, pool_and_disseminate=True)
    fcr.attest(block_root=block_b2, participation_rate=50, pool_and_disseminate=True)

    fcr.next_slot()
    fcr.run_fast_confirmation()

    balance_source = spec.get_current_balance_source(store)

    # Both must have some support
    support_b1 = int(spec.get_attestation_score(store, block_b1, balance_source))
    support_b2 = int(spec.get_attestation_score(store, block_b2, balance_source))
    assert support_b1 > 0, "B1 should have some support"
    assert support_b2 > 0, "B2 should have some support"

    # Neither passes with split support
    assert not spec.is_one_confirmed(store, balance_source, block_b1), (
        "B1 should fail is_one_confirmed with split support"
    )
    assert not spec.is_one_confirmed(store, balance_source, block_b2), (
        "B2 should fail is_one_confirmed with split support"
    )

    # Accumulate support for B1 only — first additional slot
    fcr.attest_and_next_slot_with_fast_confirmation(block_root=block_b1, participation_rate=100)

    balance_source = spec.get_current_balance_source(store)

    # B1 still fails after one additional slot (initial split deficit too large)
    assert not spec.is_one_confirmed(store, balance_source, block_b1), (
        "B1 should still fail after one additional slot of support"
    )
    assert not spec.is_one_confirmed(store, balance_source, block_b2), (
        "B2 should still fail with no additional support"
    )

    # Accumulate support for B1 only — second additional slot
    fcr.attest_and_next_slot_with_fast_confirmation(block_root=block_b1, participation_rate=100)

    balance_source = spec.get_current_balance_source(store)

    # B1 now passes — enough accumulated support overcomes the split deficit
    assert spec.is_one_confirmed(store, balance_source, block_b1), (
        "B1 should pass is_one_confirmed after sufficient accumulation"
    )

    # B2 still fails — it never got additional support
    assert not spec.is_one_confirmed(store, balance_source, block_b2), (
        "B2 should still fail with no additional support"
    )

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_is_confirmed_chain_safe_passes_full_chain(spec, state):
    """
    Test that is_confirmed_chain_safe returns True when the entire chain
    from the anchor checkpoint to the confirmed block has full participation.

    is_confirmed_chain_safe walks from the confirmed block back to the
    checkpoint block, checking is_one_confirmed on every block along the
    way. If any block fails, the whole chain fails. With 100% participation,
    every block should individually pass, and the chain check should succeed.

    This test verifies:
    1. confirmed_root advances beyond genesis (FCR confirms blocks)
    2. The confirmed chain has multiple blocks
    3. is_confirmed_chain_safe returns True for the confirmed root
    4. Every individual block in the chain passes is_one_confirmed
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # Build through epoch 2 with 100% participation
    fcr.run_slots_with_blocks_and_fast_confirmation(3 * S, participation_rate=100)

    confirmed_root = store.confirmed_root

    # Confirmed root must have advanced beyond genesis
    assert confirmed_root != state.latest_block_header.parent_root, (
        "confirmed_root should have advanced beyond genesis"
    )

    # Verify is_confirmed_chain_safe passes
    assert spec.is_confirmed_chain_safe(store, confirmed_root), (
        "is_confirmed_chain_safe should pass with 100% participation"
    )

    # Walk the chain from confirmed_root back toward the anchor and verify
    # each block individually passes is_one_confirmed
    balance_source = spec.get_previous_balance_source(store)
    block_root = confirmed_root
    anchor_root = store.previous_epoch_observed_justified_checkpoint.root
    blocks_checked = 0

    while block_root != anchor_root:
        block = store.blocks[block_root]
        assert spec.is_one_confirmed(store, balance_source, block_root), (
            f"Block at slot {block.slot} should individually pass is_one_confirmed"
        )
        block_root = block.parent_root
        blocks_checked += 1

    # The chain should have multiple blocks (non-trivial walk)
    assert blocks_checked > 1, f"Expected multi-block chain, only checked {blocks_checked} blocks"

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_is_one_confirmed_epoch_crossing_adversarial_range_matters(spec, state):
    """
    Implementation-level test for epoch-crossing adversarial range.

    When a block crosses an epoch boundary (parent in epoch e-1, block in
    epoch e) with an empty slot at epoch start, the adversarial budget must
    include that empty slot's committee. If the implementation incorrectly
    used block.slot instead of epoch_start, the adversarial budget would be
    smaller and the block could be incorrectly confirmed.

    This test engineers a scenario where the margin between correct and
    incorrect adversarial ranges determines whether is_one_confirmed passes:
    - With correct range (from epoch_start): FAILS (margin = -102.4B)
    - With wrong range (from block.slot): WOULD PASS (margin = +25.6B)
    - The difference is exactly one committee's adversarial contribution (128B)

    The test verifies through confirmed_root that the epoch-crossing block
    is NOT confirmed — proving the implementation correctly uses the wider
    adversarial range.

    Setup:
    1. Build chain through epoch 1 with 100% participation
    2. Skip first slot of epoch 2 (empty)
    3. Propose block at slot 17 with parent at slot 15 (epoch crossing)
    4. Accumulate 85% support for 2 slots
    5. Verify block is NOT confirmed (correct adversarial range prevents it)
    6. Verify it WOULD be confirmed with the narrower (incorrect) range
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # Build through epoch 1 with full participation
    fcr.run_slots_with_blocks_and_fast_confirmation(2 * S, participation_rate=100)

    parent_root = fcr.head()

    # Skip first slot of epoch 2 (empty) — attest to parent
    fcr.attest_and_next_slot_with_fast_confirmation(block_root=parent_root, participation_rate=100)

    # Propose epoch-crossing block at slot 17 with parent at slot 15
    block_b = fcr.next_slot_with_block_and_fast_confirmation(
        parent_root=parent_root, participation_rate=85
    )

    # Verify epoch crossing
    block = store.blocks[block_b]
    block_epoch = spec.get_block_epoch(store, block_b)
    parent_block = store.blocks[block.parent_root]
    parent_epoch = spec.compute_epoch_at_slot(parent_block.slot)
    assert block_epoch > parent_epoch, (
        f"Block must cross epoch boundary: block_epoch={block_epoch}, parent_epoch={parent_epoch}"
    )

    # Verify there is a gap (empty slot between epoch_start and block.slot)
    epoch_start = spec.compute_start_slot_at_epoch(block_epoch)
    assert block.slot > epoch_start, (
        f"Block must be after epoch start to have a gap: block.slot={block.slot}, epoch_start={epoch_start}"
    )

    # Accumulate support at 85% for 2 more slots
    for _ in range(2):
        fcr.attest_and_next_slot_with_fast_confirmation(block_root=block_b, participation_rate=85)

    balance_source = spec.get_current_balance_source(store)
    current_slot = spec.get_current_slot(store)
    total_active_balance = spec.get_total_active_balance(balance_source)

    # Block should NOT be confirmed (correct adversarial range)
    assert not spec.is_one_confirmed(store, balance_source, block_b), (
        "Epoch-crossing block should NOT be confirmed with correct adversarial range"
    )

    # Verify the epoch-crossing logic is what prevents confirmation:
    # compute margins with correct vs wrong adversarial range
    adv_correct = int(
        spec.compute_adversarial_weight(
            store, balance_source, epoch_start, spec.Slot(current_slot - 1)
        )
    )
    adv_wrong = int(
        spec.compute_adversarial_weight(
            store, balance_source, block.slot, spec.Slot(current_slot - 1)
        )
    )

    support = int(spec.get_attestation_score(store, block_b, balance_source))
    max_support = int(
        spec.estimate_committee_weight_between_slots(
            total_active_balance,
            spec.Slot(parent_block.slot + 1),
            spec.Slot(current_slot - 1),
        )
    )
    proposer = int(spec.compute_proposer_score(balance_source))
    discount = int(spec.get_support_discount(store, balance_source, block_b))

    lhs = 2 * support + discount
    rhs_correct = max_support + proposer + 2 * adv_correct
    rhs_wrong = max_support + proposer + 2 * adv_wrong

    # With correct range: fails (negative margin)
    assert lhs <= rhs_correct, (
        f"Should fail with correct adversarial range: lhs={lhs}, rhs={rhs_correct}"
    )

    # With wrong range: would pass (positive margin)
    assert lhs > rhs_wrong, (
        f"Would pass with incorrect adversarial range: lhs={lhs}, rhs={rhs_wrong}"
    )

    # confirmed_root should NOT include block_b
    assert store.confirmed_root != block_b, (
        "confirmed_root should not advance to the epoch-crossing block"
    )

    yield from fcr.get_test_artefacts()
