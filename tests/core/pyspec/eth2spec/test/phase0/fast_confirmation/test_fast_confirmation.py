import copy
from eth2spec.test.context import (
    MINIMAL,
    spec_state_test,
    with_altair_and_later,
    with_presets,
)
# Restored the original helper that exists in this branch
from eth2spec.test.helpers.attestations import (
    get_valid_attestations_for_block_at_slot,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.fast_confirmation import (
    on_slot_start_after_past_attestations_applied_and_append_step,
)
from eth2spec.test.helpers.fork_choice import (
    add_attestations,
    add_block,
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
)
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fast_confirm_an_epoch(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    attestations = []
    # run for each slot of the first epoch
    for slot in range(spec.GENESIS_SLOT, spec.SLOTS_PER_EPOCH):
        # build and sign a block
        if slot > spec.GENESIS_SLOT:
            block = build_empty_block_for_next_slot(spec, state)
            for attestation in attestations:
                block.body.attestations.append(attestation)
            signed_block = state_transition_and_sign_block(spec, state, block)
            yield from add_block(spec, store, signed_block, test_steps)
        else:
            block = anchor_block

        # attest and keep attestations for onchain inclusion
        attestations = get_valid_attestations_for_block_at_slot(
            spec, state, state.slot, block.hash_tree_root()
        )

        # move to the next slot
        current_time = (slot + 1) * spec.config.SECONDS_PER_SLOT + store.genesis_time
        on_tick_and_append_step(spec, store, current_time, test_steps)

        # apply attestations and run FCR
        yield from add_attestations(spec, store, attestations, test_steps)
        on_slot_start_after_past_attestations_applied_and_append_step(spec, store, test_steps)

        assert store.confirmed_root == block.hash_tree_root()

    yield "steps", test_steps

# FCR never confirms something non-canonical, and it never goes backwards (unless it resets to GF)

@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_invariants_monotone_and_canonical(spec, state):
    test_steps = []
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)

    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    attestations = []
    prev_confirmed_slot = store.blocks[store.confirmed_root].slot

    end_slot = spec.GENESIS_SLOT + 8

    for slot in range(spec.GENESIS_SLOT, end_slot):
        # build and sign a block
        if slot > spec.GENESIS_SLOT:
            block = build_empty_block_for_next_slot(spec, state)
            for attestation in attestations:
                block.body.attestations.append(attestation)
            signed_block = state_transition_and_sign_block(spec, state, block)
            yield from add_block(spec, store, signed_block, test_steps)
        else:
            block = anchor_block

        attestations = get_valid_attestations_for_block_at_slot(
            spec, state, state.slot, block.hash_tree_root()
        )

        current_time = (slot + 1) * spec.config.SECONDS_PER_SLOT + store.genesis_time
        on_tick_and_append_step(spec, store, current_time, test_steps)

        yield from add_attestations(spec, store, attestations, test_steps)
        on_slot_start_after_past_attestations_applied_and_append_step(spec, store, test_steps)

        head = spec.get_head(store)
        confirmed = store.confirmed_root

        # confirmed must be on canonical chain: confirmed is ancestor of head
        assert spec.is_ancestor(store, head, confirmed)

        # confirmed slot monotonic
        confirmed_slot = store.blocks[confirmed].slot
        finalized = store.finalized_checkpoint.root
        finalized_slot = store.blocks[finalized].slot

        if confirmed != finalized:
            assert confirmed_slot >= prev_confirmed_slot
        else:
            # if reset happened, it must reset exactly to finalized
            assert confirmed_slot == finalized_slot

        prev_confirmed_slot = confirmed_slot

    yield "steps", test_steps

# Stale confirmed_root => reset to finalized GF.

@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_reverts_to_finalized_when_confirmed_too_old_with_old_root(spec, state):
    test_steps = []

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    attestations = []

    target_slot = spec.SLOTS_PER_EPOCH * 2  
    old_root = None

    for slot in range(spec.GENESIS_SLOT, target_slot):
        if slot > spec.GENESIS_SLOT:
            block = build_empty_block_for_next_slot(spec, state)
            for att in attestations:
                block.body.attestations.append(att)
            signed_block = state_transition_and_sign_block(spec, state, block)
            yield from add_block(spec, store, signed_block, test_steps)

            # Remember an "old" (but canonical) block root to force confirmed_root later
            if old_root is None:
                old_root = signed_block.message.hash_tree_root()
        else:
            block = anchor_block
        
        attestations = get_valid_attestations_for_block_at_slot(
            spec, state, state.slot, block.hash_tree_root()
        )

        current_time = (slot + 1) * spec.config.SECONDS_PER_SLOT + store.genesis_time
        on_tick_and_append_step(spec, store, current_time, test_steps)

        yield from add_attestations(spec, store, attestations, test_steps)
        on_slot_start_after_past_attestations_applied_and_append_step(spec, store, test_steps)

    assert old_root is not None
    assert store.finalized_checkpoint.root != old_root

    # Force confirmed_root to be "too old" (still canonical)
    store.confirmed_root = old_root

    on_slot_start_after_past_attestations_applied_and_append_step(spec, store, test_steps)

    assert store.confirmed_root == store.finalized_checkpoint.root

    yield "steps", test_steps


# Stale confirmed root => revert to GF (v2, more realistic scenario)

@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_reverts_to_finalized_when_confirmed_too_old_lower_participation(spec, state):
    test_steps = []

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    attestations = []

    S = spec.SLOTS_PER_EPOCH
    epoch1_start = S
    epoch2_start = 2 * S
    epoch3_start = 3 * S

    # Start dropping attestations at a mid-epoch slot in epoch 1
    drop_slot = epoch1_start + (S // 2)
    assert drop_slot % S != 0  

    saw_nonfinal_confirmed = False

    # Run up to (and including) the epoch-3 start slot processing
    for slot in range(spec.GENESIS_SLOT, epoch3_start):
        if slot > spec.GENESIS_SLOT:
            block = build_empty_block_for_next_slot(spec, state)
            for att in attestations:
                block.body.attestations.append(att)
            signed = state_transition_and_sign_block(spec, state, block)
            yield from add_block(spec, store, signed, test_steps)

        if slot < drop_slot:
            head = spec.get_head(store)
            attestations = get_valid_attestations_for_block_at_slot(
                spec, state, state.slot, head
            )
        else:
            attestations = []

        current_time = (slot + 1) * spec.config.SECONDS_PER_SLOT + store.genesis_time
        on_tick_and_append_step(spec, store, current_time, test_steps)

        yield from add_attestations(spec, store, attestations, test_steps)
        on_slot_start_after_past_attestations_applied_and_append_step(spec, store, test_steps)

        # Confirmed was non-finalized before the drop
        if store.confirmed_root != store.finalized_checkpoint.root:
            saw_nonfinal_confirmed = True

        # At epoch 2 start, confirmed should still be in epoch <= 1
        if slot + 1 == epoch2_start:
            assert spec.is_start_slot_at_epoch(spec.get_current_slot(store))
            confirmed_epoch = spec.get_block_epoch(store, store.confirmed_root)
            assert confirmed_epoch <= spec.Epoch(1)

    assert saw_nonfinal_confirmed 

    # Now we are at the start of epoch 3. "Too old" condition on latest confirmed should have triggered.
    assert spec.is_start_slot_at_epoch(spec.get_current_slot(store))
    assert store.confirmed_root == store.finalized_checkpoint.root

    yield "steps", test_steps

# Confirmed blocks become non canonical => we revert to finalized (test beginning epoch)

@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_reverts_to_finalized_when_confirmed_not_canonical_at_epoch_start(spec, state):
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

    # Run until we reach start of epoch 2
    for slot in range(spec.GENESIS_SLOT, epoch2_start):
        if slot > spec.GENESIS_SLOT:
            if slot + 1== fork_slot:
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

        # At the *start of epoch 2*, force confirmed_root to the non-canonical fork2 root.
        if slot + 1 == epoch2_start:
            assert fork2_root is not None
            assert store.finalized_checkpoint.root != fork2_root

            head = spec.get_head(store)
            assert not spec.is_ancestor(store, head, fork2_root)

            # Prevent restart clause from overriding revert-to-finalized
            store.current_epoch_observed_justified_checkpoint = spec.Checkpoint(
                epoch=spec.Epoch(0),
                root=store.finalized_checkpoint.root,
            )

            store.confirmed_root = fork2_root

        on_slot_start_after_past_attestations_applied_and_append_step(spec, store, test_steps)

    # Confirmed must be finalized (we prevented restart)
    assert store.confirmed_root == store.finalized_checkpoint.root

    yield "steps", test_steps

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

@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_no_restart_when_GU_too_old_then_reset_to_finalized(spec, state):

    test_steps = []

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    attestations = []
    last_root = anchor_block.hash_tree_root()

    S = spec.SLOTS_PER_EPOCH
    epoch2_start = 2 * S
    epoch3_start = 3 * S

    gu_after_epoch2_start = None
    confirmed_after_epoch2_start = None

    for slot in range(spec.GENESIS_SLOT, epoch3_start):
        if slot > spec.GENESIS_SLOT:
            block = build_empty_block_for_next_slot(spec, state)
            for att in attestations:
                block.body.attestations.append(att)
            signed = state_transition_and_sign_block(spec, state, block)
            yield from add_block(spec, store, signed, test_steps)
            last_root = signed.message.hash_tree_root()

        # - full participation before epoch 2 start (i.e., epochs 0 and 1)
        # - zero participation starting in epoch 2 
        if slot < epoch2_start:
            head = spec.get_head(store)
            attestations = get_valid_attestations_for_block_at_slot(
                spec, state, state.slot, head
            )
        else:
            attestations = []

        current_time = (slot + 1) * spec.config.SECONDS_PER_SLOT + store.genesis_time
        on_tick_and_append_step(spec, store, current_time, test_steps)

        yield from add_attestations(spec, store, attestations, test_steps)
        on_slot_start_after_past_attestations_applied_and_append_step(spec, store, test_steps)

        # Capture right after epoch 2 start processing
        if slot + 1 == epoch2_start:
            assert spec.is_start_slot_at_epoch(spec.get_current_slot(store))
            assert spec.get_current_store_epoch(store) == spec.Epoch(2)

            gu_after_epoch2_start = store.current_epoch_observed_justified_checkpoint
            confirmed_after_epoch2_start = store.confirmed_root

            # Confirmed shouldn't already be finalized here
            assert confirmed_after_epoch2_start != store.finalized_checkpoint.root

            # It should also not be "too old" at epoch 2 start (otherwise we'd reset immediately)
            assert spec.get_block_epoch(store, confirmed_after_epoch2_start) + 1 >= spec.Epoch(2)

        # Check at epoch 3 start
        if slot + 1 == epoch3_start:
            assert spec.is_start_slot_at_epoch(spec.get_current_slot(store))
            current_epoch = spec.get_current_store_epoch(store)
            assert current_epoch == spec.Epoch(3)

            # GU must be stale because we had *no* epoch-2 attestations
            gu = store.current_epoch_observed_justified_checkpoint
            assert gu_after_epoch2_start is not None
            assert gu.epoch <= spec.Epoch(1)
            assert gu.epoch + 1 != current_epoch  # => restart clause cannot run

            # We should end up reset to finalized (and in particular not restart to GU)
            assert store.confirmed_root == store.finalized_checkpoint.root
            assert store.confirmed_root != gu.root

    yield "steps", test_steps