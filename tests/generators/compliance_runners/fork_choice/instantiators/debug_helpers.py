from eth2spec.test.helpers.state import (
    transition_to,
)


def attesters_in_block(spec, epoch_state, signed_block, target_epoch):
    block = signed_block.message
    attesters = set()
    for a in block.body.attestations:
        if a.data.target.epoch == target_epoch:
            attesters.update(spec.get_attesting_indices(epoch_state, a.data, a.aggregation_bits))
    return attesters


def print_block(spec, epoch_state, signed_block):
    block = signed_block.message
    if spec.get_current_epoch(epoch_state) > spec.GENESIS_EPOCH:
        prev_attesters = attesters_in_block(
            spec, epoch_state, signed_block, spec.get_previous_epoch(epoch_state)
        )
    else:
        prev_attesters = set()

    curr_attesters = attesters_in_block(
        spec, epoch_state, signed_block, spec.get_current_epoch(epoch_state)
    )
    prev_attester_str = "a_prev=" + str(prev_attesters) if any(prev_attesters) else "a_prev={}"
    curr_attester_str = "a_curr=" + str(curr_attesters) if any(curr_attesters) else "a_curr={}"

    return (
        "b(r="
        + str(spec.hash_tree_root(block))[:6]
        + ", p="
        + str(block.proposer_index)
        + ", "
        + prev_attester_str
        + ", "
        + curr_attester_str
        + ")"
    )


def print_slot_range(spec, root_state, signed_blocks, start_slot, end_slot):
    ret = ""
    epoch_state = root_state.copy()
    for slot in range(start_slot, end_slot):
        transition_to(spec, epoch_state, slot)
        blocks_in_slot = [b for b in signed_blocks if b.message.slot == slot]
        if ret != "":
            ret = ret + " <- "
        if any(blocks_in_slot):
            ret = (
                ret
                + "s("
                + str(slot)
                + ", "
                + print_block(spec, epoch_state, blocks_in_slot[0])
                + ")"
            )
        else:
            ret = ret + "s(" + str(slot) + ", _)"

    return ret


def print_epoch(spec, epoch_state, signed_blocks):
    epoch = spec.get_current_epoch(epoch_state)
    start_slot = spec.compute_start_slot_at_epoch(epoch)
    return print_slot_range(
        spec, epoch_state, signed_blocks, start_slot, start_slot + spec.SLOTS_PER_EPOCH
    )


def print_block_tree(spec, root_state, signed_blocks):
    start_slot = signed_blocks[0].message.slot
    end_slot = signed_blocks[len(signed_blocks) - 1].message.slot + 1
    return print_slot_range(spec, root_state, signed_blocks, start_slot, end_slot)


def print_head(spec, store):
    head = spec.get_head(store)
    weight = spec.get_weight(store, head)
    state = store.checkpoint_states[store.justified_checkpoint]
    total_active_balance = spec.get_total_active_balance(state)

    return (
        "(slot="
        + str(store.blocks[head].slot)
        + ", root="
        + str(head)[:6]
        + ", weight="
        + str(weight * 100 // total_active_balance)
        + "%)"
    )
