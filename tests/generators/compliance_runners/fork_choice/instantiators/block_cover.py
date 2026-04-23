import random

from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
    run_on_block,
    run_on_attestation,
    run_on_attester_slashing,
    run_on_execution_payload_envelope,
    run_on_payload_attestation_message,
)
from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.forks import is_post_gloas
from eth_consensus_specs.test.helpers.state import (
    next_slot,
    transition_to,
)
from eth_consensus_specs.utils import bls

from .helpers import (
    advance_state_to_anchor_epoch,
    attest_to_slot,
    build_random_payload_attestation_messages,
    BranchTip,
    FCTestData,
    payload_attestation_to_messages,
    produce_block,
    ProtocolMessage,
)


def _should_justify_epoch(parents, current_justifications, previous_justifications, block) -> bool:
    if current_justifications[block]:
        return True

    # Check if any child of the block justifies the epoch
    for c in (b for b, p in enumerate(parents) if p == block):
        if previous_justifications[c]:
            return True

    return False


def _generate_filter_block_tree(
    spec,
    genesis_state,
    block_epochs,
    parents,
    previous_justifications,
    current_justifications,
    rnd: random.Random,
    debug,
) -> ([], [], [], []):
    JUSTIFYING_SLOT = 2 * spec.SLOTS_PER_EPOCH // 3 + 1
    JUSTIFYING_SLOT_COUNT = spec.SLOTS_PER_EPOCH - JUSTIFYING_SLOT

    anchor_epoch = block_epochs[0]

    # Run constraint checks before starting to generate blocks
    for epoch in range(anchor_epoch + 1, max(block_epochs) + 1):
        current_blocks = [i for i, e in enumerate(block_epochs) if e == epoch]
        assert len(current_blocks) <= spec.SLOTS_PER_EPOCH, (
            "Number of blocks does not fit into an epoch=" + str(epoch)
        )

        justifying_blocks = [
            b
            for b in current_blocks
            if _should_justify_epoch(parents, current_justifications, previous_justifications, b)
        ]
        current_justifying_blocks = [b for b in justifying_blocks if current_justifications[b]]
        previous_only_justifying_blocks = [b for b in justifying_blocks if not current_justifications[b]]

        # There should be enough slots to propose all blocks that are required to justify the epoch
        assert len(justifying_blocks) <= JUSTIFYING_SLOT_COUNT, (
            "Not enough slots to accommodate blocks justifying epoch=" + str(epoch)
        )

    signed_blocks, anchor_tip = advance_state_to_anchor_epoch(
        spec, genesis_state, anchor_epoch, debug
    )

    block_tips = [None for _ in range(0, len(block_epochs))]
    model_blocks = [None for _ in range(0, len(block_epochs))]
    model_post_states = [None for _ in range(0, len(block_epochs))]
    # Initialize with the anchor block
    block_tips[0] = anchor_tip

    for epoch in range(anchor_epoch + 1, max(block_epochs) + 1):
        current_blocks = [i for i, e in enumerate(block_epochs) if e == epoch]
        if len(current_blocks) == 0:
            continue

        # Case 2. Blocks are from disjoint subtrees -- not supported yet
        assert len(set([a for i, a in enumerate(parents) if i in current_blocks])) == 1, (
            "Disjoint trees are not supported"
        )

        # Case 1. Blocks have common ancestor
        a = parents[current_blocks[0]]
        ancestor_tip = block_tips[a].copy()

        state = ancestor_tip.beacon_state
        attestations = ancestor_tip.attestations

        justifying_blocks = [
            b
            for b in current_blocks
            if _should_justify_epoch(parents, current_justifications, previous_justifications, b)
        ]

        common_prefix_len = min(JUSTIFYING_SLOT, spec.SLOTS_PER_EPOCH - len(current_blocks))
        threshold_slot = spec.compute_start_slot_at_epoch(epoch) + common_prefix_len

        # Build the chain up to but excluding a block that will justify current checkpoint
        while state.slot < threshold_slot:
            # Do not include attestations into blocks
            if state.slot < spec.compute_start_slot_at_epoch(epoch):
                new_block, state, _, _, _ = produce_block(spec, state, [])
                signed_blocks.append(new_block)
            else:
                # Prevent previous epoch from being accidentally justified
                # by filtering out previous epoch attestations
                curr_epoch_attestations = [
                    a for a in attestations if epoch == spec.compute_epoch_at_slot(a.data.slot)
                ]
                other_attestations = [a for a in attestations if a not in curr_epoch_attestations]
                new_block, state, curr_epoch_attestations, _, _ = produce_block(
                    spec, state, curr_epoch_attestations
                )
                attestations = other_attestations + curr_epoch_attestations
                signed_blocks.append(new_block)

            # Attest
            curr_slot_attestations = attest_to_slot(spec, state, state.slot)
            attestations = curr_slot_attestations + attestations

            # Next slot
            next_slot(spec, state)

        common_state = state

        # Assumption: one block is enough to satisfy previous_justifications[b] and current_justifications[b],
        # i.e. block capacity is enough to accommodate attestations to justify previous and current epoch checkpoints
        # if that needed. Considering that most of attestations were already included into the common chain prefix,
        # we assume it is possible
        empty_slot_count = spec.SLOTS_PER_EPOCH - common_prefix_len - len(current_blocks)
        prefix_window_len = JUSTIFYING_SLOT - common_prefix_len
        suffix_window_len = spec.SLOTS_PER_EPOCH - JUSTIFYING_SLOT

        remaining_items = [b for b in current_blocks if b not in justifying_blocks]
        remaining_items = remaining_items + [-1 for _ in range(0, empty_slot_count)]
        rnd.shuffle(remaining_items)

        suffix_extra_count = suffix_window_len - len(justifying_blocks)
        suffix_extras = remaining_items[:suffix_extra_count]
        prefix_items = remaining_items[suffix_extra_count:]

        assert len(prefix_items) == prefix_window_len
        assert len(suffix_extras) + len(previous_only_justifying_blocks) + len(
            current_justifying_blocks
        ) == suffix_window_len

        rnd.shuffle(prefix_items)
        rnd.shuffle(suffix_extras)
        rnd.shuffle(previous_only_justifying_blocks)
        rnd.shuffle(current_justifying_blocks)
        suffix_items = (
            suffix_extras + previous_only_justifying_blocks + current_justifying_blocks
        )
        block_distribution = prefix_items + suffix_items

        for index, block in enumerate(block_distribution):
            slot = threshold_slot + index
            state = common_state.copy()

            # Advance state to the slot
            if state.slot < slot:
                transition_to(spec, state, slot)

            # Propose a block if slot isn't empty
            block_attestations = []
            if block > -1:
                previous_epoch_attestations = [
                    a for a in attestations if epoch == spec.compute_epoch_at_slot(a.data.slot) + 1
                ]
                current_epoch_attestations = [
                    a for a in attestations if epoch == spec.compute_epoch_at_slot(a.data.slot)
                ]
                if previous_justifications[block]:
                    block_attestations = block_attestations + previous_epoch_attestations
                if current_justifications[block]:
                    block_attestations = block_attestations + current_epoch_attestations

                # Propose block
                new_block, state, _, _, _ = produce_block(spec, state, block_attestations)
                signed_blocks.append(new_block)
                model_blocks[block] = new_block
                model_post_states[block] = state.copy()

            # Attest
            # TODO pick a random tip to make attestation with if the slot is empty
            curr_slot_attestations = attest_to_slot(spec, state, state.slot)
            attestations = curr_slot_attestations + attestations

            # Next slot
            next_slot(spec, state)

            if block > -1:
                not_included_attestations = [a for a in attestations if a not in block_attestations]

                check_up_state = state.copy()
                spec.process_justification_and_finalization(check_up_state)

                if current_justifications[block]:
                    assert check_up_state.current_justified_checkpoint.epoch == epoch, (
                        "Unexpected current_jusitified_checkpoint.epoch: "
                        + str(check_up_state.current_justified_checkpoint.epoch)
                        + " != "
                        + str(epoch)
                    )
                elif previous_justifications[block]:
                    assert check_up_state.current_justified_checkpoint.epoch + 1 == epoch, (
                        "Unexpected current_jusitified_checkpoint.epoch: "
                        + str(check_up_state.current_justified_checkpoint.epoch)
                        + " != "
                        + str(epoch - 1)
                    )

                block_tips[block] = BranchTip(
                    state,
                    not_included_attestations,
                    [*range(0, len(state.validators))],
                    check_up_state.current_justified_checkpoint,
                )

    return signed_blocks, block_tips, model_blocks, model_post_states


def _debug_run_sanity_checks(
    spec,
    anchor_state,
    anchor_block,
    signed_blocks,
    envelopes,
    payload_attestations,
    model_params,
    target_block_root,
):
    store = spec.get_forkchoice_store(anchor_state, anchor_block)
    envelopes_by_block_root = {e.payload.message.beacon_block_root: e.payload for e in envelopes}
    payload_attestations_by_block_root = {}
    for ptc_message in payload_attestations:
        payload_attestations_by_block_root.setdefault(ptc_message.data.beacon_block_root, []).append(
            ptc_message
        )

    def debug_add_block(signed_block):
        run_on_block(spec, store, signed_block, valid=True)

        for attestation in signed_block.message.body.attestations:
            try:
                run_on_attestation(spec, store, attestation, is_from_block=True, valid=True)
            except AssertionError:
                pass

        for attester_slashing in signed_block.message.body.attester_slashings:
            try:
                run_on_attester_slashing(spec, store, attester_slashing, valid=True)
            except AssertionError:
                pass

        if is_post_gloas(spec):
            state = store.block_states[signed_block.message.hash_tree_root()]
            for payload_attestation in signed_block.message.body.payload_attestations:
                for ptc_message in payload_attestation_to_messages(spec, state, payload_attestation):
                    run_on_payload_attestation_message(
                        spec, store, ptc_message, is_from_block=True, valid=True
                    )

            envelope = envelopes_by_block_root.get(signed_block.message.hash_tree_root())
            if envelope is not None:
                run_on_execution_payload_envelope(spec, store, envelope, valid=True)

            for ptc_message in payload_attestations_by_block_root.get(
                signed_block.message.hash_tree_root(), []
            ):
                run_on_payload_attestation_message(spec, store, ptc_message, valid=True)

    for signed_block in signed_blocks:
        block_time = (
            anchor_state.genesis_time
            + signed_block.message.slot * spec.config.SLOT_DURATION_MS // 1000
        )
        if block_time > store.time:
            spec.on_tick(store, block_time)
        debug_add_block(signed_block)

    current_epoch_slot = spec.compute_start_slot_at_epoch(model_params["current_epoch"])
    current_epoch_time = (
        anchor_state.genesis_time + current_epoch_slot * spec.config.SLOT_DURATION_MS // 1000
    )
    if current_epoch_time > store.time:
        spec.on_tick(store, current_epoch_time)

    run_sanity_checks(spec, store, model_params, target_block_root)


def gen_block_cover_test_data(spec, state, model_params, debug, seed) -> (FCTestData, object):
    anchor_state = state
    _, anchor_block = get_genesis_forkchoice_store_and_block(spec, anchor_state)

    if debug:
        print("\nseed:", seed)
        print("model_params:", str(model_params))

    block_epochs = model_params["block_epochs"]
    parents = model_params["parents"]
    previous_justifications = model_params["previous_justifications"]
    current_justifications = model_params["current_justifications"]

    store_justified_epoch = model_params["store_justified_epoch"]
    target_block = model_params["target_block"]

    # Ensure that there is no attempt to justify GENESIS_EPOCH + 1 as it is not supported by the protocol
    assert store_justified_epoch != spec.GENESIS_EPOCH + 1, (
        "Justification of epoch 1 is not supported by the protocol"
    )

    # Ensure that epoch(block) == epoch(parent) + 1
    for b in range(1, len(block_epochs)):
        assert block_epochs[b] == block_epochs[parents[b]] + 1, (
            "epoch("
            + str(b)
            + ") != epoch("
            + str(parents[b])
            + ") + 1, block_epochs="
            + str(block_epochs)
            + ", parents="
            + str(parents)
        )

    # Ensure that a descendant doesn't attempt to justify the previous epoch checkpoint
    # if it has already been justified by its ancestor
    for b in range(1, len(block_epochs)):
        if previous_justifications[b]:
            a = parents[b]
            assert not current_justifications[a], (
                str(b) + " attempts to justify already justified epoch"
            )

    rnd = random.Random(seed)
    signed_blocks, post_block_tips, model_blocks, model_post_states = _generate_filter_block_tree(
        spec,
        state,
        block_epochs,
        parents,
        previous_justifications,
        current_justifications,
        rnd,
        debug,
    )

    # Meta data
    meta = {
        "seed": seed,
        "model_params": model_params,
        "bls_setting": 0 if bls.bls_active else 2,
    }

    blocks = [ProtocolMessage(block) for block in signed_blocks]
    envelopes = []
    payload_attestations = []

    current_epoch_slot = spec.compute_start_slot_at_epoch(model_params["current_epoch"])
    current_epoch_time = (
        state.genesis_time + current_epoch_slot * spec.config.SLOT_DURATION_MS // 1000
    )

    test_data = FCTestData(
        meta, anchor_block, anchor_state, blocks, store_final_time=current_epoch_time
    )
    target_block_root = spec.hash_tree_root(
        post_block_tips[target_block].beacon_state.latest_block_header
    )
    if is_post_gloas(spec):
        target_signed_block = model_blocks[target_block]
        target_post_state = model_post_states[target_block]
        if target_signed_block is not None and target_post_state is not None:
            envelope_mode = rnd.choice(["none", "valid"])
            if envelope_mode == "valid":
                envelopes.append(
                    ProtocolMessage(
                        build_signed_execution_payload_envelope(
                            spec, target_post_state, target_block_root, target_signed_block
                        )
                    )
                )
                for ptc_message in build_random_payload_attestation_messages(
                    spec,
                    target_post_state,
                    target_block_root,
                    target_signed_block.message.slot,
                    rnd,
                ):
                    payload_attestations.append(ProtocolMessage(ptc_message))

    test_data.envelopes = envelopes
    test_data.payload_atts = payload_attestations

    if debug:
        _debug_run_sanity_checks(
            spec,
            anchor_state,
            anchor_block,
            signed_blocks,
            envelopes,
            [m.payload for m in payload_attestations],
            model_params,
            target_block_root,
        )

    return test_data, target_block_root


def run_sanity_checks(spec, store, model_params, target_block_root):
    current_epoch = spec.get_current_store_epoch(store)
    # Ensure the epoch is correct
    assert current_epoch == model_params["current_epoch"], (
        str(current_epoch) + " != " + str(model_params["current_epoch"])
    )
    # Ensure the store.justified_checkpoint.epoch is as expected
    assert store.justified_checkpoint.epoch == model_params["store_justified_epoch"]

    # Check predicates
    predicates = model_params["predicates"]
    if predicates["store_je_eq_zero"]:
        assert store.justified_checkpoint.epoch == spec.GENESIS_EPOCH, (
            "store_je_eq_zero not satisfied"
        )

    if predicates["block_is_leaf"]:
        assert not any(b for b in store.blocks.values() if b.parent_root == target_block_root), (
            "block_is_leaf not satisfied"
        )
    else:
        assert any(b for b in store.blocks.values() if b.parent_root == target_block_root), (
            "block_is_leaf not satisfied"
        )

    voting_source = spec.get_voting_source(store, target_block_root)
    if predicates["block_vse_eq_store_je"]:
        assert voting_source.epoch == store.justified_checkpoint.epoch, (
            "block_vse_eq_store_je not satisfied"
        )
    else:
        assert voting_source.epoch != store.justified_checkpoint.epoch, (
            "block_vse_eq_store_je not satisfied"
        )

    if predicates["block_vse_plus_two_ge_curr_e"]:
        assert voting_source.epoch + 2 >= current_epoch, (
            "block_vse_plus_two_ge_curr_e not satisfied"
        )
    else:
        assert voting_source.epoch + 2 < current_epoch, "block_vse_plus_two_ge_curr_e not satisfied"

    # Ensure the target block is in filtered blocks if it is a leaf and eligible
    if predicates["block_is_leaf"] and (
        predicates["store_je_eq_zero"]
        or predicates["block_vse_eq_store_je"]
        or predicates["block_vse_plus_two_ge_curr_e"]
    ):
        assert target_block_root in spec.get_filtered_block_tree(store).keys()
