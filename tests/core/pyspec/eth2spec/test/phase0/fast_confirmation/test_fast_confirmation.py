import copy

from eth_utils import encode_hex

from eth2spec.test.helpers.state import transition_to

from eth2spec.test.context import MINIMAL, spec_state_test, with_altair_and_later, with_presets

from eth2spec.test.helpers.block import build_empty_block  # NOTE: build_empty_block (not _for_next_slot)
from eth2spec.test.helpers.state import state_transition_and_sign_block, transition_to
from eth2spec.test.helpers.fork_choice import add_block

from eth2spec.test.helpers.attestations import get_valid_attestations_for_block_at_slot

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

@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fast_confirm_an_epoch(spec, state):
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)
    for _ in range(spec.SLOTS_PER_EPOCH):
        fcr.next_slot_with_block_and_fast_confirmation()
        # Ensure head is confirmed
        assert store.confirmed_root == fcr.head()

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_invariants_monotone_and_canonical(spec, state):
    """    
    Validates two critical properties of the Fast Confirmation Rule:
    1. **Monotonicity**: Once a block at slot N is confirmed, all subsequent 
       confirmed blocks must be at slots > N (confirmation slot never decreases)
    2. **Canonicality**: The confirmation chain must be a proper subchain of 
       the head chain, ensuring confirmed blocks are always canonical
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)
    
    prev_confirmed_slot = store.blocks[store.confirmed_root].slot

    # Run through an entire epoch + 1 to cross epoch boundary
    # This tests reconfirmation and restart logic
    for _ in range(spec.SLOTS_PER_EPOCH + 1):
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

        head = fcr.head()
        confirmed = store.confirmed_root

        # Invariant 1: confirmed must be on canonical chain
        assert spec.is_ancestor(store, head, confirmed)

        # Invariant 2: confirmed slot monotonic unless reset to finalized
        confirmed_slot = store.blocks[confirmed].slot
        finalized = store.finalized_checkpoint.root
        finalized_slot = store.blocks[finalized].slot

        if confirmed != finalized:
            assert confirmed_slot >= prev_confirmed_slot, \
                f"Confirmed slot went backwards: {prev_confirmed_slot} -> {confirmed_slot}"
        else:
            # If reset happened, it must reset exactly to finalized
            assert confirmed_slot == finalized_slot, \
                f"Reset didn't go to finalized: {confirmed_slot} != {finalized_slot}"

        prev_confirmed_slot = confirmed_slot

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_reverts_to_finalized_when_confirmed_too_old_lower_participation(spec, state):
    """
    Goal:
      - Get confirmed_root into epoch 1 under full participation.
      - Then run low participation through epoch 2 so confirmed_root becomes "too old"
        only when we reach epoch 3 start.
      - At epoch 3 start: reset confirmed_root to finalized.
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    epoch1_start = 1 * S
    epoch2_start = 2 * S
    epoch3_start = 3 * S

    # 1) Full participation up to epoch 2 start.
    #    Ensure confirmed_root has advanced into epoch 1 (critical).
    while fcr.current_slot() < epoch2_start:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    assert fcr.current_slot() == epoch2_start
    assert spec.is_start_slot_at_epoch(fcr.current_slot())

    # Confirm we are indeed in the regime "confirmed is in epoch 1".
    assert store.confirmed_root != store.finalized_checkpoint.root
    assert spec.get_block_epoch(store, store.confirmed_root) == spec.Epoch(1)

    frozen_epoch1_confirmed = store.confirmed_root

    # 2) Epoch 2 with low participation: confirmed should not reset yet.
    low_participation = 60  # or 20/5; pick something clearly low for *confirmation* in your model

    while fcr.current_slot() < epoch3_start - 1:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=low_participation)

        # Must not reset before epoch 3 start.
        assert store.confirmed_root != store.finalized_checkpoint.root

        # It should still be from epoch 1 (it may or may not equal frozen_epoch1_confirmed).
        assert spec.get_block_epoch(store, store.confirmed_root) == spec.Epoch(1)

    # We are now at slot epoch3_start - 1, i.e., last slot before the boundary.
    assert fcr.current_slot() == epoch3_start - 1
    pre_boundary_confirmed = store.confirmed_root
    assert spec.get_block_epoch(store, pre_boundary_confirmed) == spec.Epoch(1)

    # 3) Cross into epoch 3 start: now it becomes "too old" and should reset.
    fcr.next_slot_with_block_and_fast_confirmation(participation_rate=low_participation)

    assert fcr.current_slot() == epoch3_start
    assert spec.is_start_slot_at_epoch(fcr.current_slot())

    current_epoch = spec.get_current_store_epoch(store)
    assert current_epoch == spec.Epoch(3)

    # Reset condition: pre-boundary confirmed was epoch 1, so 1 + 1 < 3.
    assert spec.get_block_epoch(store, pre_boundary_confirmed) + 1 < current_epoch

    # Must have reset to finalized at epoch 3 start.
    assert store.confirmed_root == store.finalized_checkpoint.root

    yield from fcr.get_test_artefacts()

# Confirmed blocks become non-canonical mid-epoch => revert to finalized 

@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_reverts_to_finalized_when_confirmed_not_canonical_mid_epoch(spec, state):
    """
    Test that confirmed_root resets to finalized when it becomes non-canonical due to a reorg.
    
    Scenario:
    --------
    1. Build a chain with confirmations advancing normally into epoch 2 (mid-epoch)
    2. Create a fork at block R with two competing children:
       - Block A: Initially becomes canonical (75% vote)
       - Block M: Competing sibling (same slot, same parent)
    3. Extend the A-chain: R → A → B → C → D
       - Confirmations advance onto the A-side chain
    4. Reorg by voting 100% for M (twice):
       - Head flips from D (A-side) to M (M-side)
       - Previously confirmed blocks on A-side become non-canonical
    
    When confirmed blocks become non-canonical, FCR must reset confirmed_root to 
    finalized_checkpoint.root rather than moving confirmations backward.
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    epoch2_start = 2 * S

    # Drive to epoch 2 start, then 2 slots into epoch 2 (mid-epoch)
    fcr.run_slots_with_blocks_and_fast_confirmation(
        epoch2_start - fcr.current_slot(), participation_rate=100
    )
    fcr.run_slots_with_blocks_and_fast_confirmation(2, participation_rate=100)
    assert fcr.current_slot() % S != 0  # mid-epoch

    # Build fork parent R at current slot; vote 100% for it; advance + apply + FCR
    r_root = fcr.add_and_apply_block(parent_root=fcr.head())
    fcr.attest_and_next_slot_with_fast_confirmation(block_root=r_root, participation_rate=100)

    # Now we are at the fork slot: create siblings A (canonical) and M (competing)
    fork_slot = fcr.current_slot()
    assert fork_slot % S != 0

    # Save "previous-slot" attestations that should be included in blocks at fork_slot
    prev_atts = list(fcr.attestation_pool)

    # Canonical child A at fork_slot
    a_root = fcr.add_and_apply_block(parent_root=r_root)

    # Competing sibling M at same parent/slot (manual build)
    parent_state = store.block_states[r_root].copy()
    competing_block = build_empty_block(spec, parent_state, fork_slot)
    for att in prev_atts:
        competing_block.body.attestations.append(att)
    competing_block.body.graffiti = b"i_love_ethereum".ljust(32, b"\x00")

    signed_m = state_transition_and_sign_block(spec, parent_state, competing_block)
    for artefact in add_block(spec, store, signed_m, fcr.test_steps):
        fcr.blockchain_artefacts.append(artefact)
    m_root = signed_m.message.hash_tree_root()

    # Slot fork_slot: 75% attest to A; advance + apply + FCR
    fcr.attest_and_next_slot_with_fast_confirmation(block_root=a_root, participation_rate=75)

    # Next slot: build B on A; attest 100% to B; advance + apply + FCR
    b_root = fcr.add_and_apply_block(parent_root=a_root)
    fcr.attest_and_next_slot_with_fast_confirmation(block_root=b_root, participation_rate=100)

    # By now we should have confirmed onto the A side
    assert spec.is_ancestor(store, store.confirmed_root, a_root), "Confirmed did not reach A"

    # snapshot what confirmed_root is *before* we start pushing 100%-to-M 
    confirmed_before_flip = store.confirmed_root
    assert confirmed_before_flip != store.finalized_checkpoint.root
    assert spec.is_ancestor(store, confirmed_before_flip, a_root)

    # Next slot: build C on B; attest 100% to M; advance + apply + FCR
    c_root = fcr.add_and_apply_block(parent_root=b_root)
    fcr.attest_and_next_slot_with_fast_confirmation(block_root=m_root, participation_rate=100)

    # Confirmed still on A side 
    assert spec.is_ancestor(store, store.confirmed_root, a_root)

    # Next slot: build D on C; attest 100% to M again; advance + apply + FCR
    _d_root = fcr.add_and_apply_block(parent_root=c_root)
    fcr.attest_and_next_slot_with_fast_confirmation(block_root=m_root, participation_rate=100)

    # Now: head should be on M side, and confirmed should have reset to finalized.
    # (FCR does not move confirmations backwards; it resets to finalized when confirmed becomes non-canonical.)
    head = fcr.head()
    assert spec.is_ancestor(store, head, m_root), "Head did not flip to M"
    assert store.confirmed_root == store.finalized_checkpoint.root, "Expected reset to finalized mid-epoch"
    assert store.confirmed_root != confirmed_before_flip  # we actually reset

    yield from fcr.get_test_artefacts()

# At an epoch boundary, if the previously confirmed chain cannot be re-confirmed
# under the new epoch anchor, FCR must reset confirmed_root to finalized
@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_reverts_to_finalized_when_reconfirmation_fails_at_epoch_start_due_to_late_equivocations(spec, state):
    """
    Test that confirmed_root resets to finalized when reconfirmation fails at an epoch boundary.

    Scenario:
    --------
    1. Build chain through epoch 2 with 100% participation
    - Confirmations advance into epoch 2
    - Ensure confirmed_root is NOT "too old" (to isolate reconfirmation failure)

    2. In the last 3 slots before epoch 3 boundary (slots s1, s2, s3):
    - Create competing forks: 6 blocks total (tip vs competing sibling per slot)
    - Vote 100% for the "tip" blocks each time
    - The tip blocks become one-confirmed under the previous epoch balance source

    3. At the epoch 3 boundary (before running FCR):
    - Late equivocation evidence arrives (3 attester slashings, 25% each)
    - This adds validators to store.equivocating_indices
    - Slashed validators' balances are now excluded from attestation weight

    4. Run epoch-start FCR logic (reconfirmation check):
    - FCR attempts to reconfirm the previous confirmed_root under the NEW balance source
    - With 75% of validators slashed, the tip blocks no longer meet the confirmation threshold
    - Reconfirmation fails

    When reconfirmation fails at an epoch boundary, confirmed_root must reset to 
    finalized_checkpoint.root rather than continuing with an under-supported chain.

    At each epoch boundary, FCR must verify that the previously confirmed chain still
    has sufficient support under the new epoch's balance source (which may exclude
    newly-slashed validators). If reconfirmation fails, FCR resets to the safe fallback.
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    epoch2_start = 2 * S
    epoch3_start = 3 * S

    # Drive to epoch 2 start
    while fcr.current_slot() < epoch2_start:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)
    assert fcr.current_slot() == epoch2_start
    assert spec.is_start_slot_at_epoch(fcr.current_slot())

    # Make sure confirmed_root is in epoch 2 (avoid "too old" disjunct at epoch 3 start)
    fcr.run_slots_with_blocks_and_fast_confirmation(2, participation_rate=100)
    assert spec.get_block_epoch(store, store.confirmed_root) == spec.Epoch(2)
    assert store.confirmed_root != store.finalized_checkpoint.root

    # Go to epoch3_start-3 so we can fork for 3 slots => 6 blocks total (tip/competing per slot)
    s1 = epoch3_start - 3
    s2 = epoch3_start - 2
    s3 = epoch3_start - 1
    while fcr.current_slot() < s1:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)
    assert fcr.current_slot() == s1

    tip_roots = []

    def fork_and_vote_tip_at_slot(slot, run_fcr_after_applying=True):
        """
        At `slot` (must equal fcr.current_slot()):
          - create sibling blocks tip vs competing at same parent/slot (6 blocks total across 3 slots)
          - vote 100% for tip
          - move to next slot, apply votes
          - optionally run FCR (we skip it at epoch boundary until after slashings)
        """
        assert fcr.current_slot() == slot

        fork_parent_root = fcr.head()
        prev_pool_atts = list(fcr.attestation_pool)

        # tip block
        fcr.attestation_pool = list(prev_pool_atts)
        tip_root = fcr.add_and_apply_block(
            parent_root=fork_parent_root, release_att_pool=True, graffiti=f"tip_{slot}"
        )

        # competing sibling block 
        fcr.attestation_pool = list(prev_pool_atts)
        _competing_root = fcr.add_and_apply_block(
            parent_root=fork_parent_root, release_att_pool=True, graffiti=f"competing_{slot}"
        )

        # vote for tip
        fcr.attest(block_root=tip_root, slot=slot, participation_rate=100)
        tip_roots.append(tip_root)

        # advance + apply votes
        fcr.next_slot()
        fcr.apply_attestations()
        fcr.attestation_pool = []

        if run_fcr_after_applying:
            fcr.run_fast_confirmation()

    # Slot s1: fork, vote for tip, advance, apply, run FCR
    fork_and_vote_tip_at_slot(s1, run_fcr_after_applying=True)
    assert fcr.current_slot() == s2

    # Slot s2: fork, vote for tip, advance, apply, run FCR
    fork_and_vote_tip_at_slot(s2, run_fcr_after_applying=True)
    assert fcr.current_slot() == s3

    # Slot s3: fork, vote for tip, advance into epoch 3, apply votes, but do not run FCR yet
    fork_and_vote_tip_at_slot(s3, run_fcr_after_applying=False)
    assert fcr.current_slot() == epoch3_start
    assert spec.is_start_slot_at_epoch(fcr.current_slot())

    # Before we inject slashings, the tips should be one-confirmed under the previous balance source.
    balance_source = spec.get_previous_balance_source(store)
    for i, root in enumerate(tip_roots):
        assert spec.is_one_confirmed(store, balance_source, root), f"tip[{i}] not one-confirmed pre-slashing"

    # Rule out the other reset disjuncts *before* reconfirmation:
    confirmed_before = store.confirmed_root
    head_before = fcr.head()
    assert confirmed_before != store.finalized_checkpoint.root
    assert spec.is_ancestor(store, head_before, confirmed_before)  # canonical
    assert spec.get_block_epoch(store, confirmed_before) >= spec.Epoch(2)  # not too old

    # Late equivocation evidence arrives at epoch boundary 
    slashings = []
    for _ in range(3):
        sl = fcr.apply_attester_slashing(slashing_percentage=25, slot=fcr.current_slot())
        slashings.append(sl)
        # Optional: explicit artefact for easier reproduction/debug
        fcr.blockchain_artefacts.append(("late_attester_slashing", sl))

    assert len(store.equivocating_indices) > 0

    # Now run epoch-start fast-confirmation logic (this is where reconfirmation is checked)
    fcr.run_fast_confirmation()

    # Expect reset-to-finalized due to reconfirmation failure at epoch boundary
    assert store.confirmed_root == store.finalized_checkpoint.root

    yield from fcr.get_test_artefacts()

@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_reset_to_finality_but_no_restart_to_gu_because_gu_too_old_epoch(spec, state):
    """
    Test that confirmed_root resets to finalized (not GU) when both are old at epoch boundary.

    Scenario:
    --------
    1. Epochs 0-1: 100% participation
    - Confirmations advance normally

    2. Epoch 2: Low participation (20%)
    - Confirmations stall and become "too old"
    - Neither finalized nor GU advance (low participation prevents justification/finalization)

    3. At epoch 3 start:
    - confirmed_root is 2+ epochs old → triggers reset
    - GU is also too old (GU.epoch + 1 < current_epoch) → blocks restart-to-GU
    - finalized is strictly older than GU at the block level (slot(finalized) < slot(GU))

    Expected Behavior:
    -----------------
    When confirmed_root must reset at an epoch boundary:
    1. First check: 
    - Reset to finalized checkpoint instead
    2. Second check: Can we restart to GU? 
    - NO: GU is too old, although slot(bcand=GF) < slot(\block(GU))

    Result: confirmed_root = finalized_checkpoint.root (NOT GU)
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    epoch2_start = 2 * S
    epoch3_start = 3 * S

    # Full participation through epochs 0 and 1, reaching epoch 2 start.
    saw_nonfinal_confirmed = False
    while fcr.current_slot() < epoch2_start:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

        if store.confirmed_root != store.finalized_checkpoint.root:
            saw_nonfinal_confirmed = True

    assert fcr.current_slot() == epoch2_start
    assert spec.is_start_slot_at_epoch(fcr.current_slot())
    assert saw_nonfinal_confirmed, "confirmed_root never advanced under full participation (unexpected)"

    # Epoch 2 with low participation.
    low_participation = 20

    while fcr.current_slot() < epoch3_start:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=low_participation)

        # Must not reset early (only care that reset happens at epoch 3 start).
        if fcr.current_slot() < epoch3_start:
            assert store.confirmed_root != store.finalized_checkpoint.root, (
                "confirmed_root reset before epoch 3 start (unexpected for this scenario)"
            )

    # Now at epoch 3 start.
    assert fcr.current_slot() == epoch3_start
    assert spec.is_start_slot_at_epoch(fcr.current_slot())

    current_epoch = spec.get_current_store_epoch(store)
    assert current_epoch == spec.Epoch(3)

    # current_epoch_observed_justified_checkpoint is set from unrealized_justified_checkpoint
    # at the start of the last slot of the previous epoch.
    gu = store.current_epoch_observed_justified_checkpoint

    # Finalized strictly older than GU at the block/slot level
    finalized_slot = store.blocks[store.finalized_checkpoint.root].slot
    gu_slot = store.blocks[gu.root].slot
    assert finalized_slot < gu_slot

    # GU is too old to allow restart-to-GU at epoch 3 start.
    assert gu.epoch + 1 < current_epoch, (
        f"GU not old enough to block restart: gu={int(gu.epoch)}, current={int(current_epoch)}"
    )

    # Reset-to-finalized must happen at epoch 3 start due to confirmed being "too old".
    assert store.confirmed_root == store.finalized_checkpoint.root

    yield from fcr.get_test_artefacts()

@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_epoch_start_resets_when_confirmed_not_descendant_of_gu(spec, state):
    """
    Goal (epoch-start guard):
      At the first slot of an epoch, if the stored confirmed candidate bcand is NOT
      a descendant of GU (i.e., bcand ⊁= GU, equivalently GU is not an ancestor of bcand),
      then the confirmation rule takes the reset branch and sets confirmed_root to finality.

    Note:
      In Gasper, GU at epoch e start is the epoch-(e-1) checkpoint (first block of epoch e-1).
      Therefore bcand ⊁= GU typically implies bcand is at most from epoch e-2 (or on a fork),
      so other epoch-start guards may also be true. This test checks the ancestry relation
      and the resulting reset, not disjunct isolation.
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    epoch2_start = 2 * S           # slot 16 in MINIMAL
    epoch3_start = 3 * S           # slot 24 in MINIMAL
    epoch2_last_slot = epoch3_start - 1  # slot 23

    def is_descendant(block_root, ancestor_root) -> bool:
        # Return True iff block_root is a descendant of (or equal to) ancestor_root in store.
        if block_root == ancestor_root:
            return True
        b = block_root
        while b != store.finalized_checkpoint.root:
            b_obj = store.blocks.get(b)
            if b_obj is None:
                return False
            parent = b_obj.parent_root
            if parent == ancestor_root:
                return True
            b = parent
        return False

    # Phase 1: build through epoch 1 with full participation so FFG state progresses normally.
    while fcr.current_slot() < epoch2_start:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    assert fcr.current_slot() == epoch2_start
    assert spec.is_start_slot_at_epoch(fcr.current_slot())

    # Phase 2: in epoch 2, push participation low enough that confirmations tend to stall / lag.
    # We specifically want to reach the *last slot of epoch 2* because that's when the
    # (current_epoch_observed_justified_checkpoint := unrealized_justified_checkpoint) latch runs.
    low_participation = 5
    while fcr.current_slot() < epoch2_last_slot:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=low_participation)

    assert fcr.current_slot() == epoch2_last_slot

    # At this point (slot 23 start already processed), the GU latch should have executed.
    gu = store.current_epoch_observed_justified_checkpoint
    assert gu.epoch >= spec.Epoch(1), (
        f"GU did not advance by the end of epoch 2 last-slot latch; got epoch={int(gu.epoch)}"
    )

    # Now we cross the epoch boundary manually so we can inspect PRE state before slot-start confirmation.
    # Build+attest for slot 23, advance to slot 24, apply attestations, but DO NOT run run_fast_confirmation yet.
    fcr.next_slot_with_block_and_apply_attestations(participation_rate=low_participation)
    assert fcr.current_slot() == epoch3_start
    assert spec.is_start_slot_at_epoch(fcr.current_slot())

    # Snapshot bcand before the epoch-start rule runs at slot 24.
    bcand_pre = store.confirmed_root
    gu_pre = store.current_epoch_observed_justified_checkpoint

    # GU is not an ancestor of bcand (i.e., bcand ⊁= GU).
    assert not is_descendant(bcand_pre, gu_pre.root), (
        "precondition failed: bcand_pre is still a descendant of GU; "
        "this run did not construct the bcand ⊁= GU configuration"
    )

    # Now run the epoch-start slot-start processing: should reset to finality.
    fcr.run_fast_confirmation()
    assert store.confirmed_root == store.finalized_checkpoint.root

    yield from fcr.get_test_artefacts()