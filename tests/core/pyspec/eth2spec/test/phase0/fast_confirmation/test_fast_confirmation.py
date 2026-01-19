import copy

from eth2spec.test.context import MINIMAL, spec_state_test, with_altair_and_later, with_presets

from eth2spec.test.helpers.block import build_empty_block  # NOTE: build_empty_block (not _for_next_slot)
from eth2spec.test.helpers.state import state_transition_and_sign_block, transition_to
from eth2spec.test.helpers.fork_choice import add_block

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


# Stale confirmed root => revert to GF (v2, more realistic scenario)

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
    epoch1_start = S
    epoch2_start = 2 * S
    epoch3_start = 3 * S

    drop_slot = epoch1_start + (S // 2)
    assert drop_slot % S != 0

    nonfinal_confirmed_root = None
    frozen_root = None

    # We run slots up to the start of epoch 3 (exclusive),
    # because "epoch start processing" happens when we enter that slot.
    while fcr.current_slot() < epoch3_start:
        cur = fcr.current_slot()

        # Decide participation *for the attestations produced at this slot*.
        # Before drop_slot: normal voting. From drop_slot onward: zero voting.
        participation = 100 if cur < drop_slot else 60

 
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=participation)

        now_slot = fcr.current_slot()

        # Before the drop begins, record a concrete non-final confirmation.
        if now_slot <= drop_slot and store.confirmed_root != store.finalized_checkpoint.root:
            if nonfinal_confirmed_root is None:
                nonfinal_confirmed_root = store.confirmed_root

        # Exactly when we *enter* drop_slot, lock the confirmed root.
        #    (Because participation for cur==drop_slot was set to 60,
        #     from this point onward confirmations should stall.)
        if now_slot == drop_slot:
            frozen_root = store.confirmed_root
            assert frozen_root != store.finalized_checkpoint.root

        # After the drop begins, but before epoch3 reset, confirmed must remain frozen.
        if frozen_root is not None and now_slot < epoch3_start:
            assert store.confirmed_root == frozen_root

        if now_slot == epoch2_start:
            assert spec.is_start_slot_at_epoch(now_slot)
            confirmed_epoch = spec.get_block_epoch(store, store.confirmed_root)
            assert confirmed_epoch <= spec.Epoch(1)

    # We must have actually seen non-final confirmation before drop.
    assert nonfinal_confirmed_root is not None

    # Now we are at epoch 3 start; the "too old" rule should reset to finalized.
    assert spec.is_start_slot_at_epoch(fcr.current_slot())
    assert fcr.current_slot() == epoch3_start
    assert store.confirmed_root == store.finalized_checkpoint.root

    yield from fcr.get_test_artefacts()

# Confirmed blocks become non canonical => we revert to finalized 

@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_reverts_to_finalized_when_confirmed_not_canonical_at_epoch_start(spec, state):
    fcr = FCRTest(spec)
    store = fcr.initialize(state, seed=1)

    S = spec.SLOTS_PER_EPOCH
    epoch2_start = 2 * S

    # We want:
    #   - create competing children at fork_slot
    #   - allow at least one full slot after fork_slot to let FCR confirm past the fork point
    #   - at last slot of epoch 1, vote 100% for competing child
    fork_slot = epoch2_start - 3         
    last_epoch1_slot = epoch2_start - 1  

    canonical_child_root = None
    competing_child_root = None

    while fcr.current_slot() < epoch2_start:
        cur_slot = fcr.current_slot()

        if cur_slot == fork_slot:
            fork_parent_root = fcr.head()

            # attestations from previous slot that should be included in blocks at cur_slot
            prev_slot_attestations = list(fcr.attestation_pool)

            # canonical child at cur_slot 
            canonical_child_root = fcr.add_and_apply_block(parent_root=fork_parent_root)

            # competing sibling at same parent/slot
            parent_state = store.block_states[fork_parent_root].copy()
            competing_block = build_empty_block(spec, parent_state, cur_slot)
            for att in prev_slot_attestations:
                competing_block.body.attestations.append(att)
            competing_block.body.graffiti = b"i_love_ethereum".ljust(32, b"\x00")

            signed_competing = state_transition_and_sign_block(spec, parent_state, competing_block)
            for artefact in add_block(spec, store, signed_competing, fcr.test_steps):
                fcr.blockchain_artefacts.append(artefact)

            competing_child_root = signed_competing.message.hash_tree_root()

            # fork_slot: only 75% vote for canonical child 
            fcr.attest(block_root=canonical_child_root, slot=cur_slot, participation_rate=75)
            fcr.next_slot()
            fcr.apply_attestations()
            fcr.run_fast_confirmation()
            continue

        # At last slot of epoch 1, vote for competing child 
        if cur_slot == last_epoch1_slot:
            assert competing_child_root is not None

            fcr.add_and_apply_block(parent_root=fcr.head())

            # vote 100% for competing child to flip head at epoch2_start
            fcr.attest(block_root=competing_child_root, slot=cur_slot, participation_rate=100)

            fcr.next_slot()
            fcr.apply_attestations()
            fcr.run_fast_confirmation()
            continue

        # Normal case
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

        # After we have passed fork_slot by at least one normal slot,
        # ensure confirmation has moved onto the canonical child chain
        if canonical_child_root is not None and fcr.current_slot() >= fork_slot + 2:
            assert spec.is_ancestor(store, store.confirmed_root, canonical_child_root)

    # Now at epoch2_start, after applying last-epoch attestations and running FCR.
    assert fcr.current_slot() == epoch2_start

    # If epoch-start safety check detects confirmed is not canonical, it should reset to finalized.
    assert store.confirmed_root == store.finalized_checkpoint.root

    yield from fcr.get_test_artefacts()

# DONE UNTIL HERE

# Confirmed blocks become non canonical => we revert to finalized (test mid epoch)

@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_reverts_to_finalized_when_confirmed_not_canonical_at_mid_epoch(spec, state):
    test_steps = []

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    # Tick to genesis slot start
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    attestations = []
    fork2_root = None
    fork1_root = None

    # fork inside epoch 1
    fork_slot = spec.SLOTS_PER_EPOCH + 1
    
    epoch2_start = spec.SLOTS_PER_EPOCH * 2
    trigger_slot = epoch2_start + 5  # mid-epoch slot (not boundary)
    assert trigger_slot % spec.SLOTS_PER_EPOCH != 0

    end_slot = trigger_slot

    for slot in range(spec.GENESIS_SLOT, end_slot):
        if slot > spec.GENESIS_SLOT:
            if slot + 1 == fork_slot:
                pre_state = copy.deepcopy(state)
                block1 = build_empty_block_for_next_slot(spec, state)
                
                for att in attestations:
                    block1.body.attestations.append(att)
                signed1 = state_transition_and_sign_block(spec, state, block1)
                yield from add_block(spec, store, signed1, test_steps)
                fork1_root = signed1.message.hash_tree_root()

                # Competing sibling block (fork2) using pre_state (same parent/slot, different contents)
                block2 = build_empty_block_for_next_slot(spec, pre_state)
                for att in attestations:
                    block2.body.attestations.append(att)
                block2.body.graffiti = b"i love ethereum".ljust(32, b"\x00")
                signed2 = state_transition_and_sign_block(spec, pre_state, block2)
                yield from add_block(spec, store, signed2, test_steps)
                fork2_root = signed2.message.hash_tree_root()

                # Add attestations towards fork1 for this slot
                attestations = get_valid_attestations_for_block_at_slot(
                    spec, state, state.slot, fork1_root
                )
            else:
                block = build_empty_block_for_next_slot(spec, state)
                for att in attestations:
                    block.body.attestations.append(att)
                signed = state_transition_and_sign_block(spec, state, block)
                yield from add_block(spec, store, signed, test_steps)

                attestations = get_valid_attestations_for_block_at_slot(
                    spec, state, state.slot, spec.get_head(store)
                )
        else:
            # slot == GENESIS_SLOT
            attestations = get_valid_attestations_for_block_at_slot(
                spec, state, state.slot, spec.get_head(store)
            )

        current_time = (slot + 1) * spec.config.SECONDS_PER_SLOT + store.genesis_time
        on_tick_and_append_step(spec, store, current_time, test_steps)

        yield from add_attestations(spec, store, attestations, test_steps)

        # Inject the non-canonical confirmed_root at *mid-epoch* slot start
        if slot + 1 == trigger_slot:
            assert fork2_root is not None
            head = spec.get_head(store)
            assert not spec.is_ancestor(store, head, fork2_root)  
            store.confirmed_root = fork2_root


        on_slot_start_after_past_attestations_applied_and_append_step(spec, store, test_steps)

    # Confirmed must be finalized (we prevented restart)
    assert store.confirmed_root == store.finalized_checkpoint.root

    yield "steps", test_steps

#  At an epoch boundary, if the previously confirmed chain cannot be re-confirmed, FCR must reset confirmed_root to finalized.

@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_reverts_to_finalized_when_reconfirmation_fails_at_epoch_start(spec, state):
    test_steps = []

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    attestations = []
    last_root = anchor_block.hash_tree_root()

    epoch2_start = spec.SLOTS_PER_EPOCH * 2

    # Build a canonical chain up to the start of epoch 2
    for slot in range(spec.GENESIS_SLOT, epoch2_start):
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

    # Sanity: we are at an epoch boundary now
    assert spec.is_start_slot_at_epoch(spec.get_current_slot(store))

    # Force confirmed_root to be a recent canonical block (not finalized)
    assert last_root != store.finalized_checkpoint.root
    store.confirmed_root = last_root

    # Sanity: the other two disjuncts do NOT trigger
    head = spec.get_head(store)
    current_epoch = spec.get_current_store_epoch(store)
    assert spec.get_block_epoch(store, store.confirmed_root) + 1 >= current_epoch   # not too old
    assert spec.is_ancestor(store, head, store.confirmed_root)                     # canonical

    # Prevent the restart clause from overriding the "revert to finalized" outcome:
    # pick a very old observed-justified (finalized) anchor.
    store.current_epoch_observed_justified_checkpoint = spec.Checkpoint(
        epoch=spec.Epoch(0),
        root=store.finalized_checkpoint.root,
    )

    # Precondition for "reconfirmation-failure => revert":
    # we must be in the regime GU <= confirmed (GU is ancestor of confirmed).
    assert spec.is_ancestor(store, store.confirmed_root, store.current_epoch_observed_justified_checkpoint.root)

    # Force reconfirmation failure: wipe latest votes so is_one_confirmed(...) fails.
    store.latest_messages = {}

    # Run epoch-start handler: should detect reconfirmation failure and revert to finalized.
    on_slot_start_after_past_attestations_applied_and_append_step(spec, store, test_steps)

    assert store.confirmed_root == store.finalized_checkpoint.root

    yield "steps", test_steps

#  At an epoch boundary, if the previously confirmed chain cannot be re-confirmed, FCR must reset confirmed_root to finalized. (v2)

@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_reverts_to_finalized_when_reconfirmation_fails_at_epoch_start_partial_vote_flip(spec, state):
    test_steps = []

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    attestations = []
    last_root = anchor_block.hash_tree_root()

    epoch2_start = spec.SLOTS_PER_EPOCH * 2

    # We'll create a sibling fork at some slot in epoch 1 (so it exists in the store),
    # but keep the canonical head on the main chain via attestations.
    fork_slot = spec.SLOTS_PER_EPOCH + 1  # epoch 1, slot 1
    fork_root = None

    # Build canonical chain up to start of epoch 2
    for slot in range(spec.GENESIS_SLOT, epoch2_start):
        if slot > spec.GENESIS_SLOT:
            # If next block is at fork_slot, snapshot state so we can build a sibling at same parent/slot.
            pre_state = copy.deepcopy(state) if (state.slot + 1 == fork_slot) else None

            # Canonical block
            block = build_empty_block_for_next_slot(spec, state)
            for att in attestations:
                block.body.attestations.append(att)
            signed = state_transition_and_sign_block(spec, state, block)
            yield from add_block(spec, store, signed, test_steps)
            last_root = signed.message.hash_tree_root()

            # Competing sibling block (same parent/slot, different contents)
            if pre_state is not None:
                sib = build_empty_block_for_next_slot(spec, pre_state)
                for att in attestations:
                    sib.body.attestations.append(att)
                sib.body.graffiti = b"i love ethereum".ljust(32, b"\x00")
                signed_sib = state_transition_and_sign_block(spec, pre_state, sib)
                yield from add_block(spec, store, signed_sib, test_steps)
                fork_root = signed_sib.message.hash_tree_root()

        # Attest to the current head to keep the main chain canonical
        attestations = get_valid_attestations_for_block_at_slot(
            spec, state, state.slot, spec.get_head(store)
        )

        current_time = (slot + 1) * spec.config.SECONDS_PER_SLOT + store.genesis_time
        on_tick_and_append_step(spec, store, current_time, test_steps)

        yield from add_attestations(spec, store, attestations, test_steps)
        on_slot_start_after_past_attestations_applied_and_append_step(spec, store, test_steps)

    # Sanity: we are at an epoch boundary now
    assert spec.is_start_slot_at_epoch(spec.get_current_slot(store))
    assert fork_root is not None

    # Force confirmed_root to be a recent canonical block (not finalized)
    assert last_root != store.finalized_checkpoint.root
    store.confirmed_root = last_root

    # Other two disjuncts do NOT trigger (not too old, still canonical)
    head_before = spec.get_head(store)
    current_epoch = spec.get_current_store_epoch(store)
    assert spec.get_block_epoch(store, store.confirmed_root) + 1 >= current_epoch
    assert spec.is_ancestor(store, head_before, store.confirmed_root)  # confirmed ⪯ head

    # Make sure fork_root is indeed *not* on the canonical head chain (i.e., not an ancestor of head)
    assert not spec.is_ancestor(store, head_before, fork_root)

    # Prevent restart clause from overriding the revert-to-finalized outcome:
    store.current_epoch_observed_justified_checkpoint = spec.Checkpoint(
        epoch=spec.Epoch(0),
        root=store.finalized_checkpoint.root,
    )

    # Precondition for the reconfirmation regime:
    # GU must be ancestor of confirmed_root, i.e., GU ⪯ confirmed.
    assert spec.is_ancestor(store, store.confirmed_root, store.current_epoch_observed_justified_checkpoint.root)

    # Target block whose one-confirmed support we want to break.
    victim_root = store.confirmed_root

    # Identify validators whose latest vote currently supports victim_root,
    # i.e., victim_root is an ancestor of the validator's latest vote root.
    supporters = []
    for vidx, msg in store.latest_messages.items():
        vote_root = msg.root
        if spec.is_ancestor(store, vote_root, victim_root):  # victim_root ⪯ vote_root
            supporters.append(vidx)

    assert len(supporters) > 0
    supporters.sort()

    # Find the minimum number of supporters to "flip" onto the sibling fork
    # such that reconfirmation fails and we revert to finalized.
    def would_revert_with_k_flipped(k: int) -> bool:
        tmp = copy.deepcopy(store)
        for vidx in supporters[:k]:
            old = tmp.latest_messages[vidx]
            tmp.latest_messages[vidx] = spec.LatestMessage(epoch=old.epoch, root=fork_root)
        on_slot_start_after_past_attestations_applied_and_append_step(spec, tmp, [])
        return tmp.confirmed_root == tmp.finalized_checkpoint.root

    k_star = None
    for k in range(1, len(supporters) + 1):
        if would_revert_with_k_flipped(k):
            k_star = k
            break

    assert k_star is not None
    assert k_star < len(supporters)

    # Apply the minimal flip on the real store
    for vidx in supporters[:k_star]:
        old = store.latest_messages[vidx]
        store.latest_messages[vidx] = spec.LatestMessage(epoch=old.epoch, root=fork_root)

    # Sanity: we didn’t accidentally flip the head to the fork (we want the reconfirmation path)
    head_after = spec.get_head(store)
    assert head_after == head_before

    # Run epoch-start handler: should detect reconfirmation failure and revert to finalized.
    on_slot_start_after_past_attestations_applied_and_append_step(spec, store, test_steps)

    assert store.confirmed_root == store.finalized_checkpoint.root

    yield "steps", test_steps


#  At mid epoch, if the previously confirmed chain cannot be re-confirmed, FCR must *not* reset confirmed_root to finalized.

@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
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
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
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