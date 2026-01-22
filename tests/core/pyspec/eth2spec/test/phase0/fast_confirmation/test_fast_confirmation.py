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
    fcr_test = FCRTest(spec)
    store = fcr_test.initialize(state, seed=1)
    for _ in range(spec.SLOTS_PER_EPOCH):
        fcr_test.next_slot_with_block_and_fast_confirmation()
        # Ensure head is confirmed
        assert store.confirmed_root == fcr_test.head()

    yield from fcr_test.get_test_artefacts()


# FCR never confirms something non-canonical, and it never goes backwards (unless it resets to GF)
@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_invariants_monotone_and_canonical(spec, state):
    fcr_test = FCRTest(spec)
    store = fcr_test.initialize(state, seed=1)

    prev_confirmed_slot = store.blocks[store.confirmed_root].slot

    # Run a short prefix 
    for _ in range(8):
        fcr_test.next_slot_with_block_and_fast_confirmation(participation_rate=100)

        head = fcr_test.head()
        confirmed = store.confirmed_root

        # confirmed must be on canonical chain: confirmed is ancestor of head
        assert spec.is_ancestor(store, head, confirmed)

        # confirmed slot monotonic unless reset to finalized
        confirmed_slot = store.blocks[confirmed].slot
        finalized = store.finalized_checkpoint.root
        finalized_slot = store.blocks[finalized].slot

        if confirmed != finalized:
            assert confirmed_slot >= prev_confirmed_slot
        else:
            # if reset happened, it must reset exactly to finalized
            assert confirmed_slot == finalized_slot

        prev_confirmed_slot = confirmed_slot

    yield from fcr_test.get_test_artefacts()


# Stale confirmed root => revert to GF
@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_reverts_to_finalized_when_confirmed_too_old_lower_participation(spec, state):
    fcr = FCRTest(spec)
    store = fcr.initialize(state, seed=1)

    S = spec.SLOTS_PER_EPOCH
    epoch2_start = 2 * S
    epoch3_start = 3 * S

    drop_slot = S + (S // 2)  # mid of epoch 1
    assert drop_slot % S != 0

    saw_nonfinal_confirmation = False
    frozen_root = None

    # Run until we enter epoch 3 (epoch boundary processing happens when we start that slot)
    while fcr.current_slot() < epoch3_start:
        cur = fcr.current_slot()

        # participation controls attestations PRODUCED at slot cur
        participation = 100 if cur < drop_slot else 60

        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=participation)
        now = fcr.current_slot()

        # We should see at least one non-final confirmation before the drop kicks in
        if now <= drop_slot and store.confirmed_root != store.finalized_checkpoint.root:
            saw_nonfinal_confirmation = True

        # Freeze the confirmed root exactly when we ENTER drop_slot (i.e., after processing cur=drop_slot-1)
        if now == drop_slot:
            frozen_root = store.confirmed_root
            assert frozen_root != store.finalized_checkpoint.root

        # After the drop begins, confirmations should stall (stay frozen) until epoch3 reset
        if frozen_root is not None and now < epoch3_start:
            assert store.confirmed_root == frozen_root

        # Optional sanity at epoch2 start: confirmed should still be from epoch <= 1
        if now == epoch2_start:
            assert spec.is_start_slot_at_epoch(now)
            confirmed_epoch = spec.get_block_epoch(store, store.confirmed_root)
            assert confirmed_epoch <= spec.Epoch(1)

    assert saw_nonfinal_confirmation

    # Now at epoch 3 start: confirmed should reset to finalized due to "too old"
    assert fcr.current_slot() == epoch3_start
    assert spec.is_start_slot_at_epoch(fcr.current_slot())
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
    fcr = FCRTest(spec)
    store = fcr.initialize(state, seed=1)

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

    # Confirmed still on A side (optional sanity)
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

#  At mid epoch, if the previously confirmed chain cannot be re-confirmed, FCR must *not* reset confirmed_root to finalized.
@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_not_revert_to_finalized_when_reconfirmation_fails_at_mid_epoch(spec, state):

    test_steps = []

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    attestations = []
    last_root = anchor_block.hash_tree_root()

    epoch2_start = spec.SLOTS_PER_EPOCH * 2
    trigger_slot = epoch2_start + 12
    assert trigger_slot % spec.SLOTS_PER_EPOCH != 0

    for slot in range(spec.GENESIS_SLOT, trigger_slot):
        if slot > spec.GENESIS_SLOT:
            block = build_empty_block_for_next_slot(spec, state)
            for att in attestations:
                block.body.attestations.append(att)
            signed = state_transition_and_sign_block(spec, state, block)
            yield from add_block(spec, store, signed, test_steps)
            last_root = signed.message.hash_tree_root()

        attestations = get_valid_attestations_for_block_at_slot(
            spec, state, state.slot, spec.get_head(store)
        )

        current_time = (slot + 1) * spec.config.SECONDS_PER_SLOT + store.genesis_time
        on_tick_and_append_step(spec, store, current_time, test_steps)

        yield from add_attestations(spec, store, attestations, test_steps)
        on_slot_start_after_past_attestations_applied_and_append_step(spec, store, test_steps)

        if slot + 1 == trigger_slot:
            assert not spec.is_start_slot_at_epoch(spec.get_current_slot(store))

            # Choose a recent canonical root (last produced block)
            assert last_root != store.finalized_checkpoint.root
            head = spec.get_head(store)
            assert spec.is_ancestor(store, head, last_root)

            store.confirmed_root = last_root

            # We are not triggering "too old" or "non-canonical" resets
            current_epoch = spec.get_current_store_epoch(store)
            assert spec.get_block_epoch(store, store.confirmed_root) + 1 >= current_epoch
            assert spec.is_ancestor(store, head, store.confirmed_root)
            assert spec.is_ancestor( # confirmed is ancestor of current_epoch_observed_justified_checkpoint
                store,
                store.confirmed_root,
                store.current_epoch_observed_justified_checkpoint.root,
            )

            # Mid-epoch behavior:
            # - The restart clause cannot run (it is guarded by is_start_slot_at_epoch(...)).
            # - The reconfirmation check (is_confirmed_chain_safe) also cannot run (same guard).
            # - Therefore, wiping latest_messages mid-epoch will not "force a revert to finalized".
            #   Instead, FCR typically cannot advance confirmations (is_one_confirmed fails),
            #   and confirmed_root should remain whatever it already was.
            store.latest_messages = {}

        on_slot_start_after_past_attestations_applied_and_append_step(spec, store, test_steps)

    assert store.confirmed_root != store.finalized_checkpoint.root

    yield "steps", test_steps


# Goals:
#   - Epoch 2 has low participation, so the confirmed chain becomes "too old" by epoch 3 start,
#     and confirmed_root must reset to finalized at epoch 3 start.
#   - At the same time, we do NOT "restart to GU" at epoch 3 start because GU is too old
#     (current_epoch_observed_justified_checkpoint.epoch + 1 < current_epoch).
#   - Additionally: finalized is strictly older than GU at the block level (slot(finalized) < slot(GU))

@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_reset_to_finality_but_no_restart_to_gu_because_gu_too_old_epoch(spec, state):
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