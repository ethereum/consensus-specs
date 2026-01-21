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
    fcr.run_slots_with_blocks_and_fast_confirmation(epoch2_start - fcr.current_slot(), participation_rate=100)
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

    # Next slot: build C on B; attest 100% to M; advance + apply + FCR
    c_root = fcr.add_and_apply_block(parent_root=b_root)
    fcr.attest_and_next_slot_with_fast_confirmation(block_root=m_root, participation_rate=100)

    # Confirmed still on A side (optional sanity)
    assert spec.is_ancestor(store, store.confirmed_root, a_root)

    # Next slot: build D on C; attest 100% to M again; advance + apply + FCR
    _d_root = fcr.add_and_apply_block(parent_root=c_root)
    fcr.attest_and_next_slot_with_fast_confirmation(block_root=m_root, participation_rate=100)

    # Now: head should be on M side, and confirmed should have reset to finalized
    head = fcr.head()
    assert spec.is_ancestor(store, head, m_root), "Head did not flip to M (may need one more 100%-to-M slot)"
    assert store.confirmed_root == store.finalized_checkpoint.root, "Expected reset to finalized mid-epoch"

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
    fcr = FCRTest(spec)
    store = fcr.initialize(state, seed=1)

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
    # One slashing is too weak to break reconfirmation in practice
    s1 = epoch3_start - 3
    s2 = epoch3_start - 2
    s3 = epoch3_start - 1
    while fcr.current_slot() < s1:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)
    assert fcr.current_slot() == s1

    # We will collect (honest_atts, equiv_atts, tip_root) for 3 slots, then "prove" equivocations at epoch start
    records = []

    def fork_and_vote_at_slot(slot, run_fcr_after_applying=True):
        """
        At `slot` (must equal fcr.current_slot()):
          - create sibling blocks tip vs competing at same parent/slot
          - produce honest votes for tip (kept in pool)
          - produce equiv votes for competing (removed from pool and stored)
          - move to next slot and apply honest votes
          - optionally run FCR at slot start (do NOT run it at epoch boundary until after slashings)
        """
        assert fcr.current_slot() == slot

        fork_parent_root = fcr.head()
        prev_pool_atts = list(fcr.attestation_pool)

        # tip block
        fcr.attestation_pool = list(prev_pool_atts)
        tip_root = fcr.add_and_apply_block(
            parent_root=fork_parent_root, release_att_pool=True, graffiti=f"tip_{slot}"
        )

        # competing sibling block at same parent/slot
        fcr.attestation_pool = list(prev_pool_atts)
        competing_root = fcr.add_and_apply_block(
            parent_root=fork_parent_root, release_att_pool=True, graffiti=f"competing_{slot}"
        )

        # Honest votes for tip (keep in pool to be applied next slot)
        honest_atts = fcr.attest(block_root=tip_root, slot=slot, participation_rate=100)

        # Equivocating votes for competing 
        equiv_atts = fcr.attest(block_root=competing_root, slot=slot, participation_rate=100)
        for a in equiv_atts:
            fcr.attestation_pool.remove(a)

        records.append(
            {
                "slot": slot,
                "tip_root": tip_root,
                "competing_root": competing_root,
                "honest_atts": list(honest_atts),
                "equiv_atts": list(equiv_atts),
            }
        )

        # Advance and apply honest votes
        fcr.next_slot()
        fcr.apply_attestations()
        fcr.attestation_pool = []

        if run_fcr_after_applying:
            fcr.run_fast_confirmation()

    # Slot epoch3_start-3: fork, vote for tip, advance, apply, run FCR normally
    fork_and_vote_at_slot(s1, run_fcr_after_applying=True)
    assert fcr.current_slot() == s2

    # Slot epoch3_start-2: fork, vote for tip, advance, apply, run FCR normally
    fork_and_vote_at_slot(s2, run_fcr_after_applying=True)
    assert fcr.current_slot() == s3

    # Slot epoch3_start-1: fork, vote for tip, advance into epoch 3, apply honest votes, BUT DO NOT run FCR yet
    fork_and_vote_at_slot(s3, run_fcr_after_applying=False)
    assert fcr.current_slot() == epoch3_start
    assert spec.is_start_slot_at_epoch(fcr.current_slot())

    # Before we inject slashings, the tips should be one-confirmed under the previous balance source.
    balance_source = spec.get_previous_balance_source(store)
    for rec in records:
        assert spec.is_one_confirmed(
            store, balance_source, rec["tip_root"]
        ), f"tip at slot {rec['slot']} not one-confirmed before slashings"

    # Rule out the other reset disjuncts *before* reconfirmation:
    confirmed_before = store.confirmed_root
    head_before = fcr.head()
    assert confirmed_before != store.finalized_checkpoint.root
    assert spec.is_ancestor(store, head_before, confirmed_before)  # canonical
    assert spec.get_block_epoch(store, confirmed_before) >= spec.Epoch(2)  # not too old

    # Late equivocations "land" at epoch boundary: create + process AttesterSlashings for ALL 3 slots
    for rec in records:
        slot = rec["slot"]
        honest_atts = rec["honest_atts"]
        equiv_atts = rec["equiv_atts"]
        tip_root = rec["tip_root"]

        # Find a matching committee index (same slot/target epoch, different head root)
        honest_by_index = {att.data.index: att for att in honest_atts}
        pair = None
        for att2 in equiv_atts:
            att1 = honest_by_index.get(att2.data.index)
            if att1 is None:
                continue
            if (
                att1.data.slot == att2.data.slot == slot
                and att1.data.target.epoch == att2.data.target.epoch
                and att1.data.beacon_block_root != att2.data.beacon_block_root
            ):
                pair = (att1, att2)
                break
        assert pair is not None, f"Could not find slashable equivocation pair at slot {slot}"
        honest_att, equiv_att = pair

        # Build indexed attestations in the correct state context for this slot
        att_state = store.block_states[tip_root].copy()
        transition_to(spec, att_state, slot)

        indexed_1 = spec.get_indexed_attestation(att_state, honest_att)
        indexed_2 = spec.get_indexed_attestation(att_state, equiv_att)

        slashing = spec.AttesterSlashing(attestation_1=indexed_1, attestation_2=indexed_2)

        # Add explicit artefacts + steps
        fcr.blockchain_artefacts.append(("attester_slashing", slashing))
        fcr.test_steps.append(
            {
                "attester_slashing": {
                    "slot": int(slot),
                    "tip_root": encode_hex(rec["tip_root"]),
                    "competing_root": encode_hex(rec["competing_root"]),
                    "a1": {
                        "committee_index": int(honest_att.data.index),
                        "beacon_block_root": encode_hex(honest_att.data.beacon_block_root),
                        "target_epoch": int(honest_att.data.target.epoch),
                        "target_root": encode_hex(honest_att.data.target.root),
                        "source_epoch": int(honest_att.data.source.epoch),
                        "source_root": encode_hex(honest_att.data.source.root),
                        "attesting_indices_len": int(len(indexed_1.attesting_indices)),
                    },
                    "a2": {
                        "committee_index": int(equiv_att.data.index),
                        "beacon_block_root": encode_hex(equiv_att.data.beacon_block_root),
                        "target_epoch": int(equiv_att.data.target.epoch),
                        "target_root": encode_hex(equiv_att.data.target.root),
                        "source_epoch": int(equiv_att.data.source.epoch),
                        "source_root": encode_hex(equiv_att.data.source.root),
                        "attesting_indices_len": int(len(indexed_2.attesting_indices)),
                    },
                }
            }
        )

        # Apply the slashing to the store (this is what clients must reproduce)
        spec.on_attester_slashing(store, slashing)

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


# GU too old => no restart
# This version lowers participations to 0 in order to create a too-old justification
@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_no_restart_at_epoch3_when_epoch2_not_justified_under_50_50_target_split(spec, state):
    test_steps = []

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    S = spec.SLOTS_PER_EPOCH
    epoch2_start = 2 * S
    epoch3_start = 3 * S

    fork_root = None           # epoch2-start block on the fork (B)
    main_epoch2_root = None    # epoch2-start block on the main chain (A)

    fork_state = None
    main_head_root = anchor_block.hash_tree_root()
    fork_head_root = None

    # Approximate 50/50 by choosing half the *slots* in epoch 2 to attest on the fork.
    fork_vote_slots = set(range(epoch2_start, epoch2_start + (S // 2)))

    attestations = []

    # Run until (but not including) epoch3_start processing would require slot == epoch3_start,
    # because each iteration advances store to slot+1.
    for _ in range(spec.GENESIS_SLOT, epoch3_start):
        # 1) Build next-slot block(s)
        # We are currently at state.slot; build block for state.slot + 1 (as usual in these tests).
        if state.slot + 1 == epoch2_start:
            # Create two sibling blocks at epoch-2 boundary: A (main) and B (fork)
            pre_state = copy.deepcopy(state)

            # Main block A at slot == epoch2_start
            block_a = build_empty_block_for_next_slot(spec, state)
            signed_a = state_transition_and_sign_block(spec, state, block_a)
            yield from add_block(spec, store, signed_a, test_steps)
            main_head_root = signed_a.message.hash_tree_root()
            main_epoch2_root = main_head_root

            # Fork sibling block B at the same parent/slot
            block_b = build_empty_block_for_next_slot(spec, pre_state)
            block_b.body.graffiti = b"fork".ljust(32, b"\x00")  # ensure different root
            signed_b = state_transition_and_sign_block(spec, pre_state, block_b)
            yield from add_block(spec, store, signed_b, test_steps)
            fork_root = signed_b.message.hash_tree_root()

            fork_state = pre_state
            fork_head_root = fork_root

        elif state.slot > spec.GENESIS_SLOT:
            # Extend main chain
            block_main = build_empty_block_for_next_slot(spec, state)
            signed_main = state_transition_and_sign_block(spec, state, block_main)
            yield from add_block(spec, store, signed_main, test_steps)
            main_head_root = signed_main.message.hash_tree_root()

            # Extend fork chain if it exists
            if fork_state is not None:
                block_f = build_empty_block_for_next_slot(spec, fork_state)
                signed_f = state_transition_and_sign_block(spec, fork_state, block_f)
                yield from add_block(spec, store, signed_f, test_steps)
                fork_head_root = signed_f.message.hash_tree_root()

        # 2) Choose which chain to attest to at this slot
        if state.slot < epoch2_start:
            att_state = state
            att_head = main_head_root
        else:
            assert fork_state is not None and fork_head_root is not None and fork_root is not None
            if state.slot in fork_vote_slots:
                att_state = fork_state
                att_head = fork_head_root
            else:
                att_state = state
                att_head = main_head_root

        attestations = get_valid_attestations_for_block_at_slot(
            spec, att_state, att_state.slot, att_head
        )

        # 3) Advance store time to next slot start, add attestations, run slot-start handler
        next_time = (state.slot + 1) * spec.config.SECONDS_PER_SLOT + store.genesis_time
        on_tick_and_append_step(spec, store, next_time, test_steps)

        yield from add_attestations(spec, store, attestations, test_steps)
        on_slot_start_after_past_attestations_applied_and_append_step(spec, store, test_steps)

        # After handler, store is now at "current slot start"
        cur_slot = spec.get_current_slot(store)

        # 4) Boundary assertions
        if cur_slot == epoch2_start:
            # At epoch 2 start, epoch 1 should be justified under full participation.
            assert main_epoch2_root is not None and fork_root is not None
            assert store.justified_checkpoint.epoch >= spec.Epoch(1)
            assert store.current_epoch_observed_justified_checkpoint.epoch >= spec.Epoch(1)

        if cur_slot == epoch3_start:
            # At epoch 3 start, epoch 2 must NOT be justified (target votes split).
            assert store.justified_checkpoint.epoch < spec.Epoch(2)

            gu = store.current_epoch_observed_justified_checkpoint
            # Under split, GU should still be stuck at epoch 1 (no new justification in epoch 2)
            assert gu.epoch == spec.Epoch(1)

            # Restart must NOT be able to run: guard is (gu.epoch + 1 == current_epoch)
            assert spec.is_start_slot_at_epoch(cur_slot)
            current_epoch = spec.get_current_store_epoch(store)
            assert current_epoch == spec.Epoch(3)
            assert gu.epoch + 1 != current_epoch

    yield "steps", test_steps