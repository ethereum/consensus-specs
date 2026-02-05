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


"""
Test on revert to finality
"""

@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_no_reset_when_confirmed_exactly_one_epoch_old(spec, state):
    """
    Test that confirmed_root does NOT reset when it's exactly one epoch old.

    The "too old" guard is: epoch(bcand) + 1 < current_epoch
    When epoch(bcand) + 1 == current_epoch, this is FALSE and no reset should occur.

    1. Epochs 0-1: 100% participation, confirmations advance into epoch 1
    2. Epoch 2: Low participation, confirmations stall in epoch 1
    3. Throughout epoch 2: confirmed stays in epoch 1, but should NOT reset
       because epoch(bcand=1) + 1 = 2 == current_epoch (not < current_epoch)
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    epoch2_start = 2 * S
    epoch3_start = 3 * S

    # Full participation through epoch 1
    while fcr.current_slot() < epoch2_start:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    assert fcr.current_slot() == epoch2_start
    
    # Confirm we have confirmations in epoch 1
    confirmed_at_epoch2_start = store.confirmed_root
    assert confirmed_at_epoch2_start != store.finalized_checkpoint.root
    assert spec.get_block_epoch(store, confirmed_at_epoch2_start) == spec.Epoch(1)

    # Epoch 2 with low participation - confirmations should stall but NOT reset
    low_participation = 15

    while fcr.current_slot() < epoch3_start - 1:  # Stop before crossing into epoch 3
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=low_participation)

        current_epoch = spec.get_current_store_epoch(store)
        confirmed_epoch = spec.get_block_epoch(store, store.confirmed_root)

        # Key invariant: throughout epoch 2, confirmed is in epoch 1
        # epoch(bcand=1) + 1 = 2 == current_epoch=2, so NOT "too old"
        assert current_epoch == spec.Epoch(2)
        assert confirmed_epoch == spec.Epoch(1)
        
        # Should NOT have reset to finalized
        assert store.confirmed_root != store.finalized_checkpoint.root, \
            f"Unexpected reset at slot {fcr.current_slot()}: " \
            f"confirmed_epoch={confirmed_epoch}, current_epoch={current_epoch}"

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_no_reset_at_epoch_boundary_with_full_participation(spec, state):
    """
    Test that confirmed_root does NOT reset when crossing epoch boundaries
    under healthy conditions (full participation).

      
    1. Run multiple epochs with 100% participation
    2. At each epoch boundary, verify:
       - confirmed_root is NOT reset to finalized
       - confirmed_root continues advancing
       - Reconfirmation passes (is_confirmed_chain_safe returns True)
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # Track confirmed across epoch boundaries
    confirmed_at_boundaries = []

    for epoch in range(4):
        epoch_start = epoch * S
        next_epoch_start = (epoch + 1) * S

        # Run through the epoch
        while fcr.current_slot() < next_epoch_start:
            fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

        # At epoch boundary
        if epoch > 0:  # Skip genesis epoch
            current_confirmed = store.confirmed_root
            confirmed_epoch = spec.get_block_epoch(store, current_confirmed)
            
            confirmed_at_boundaries.append({
                'at_epoch': epoch + 1,
                'confirmed_epoch': int(confirmed_epoch),
                'confirmed_root': current_confirmed,
                'is_finalized': current_confirmed == store.finalized_checkpoint.root,
            })

            # Should NOT have reset to finalized under full participation
            assert current_confirmed != store.finalized_checkpoint.root, \
                f"Unexpected reset at epoch {epoch + 1} boundary"

    # Verify confirmations advanced over time
    confirmed_epochs = [b['confirmed_epoch'] for b in confirmed_at_boundaries]
    assert confirmed_epochs[-1] > confirmed_epochs[0], \
        f"Confirmations did not advance: {confirmed_epochs}"

    yield from fcr.get_test_artefacts()

@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
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


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_reverts_to_finalized_when_confirmed_not_canonical_at_epoch_boundary(spec, state):
    """
    Test that confirmed_root resets when it becomes non-canonical at an epoch boundary.

    1. Build chain into epoch 1 with full participation, confirmations advancing
    2. At slot 10, create fork point R
    3. Create siblings at slot 11:
       - Branch A: canonical initially, confirmations advance here
       - Branch M: competing sibling
    4. Extend A-side briefly to get confirmations on A-side
    5. Switch to extending M-side with 100% votes until epoch boundary
    6. At epoch 2 start (slot 16):
       - Head flips from A-side to M-side
       - Previously confirmed blocks on A-side become non-canonical
    7. FCR should reset confirmed_root to finalized
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    epoch2_start = 2 * S

    # Build chain into epoch 1 with full participation
    while fcr.current_slot() < S + 2:  # slot 10
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    # Create fork point R
    r_root = fcr.add_and_apply_block(parent_root=fcr.head(), graffiti="R")
    fcr.attest(block_root=r_root, slot=fcr.current_slot(), participation_rate=100)
    fcr.next_slot()
    fcr.apply_attestations()
    fcr.attestation_pool = []
    fcr.run_fast_confirmation()

    # Create siblings A and M at current slot
    fork_slot = fcr.current_slot()
    prev_atts = list(fcr.attestation_pool)

    # A block
    a_root = fcr.add_and_apply_block(parent_root=r_root, graffiti="A")

    # M block (sibling)
    parent_state = store.block_states[r_root].copy()
    m_block = build_empty_block(spec, parent_state, fork_slot)
    for att in prev_atts:
        m_block.body.attestations.append(att)
    m_block.body.graffiti = b"M".ljust(32, b"\x00")
    signed_m = state_transition_and_sign_block(spec, parent_state, m_block)
    for artefact in add_block(spec, store, signed_m, fcr.test_steps):
        fcr.blockchain_artefacts.append(artefact)
    m_root = signed_m.message.hash_tree_root()

    # Build up A-side with strong votes
    fcr.attest(block_root=a_root, slot=fork_slot, participation_rate=100)
    fcr.next_slot()
    fcr.apply_attestations()
    fcr.attestation_pool = []
    fcr.run_fast_confirmation()

    # Extend A-side for one more slot to get confirmation on A-side
    a_tip = fcr.add_and_apply_block(parent_root=a_root, graffiti="A_tip")
    fcr.attest(block_root=a_tip, slot=fcr.current_slot(), participation_rate=100)
    fcr.next_slot()
    fcr.apply_attestations()
    fcr.attestation_pool = []
    fcr.run_fast_confirmation()

    # Verify confirmed is on A-side
    head = fcr.head()
    confirmed = store.confirmed_root

    assert spec.is_ancestor(store, head, confirmed), "Confirmed should be canonical"
    assert confirmed != store.finalized_checkpoint.root, "Confirmed should have advanced"
    assert spec.is_ancestor(store, confirmed, a_root), "a_root should be ancestor of confirmed"

    confirmed_before_reorg = confirmed

    # Now vote 100% for M for remaining slots until epoch boundary
    # Extend M-side to accumulate enough weight to flip head
    m_tip = m_root
    while fcr.current_slot() < epoch2_start:
        m_tip = fcr.add_and_apply_block(parent_root=m_tip, graffiti=f"M_{fcr.current_slot()}")
        fcr.attest(block_root=m_tip, slot=fcr.current_slot(), participation_rate=100)
        fcr.next_slot()
        fcr.apply_attestations()
        fcr.attestation_pool = []
        fcr.run_fast_confirmation()

    # Now at epoch 2 start — FCR already ran atomically at the boundary
    assert fcr.current_slot() == epoch2_start
    assert spec.is_start_slot_at_epoch(fcr.current_slot())

    # Verify head flipped to M-side
    head = fcr.head()
    assert spec.is_ancestor(store, head, m_root), "Head should be on M-side"

    # Verify confirmed_before_reorg is now non-canonical
    assert not spec.is_ancestor(store, head, confirmed_before_reorg), \
        "Confirmed before reorg should be non-canonical"

    # Verify reset to finalized
    assert store.confirmed_root == store.finalized_checkpoint.root, \
        "confirmed_root should reset to finalized when it becomes non-canonical"

    yield from fcr.get_test_artefacts()

@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_reverts_to_finalized_when_confirmed_not_canonical_mid_epoch(spec, state):
    """
    Test that confirmed_root resets to finalized when it becomes non-canonical due to a reorg at mid-epoch.
    
 
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


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_reverts_to_finalized_when_reconfirmation_fails_at_epoch_start_due_to_late_equivocations(spec, state):
    """
    Test that confirmed_root resets to finalized when reconfirmation fails at an epoch boundary.

    1. Build chain through epoch 2 with 100% participation so confirmations advance.
    2. In the last 3 slots before epoch 3, create competing forks and vote 100%
       for the "tip" blocks each time, so they become one-confirmed.
    3. At the last slot of epoch 2, after FCR runs and GU is sampled:
       inject late equivocation evidence (3 x 25% attester slashings).
    4. Cross into epoch 3 atomically (tick + apply attestations + FCR).
       FCR attempts to reconfirm under the new balance source but with ~75%
       of validators slashed, reconfirmation fails.
    5. Assert: confirmed_root == finalized_checkpoint.root.
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

    # Make sure confirmed_root is in epoch 2 (so it won't be "too old" at epoch 3)
    fcr.run_slots_with_blocks_and_fast_confirmation(2, participation_rate=100)
    assert spec.get_block_epoch(store, store.confirmed_root) == spec.Epoch(2)
    assert store.confirmed_root != store.finalized_checkpoint.root

    # Continue until 3 slots before epoch 3 boundary
    s1 = epoch3_start - 3
    s2 = epoch3_start - 2
    s3 = epoch3_start - 1
    while fcr.current_slot() < s1:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)
    assert fcr.current_slot() == s1

    # Fork and vote for 3 slots 
    tip_roots = []

    def fork_and_vote_tip_at_slot(slot):
        """
        At `slot`: create sibling blocks tip vs competing at same parent,
        vote 100% for tip, advance to next slot, apply votes, run FCR.
        """
        assert fcr.current_slot() == slot

        fork_parent_root = fcr.head()
        prev_pool_atts = list(fcr.attestation_pool)

        fcr.attestation_pool = list(prev_pool_atts)
        tip_root = fcr.add_and_apply_block(
            parent_root=fork_parent_root, release_att_pool=True, graffiti=f"tip_{slot}"
        )

        fcr.attestation_pool = list(prev_pool_atts)
        _competing_root = fcr.add_and_apply_block(
            parent_root=fork_parent_root, release_att_pool=True, graffiti=f"competing_{slot}"
        )

        fcr.attest(block_root=tip_root, slot=slot, participation_rate=100)
        tip_roots.append(tip_root)

        fcr.next_slot()
        fcr.apply_attestations()
        fcr.attestation_pool = []
        fcr.run_fast_confirmation()

    fork_and_vote_tip_at_slot(s1)
    assert fcr.current_slot() == s2

    fork_and_vote_tip_at_slot(s2)
    assert fcr.current_slot() == s3

    # Verify tips from s1 and s2 are one-confirmed (attestations applied)
    balance_source = spec.get_previous_balance_source(store)
    for i in range(2):
        assert spec.is_one_confirmed(store, balance_source, tip_roots[i]), \
            f"tip[{i}] not one-confirmed pre-slashing"

    # Slot s3 (last slot of epoch 2)
    # We need to inject slashing after FCR runs (GU sampling) but before
    # crossing into epoch 3.
    assert fcr.current_slot() == s3

    fork_parent_root = fcr.head()
    prev_pool_atts = list(fcr.attestation_pool)

    fcr.attestation_pool = list(prev_pool_atts)
    tip_root = fcr.add_and_apply_block(
        parent_root=fork_parent_root, release_att_pool=True, graffiti=f"tip_{s3}"
    )

    fcr.attestation_pool = list(prev_pool_atts)
    _competing_root = fcr.add_and_apply_block(
        parent_root=fork_parent_root, release_att_pool=True, graffiti=f"competing_{s3}"
    )

    fcr.attest(block_root=tip_root, slot=s3, participation_rate=100)
    tip_roots.append(tip_root)

    # Run FCR at last slot of epoch 2 — this samples GU
    fcr.run_fast_confirmation()

    # Snapshot state and verify preconditions 
    confirmed_before = store.confirmed_root
    head_before = fcr.head()
    current_epoch = spec.Epoch(3)  # we are about to cross into epoch 3

    confirmed_epoch = spec.get_block_epoch(store, confirmed_before)
    assert confirmed_epoch >= current_epoch - 1, \
        f"epoch(b_conf)={confirmed_epoch} < epoch(now)-1={current_epoch - 1}"


    assert spec.is_ancestor(store, head_before, confirmed_before), \
        "b_conf is not an ancestor of head"

    gu_prev = store.previous_epoch_observed_justified_checkpoint
    assert spec.is_ancestor(store, confirmed_before, gu_prev.root), \
        "b_conf is not a descendant of the reconfirmation anchor (GU_prev)"

    # Additional sanity: b_conf is strictly above GU_prev (not equal to it),
    # confirming there is a non-trivial segment to reconfirm
    assert confirmed_before != gu_prev.root, \
        "b_conf == GU_prev.root"

    assert confirmed_before != store.finalized_checkpoint.root, \
        "b_conf is already finalized"

    # Inject late equivocation evidence 
    equivocating_indices_before = set(store.equivocating_indices)
    slashings = []
    for _ in range(3):
        sl = fcr.apply_attester_slashing(slashing_percentage=25, slot=fcr.current_slot())
        slashings.append(sl)
    assert len(store.equivocating_indices) > len(equivocating_indices_before), \
        "Slashing had no effect — no new equivocating indices added"

    head_after_slashing = fcr.head()
    assert spec.is_ancestor(store, head_after_slashing, confirmed_before), \
        "b_conf fell off head chain after slashing"
    assert spec.get_block_epoch(store, confirmed_before) >= current_epoch - 1

    # Cross into epoch 3 
    fcr.next_slot()
    fcr.apply_attestations()
    fcr.attestation_pool = []

    # Verify we are at epoch 3 start 
    assert fcr.current_slot() == epoch3_start
    assert spec.is_start_slot_at_epoch(fcr.current_slot()), \
        "not at epoch start"

    assert confirmed_epoch >= spec.Epoch(2), \
        f"epoch(b_conf)={confirmed_epoch} < 2"

    head_at_epoch3 = fcr.head()
    assert spec.is_ancestor(store, head_at_epoch3, confirmed_before), \
        "b_conf not on head chain after crossing"

    gu_prev_at_epoch3 = store.previous_epoch_observed_justified_checkpoint
    assert spec.is_ancestor(store, confirmed_before, gu_prev_at_epoch3.root), \
        "b_conf is not a descendant of the reconf anchor"

    # Run FCR at epoch 3 start 
    fcr.run_fast_confirmation()

    assert store.confirmed_root == store.finalized_checkpoint.root, \
        (f"Expected reset to finalized={store.finalized_checkpoint.root}, "
         f"got confirmed={store.confirmed_root}")


    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_reset_to_finality_but_no_restart_to_gu_because_gu_too_old_epoch(spec, state):
    """
    Test that confirmed_root resets to finalized (not GU) when both are old at epoch boundary.
       
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
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_resets_when_bcand_not_descendant_of_gu_via_first_received_uj(spec, state):
    """
    Test that FCR resets when bcand ⊁ GU (bcand is not a descendant of the 
    globally observed unrealized justified checkpoint).
    
    This test uses "first-received UJ wins" semantics to create a scenario where:
    - GU points to checkpoint C on the RED branch (epoch 2)
    - bcand is a confirmed block on the BLACK branch (epoch 3)
    - BLACK branch is canonical (justified checkpoint is on BLACK)
    - bcand is NOT too old
    - bcand ⊁ GU (BLACK doesn't descend from RED)
    
    Timeline:
    - Epoch 2: Fork into RED and BLACK branches, neither justifies yet
    - Epoch 3 start: 
      * RED block 'a' released FIRST with epoch 2 attestations → UJ = (C, 2)
      * BLACK block 'd' released SECOND with epoch 2 attestations → internal UJ = (C'', 2)
      * Global UJ stays (C, 2) due to "first received wins"
    - Epoch 3: BLACK branch continues with 100% participation, confirmations advance
    - Epoch 3 last slot:
      * FCR runs → GU sampled = (C, 2)
      * THEN BLACK block b' released with epoch 3 attestations → justifies (d, 3)
    - Epoch 4: justified = (d, 3) so BLACK is canonical, but GU = (C, 2)
      * bcand (BLACK, epoch 3) ⊁ GU (C, epoch 2) → RESET
    
    The test verifies that reset occurs specifically due to bcand ⊁ GU,
    NOT due to bcand being too old or non-canonical.
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    epoch2_start = 2 * S
    epoch3_start = 3 * S
    epoch4_start = 4 * S

    # Epochs 0, 1: Normal operation
    while fcr.current_slot() < epoch2_start:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    assert fcr.current_slot() == epoch2_start

    # Epoch 2: Fork - RED and BLACK branches (empty attestation bodies)    
    fork_point = fcr.head()
    prev_atts = list(fcr.attestation_pool)
    
    # RED branch: C block
    fork_state = store.block_states[fork_point].copy()
    c_block = build_empty_block(spec, fork_state, fcr.current_slot())
    c_block.body.graffiti = b"C_red".ljust(32, b"\x00")
    for att in prev_atts:
        c_block.body.attestations.append(att)
    signed_c = state_transition_and_sign_block(spec, fork_state, c_block)
    for artefact in add_block(spec, store, signed_c, fcr.test_steps):
        fcr.blockchain_artefacts.append(artefact)
    c_red = signed_c.message.hash_tree_root()
    
    red_blocks_by_slot = {epoch2_start: c_red}
    red_tip = c_red
    red_state = store.block_states[c_red].copy()

    # BLACK branch: C'' block
    fcr.attestation_pool = list(prev_atts)
    c_double_prime = fcr.add_and_apply_block(parent_root=fork_point, graffiti="C_double_prime_black")
    black_tip = c_double_prime
    black_blocks_by_slot = {epoch2_start: c_double_prime}

    fcr.attest(block_root=black_tip, slot=fcr.current_slot(), participation_rate=100)
    fcr.next_slot()
    fcr.apply_attestations()
    fcr.attestation_pool = []
    fcr.run_fast_confirmation()

    # Continue epoch 2 with empty attestation bodies
    while fcr.current_slot() < epoch3_start:
        # Extend RED branch
        for s in range(epoch2_start + 1, fcr.current_slot()):
            if s not in red_blocks_by_slot:
                rb = build_empty_block(spec, red_state, s)
                rb.body.graffiti = f"red_{s}".encode().ljust(32, b"\x00")
                signed_rb = state_transition_and_sign_block(spec, red_state, rb)
                for artefact in add_block(spec, store, signed_rb, fcr.test_steps):
                    fcr.blockchain_artefacts.append(artefact)
                red_tip = signed_rb.message.hash_tree_root()
                red_blocks_by_slot[s] = red_tip
                red_state = store.block_states[red_tip].copy()
        
        # Extend BLACK branch
        parent_state = store.block_states[black_tip].copy()
        black_block = build_empty_block(spec, parent_state, fcr.current_slot())
        black_block.body.graffiti = f"black_e2_{fcr.current_slot()}".encode().ljust(32, b"\x00")
        signed_black = state_transition_and_sign_block(spec, parent_state, black_block)
        for artefact in add_block(spec, store, signed_black, fcr.test_steps):
            fcr.blockchain_artefacts.append(artefact)
        black_tip = signed_black.message.hash_tree_root()
        black_blocks_by_slot[fcr.current_slot()] = black_tip
        
        fcr.attest(block_root=black_tip, slot=fcr.current_slot(), participation_rate=100)
        fcr.next_slot()
        fcr.apply_attestations()
        fcr.attestation_pool = []
        fcr.run_fast_confirmation()

    # Complete red branch through epoch 2
    for s in range(epoch2_start + 1, epoch3_start):
        if s not in red_blocks_by_slot:
            rb = build_empty_block(spec, red_state, s)
            rb.body.graffiti = f"red_{s}".encode().ljust(32, b"\x00")
            signed_rb = state_transition_and_sign_block(spec, red_state, rb)
            for artefact in add_block(spec, store, signed_rb, fcr.test_steps):
                fcr.blockchain_artefacts.append(artefact)
            red_tip = signed_rb.message.hash_tree_root()
            red_blocks_by_slot[s] = red_tip
            red_state = store.block_states[red_tip].copy()

    assert fcr.current_slot() == epoch3_start

    # Epoch 3 start: Release 'a' FIRST with epoch 2 attestations → UJ = (C, 2)
    a_block = build_empty_block(spec, red_state, fcr.current_slot())
    a_block.body.graffiti = b"a_red_FIRST".ljust(32, b"\x00")
    
    for att_slot in range(epoch2_start, epoch3_start):
        if att_slot in red_blocks_by_slot:
            block_root_for_att = red_blocks_by_slot[att_slot]
            att_state = store.block_states[block_root_for_att].copy()
            slot_attestations = get_valid_attestations_for_block_at_slot(
                spec, att_state, spec.Slot(att_slot), block_root_for_att,
                participation_fn=lambda slot, index, committee: committee,
            )
            for att in slot_attestations:
                if len(a_block.body.attestations) < spec.MAX_ATTESTATIONS:
                    a_block.body.attestations.append(att)

    signed_a = state_transition_and_sign_block(spec, red_state, a_block)
    for artefact in add_block(spec, store, signed_a, fcr.test_steps):
        fcr.blockchain_artefacts.append(artefact)
    
    assert store.unrealized_justified_checkpoint.root == c_red
    assert store.unrealized_justified_checkpoint.epoch == spec.Epoch(2)

    # Release 'd' SECOND with epoch 2 attestations → internal UJ = (C'', 2), global stays (C, 2)
    parent_state = store.block_states[black_tip].copy()
    d_block = build_empty_block(spec, parent_state, fcr.current_slot())
    d_block.body.graffiti = b"d_black_SECOND".ljust(32, b"\x00")
    
    for att_slot in range(epoch2_start, epoch3_start):
        if att_slot in black_blocks_by_slot:
            block_root_for_att = black_blocks_by_slot[att_slot]
            att_state = store.block_states[block_root_for_att].copy()
            slot_attestations = get_valid_attestations_for_block_at_slot(
                spec, att_state, spec.Slot(att_slot), block_root_for_att,
                participation_fn=lambda slot, index, committee: committee,
            )
            for att in slot_attestations:
                if len(d_block.body.attestations) < spec.MAX_ATTESTATIONS:
                    d_block.body.attestations.append(att)

    signed_d = state_transition_and_sign_block(spec, parent_state, d_block)
    for artefact in add_block(spec, store, signed_d, fcr.test_steps):
        fcr.blockchain_artefacts.append(artefact)
    d_root = signed_d.message.hash_tree_root()
    black_tip = d_root
    black_blocks_by_slot[fcr.current_slot()] = d_root
    epoch3_black_checkpoint = d_root
    
    assert store.unrealized_justified_checkpoint.root == c_red  # Global UJ still (C, 2)

    fcr.attest(block_root=black_tip, slot=fcr.current_slot(), participation_rate=100)
    fcr.next_slot()
    fcr.apply_attestations()
    fcr.attestation_pool = []
    fcr.run_fast_confirmation()

    # Continue epoch 3 with normal black blocks
    while fcr.current_slot() < epoch4_start - 1:
        black_block = fcr.add_and_apply_block(parent_root=black_tip, graffiti=f"black_e3_{fcr.current_slot()}")
        black_tip = black_block
        black_blocks_by_slot[fcr.current_slot()] = black_block
        
        fcr.attest(block_root=black_tip, slot=fcr.current_slot(), participation_rate=100)
        fcr.next_slot()
        fcr.apply_attestations()
        fcr.attestation_pool = []
        fcr.run_fast_confirmation()

    # Last slot of epoch 3: First run FCR (GU sampling), THEN release b'
    assert fcr.current_slot() == epoch4_start - 1
    assert spec.is_start_slot_at_epoch(spec.Slot(fcr.current_slot() + 1))
    
    # Run FCR FIRST - this samples GU = (C, 2)
    fcr.run_fast_confirmation()

    gu = store.current_epoch_observed_justified_checkpoint
    assert gu.root == c_red
    assert gu.epoch == spec.Epoch(2)

    # NOW release b' with epoch 3 attestations → justifies (d_root, 3)
    parent_state = store.block_states[black_tip].copy()
    b_prime_block = build_empty_block(spec, parent_state, fcr.current_slot())
    b_prime_block.body.graffiti = b"b_prime_LAST".ljust(32, b"\x00")
    
    for att_slot in range(epoch3_start, fcr.current_slot()):
        if att_slot in black_blocks_by_slot:
            block_root_for_att = black_blocks_by_slot[att_slot]
            att_state = store.block_states[block_root_for_att].copy()
            slot_attestations = get_valid_attestations_for_block_at_slot(
                spec, att_state, spec.Slot(att_slot), block_root_for_att,
                participation_fn=lambda slot, index, committee: committee,
            )
            for att in slot_attestations:
                if len(b_prime_block.body.attestations) < spec.MAX_ATTESTATIONS:
                    b_prime_block.body.attestations.append(att)

    signed_b_prime = state_transition_and_sign_block(spec, parent_state, b_prime_block)
    for artefact in add_block(spec, store, signed_b_prime, fcr.test_steps):
        fcr.blockchain_artefacts.append(artefact)
    b_prime = signed_b_prime.message.hash_tree_root()
    black_tip = b_prime

    # Verify b' justifies (d_root, 3) on black branch
    uj_of_b_prime = store.unrealized_justifications.get(b_prime, None)
    assert uj_of_b_prime is not None
    assert uj_of_b_prime.epoch == spec.Epoch(3)
    assert uj_of_b_prime.root == epoch3_black_checkpoint
    assert spec.is_ancestor(store, uj_of_b_prime.root, c_double_prime)

    # GU should STILL be (C, 2)
    assert store.current_epoch_observed_justified_checkpoint.root == c_red
    assert store.current_epoch_observed_justified_checkpoint.epoch == spec.Epoch(2)

    fcr.attest(block_root=b_prime, slot=fcr.current_slot(), participation_rate=100)

    # Cross into Epoch 4
    fcr.next_slot()
    fcr.apply_attestations()
    fcr.attestation_pool = []

    assert fcr.current_slot() == epoch4_start
    assert spec.is_start_slot_at_epoch(fcr.current_slot())

    # Verify preconditions: reset is due to bcand ⊁ GU
    head_before_fcr = fcr.head()
    confirmed_before_fcr = store.confirmed_root
    current_epoch = spec.get_current_store_epoch(store)
    gu_root = store.current_epoch_observed_justified_checkpoint.root
    confirmed_epoch = spec.get_block_epoch(store, confirmed_before_fcr)

    bcand_too_old = confirmed_epoch + 1 < current_epoch
    bcand_not_canonical = not spec.is_ancestor(store, head_before_fcr, confirmed_before_fcr)
    bcand_not_descendant_of_gu = not spec.is_ancestor(store, confirmed_before_fcr, gu_root)

    # These must be FALSE - otherwise reset would be due to these, not bcand ⊁ GU
    assert not bcand_too_old, "bcand should NOT be too old"
    assert not bcand_not_canonical, "bcand should be canonical"
    
    # This must be TRUE - this is what triggers the reset
    assert bcand_not_descendant_of_gu, "bcand should NOT be descendant of GU"

    # Run FCR and verify reset
    fcr.run_fast_confirmation()

    confirmed_after_fcr = store.confirmed_root
    finalized = store.finalized_checkpoint.root

    assert confirmed_after_fcr == finalized, \
        "confirmed_root should reset to finalized due to bcand ⊁ GU"

    yield from fcr.get_test_artefacts()