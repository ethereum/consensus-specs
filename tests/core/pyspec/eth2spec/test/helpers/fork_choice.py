from eth_utils import encode_hex
from eth2spec.test.helpers.attestations import (
    next_epoch_with_attestations,
    next_slots_with_attestations,
)


def get_anchor_root(spec, state):
    anchor_block_header = state.latest_block_header.copy()
    if anchor_block_header.state_root == spec.Bytes32():
        anchor_block_header.state_root = spec.hash_tree_root(state)
    return spec.hash_tree_root(anchor_block_header)


def add_block_to_store(spec, store, signed_block):
    pre_state = store.block_states[signed_block.message.parent_root]
    block_time = pre_state.genesis_time + signed_block.message.slot * spec.config.SECONDS_PER_SLOT

    if store.time < block_time:
        spec.on_tick(store, block_time)

    spec.on_block(store, signed_block)


def tick_and_add_block(spec, store, signed_block, test_steps, valid=True, allow_invalid_attestations=False):
    pre_state = store.block_states[signed_block.message.parent_root]
    block_time = pre_state.genesis_time + signed_block.message.slot * spec.config.SECONDS_PER_SLOT

    if store.time < block_time:
        on_tick_and_append_step(spec, store, block_time, test_steps)

    post_state = yield from add_block(
        spec, store, signed_block, test_steps, valid=valid, allow_invalid_attestations=allow_invalid_attestations)

    return post_state


def tick_and_run_on_attestation(spec, store, attestation, test_steps):
    parent_block = store.blocks[attestation.data.beacon_block_root]
    pre_state = store.block_states[spec.hash_tree_root(parent_block)]
    block_time = pre_state.genesis_time + parent_block.slot * spec.config.SECONDS_PER_SLOT
    next_epoch_time = block_time + spec.SLOTS_PER_EPOCH * spec.config.SECONDS_PER_SLOT

    if store.time < next_epoch_time:
        spec.on_tick(store, next_epoch_time)
        test_steps.append({'tick': int(next_epoch_time)})

    spec.on_attestation(store, attestation)
    yield get_attestation_file_name(attestation), attestation
    test_steps.append({'attestation': get_attestation_file_name(attestation)})


def add_attestation(spec, store, attestation, test_steps, valid=True):
    yield get_attestation_file_name(attestation), attestation

    if not valid:
        try:
            run_on_attestation(spec, store, attestation, valid=True)
        except AssertionError:
            test_steps.append({
                'attestation': get_attestation_file_name(attestation),
                'valid': False,
            })
            return
        else:
            assert False

    run_on_attestation(spec, store, attestation, valid=True)
    test_steps.append({'attestation': get_attestation_file_name(attestation)})


def run_on_attestation(spec, store, attestation, valid=True):
    if not valid:
        try:
            spec.on_attestation(store, attestation)
        except AssertionError:
            return
        else:
            assert False

    spec.on_attestation(store, attestation)


def get_genesis_forkchoice_store(spec, genesis_state):
    store, _ = get_genesis_forkchoice_store_and_block(spec, genesis_state)
    return store


def get_genesis_forkchoice_store_and_block(spec, genesis_state):
    assert genesis_state.slot == spec.GENESIS_SLOT
    genesis_block = spec.BeaconBlock(state_root=genesis_state.hash_tree_root())
    return spec.get_forkchoice_store(genesis_state, genesis_block), genesis_block


def get_block_file_name(block):
    return f"block_{encode_hex(block.hash_tree_root())}"


def get_attestation_file_name(attestation):
    return f"attestation_{encode_hex(attestation.hash_tree_root())}"


def on_tick_and_append_step(spec, store, time, test_steps):
    spec.on_tick(store, time)
    test_steps.append({'tick': int(time)})


def run_on_block(spec, store, signed_block, valid=True):
    if not valid:
        try:
            spec.on_block(store, signed_block)
        except AssertionError:
            return
        else:
            assert False

    spec.on_block(store, signed_block)
    assert store.blocks[signed_block.message.hash_tree_root()] == signed_block.message


def add_block(spec, store, signed_block, test_steps, valid=True, allow_invalid_attestations=False):
    """
    Run on_block and on_attestation
    """
    yield get_block_file_name(signed_block), signed_block

    if not valid:
        try:
            run_on_block(spec, store, signed_block, valid=True)
        except AssertionError:
            test_steps.append({
                'block': get_block_file_name(signed_block),
                'valid': False,
            })
            return
        else:
            assert False

    run_on_block(spec, store, signed_block, valid=True)
    test_steps.append({'block': get_block_file_name(signed_block)})

    # An on_block step implies receiving block's attestations
    try:
        for attestation in signed_block.message.body.attestations:
            run_on_attestation(spec, store, attestation, valid=True)
    except AssertionError:
        if allow_invalid_attestations:
            pass
        else:
            raise

    block_root = signed_block.message.hash_tree_root()
    assert store.blocks[block_root] == signed_block.message
    assert store.block_states[block_root].hash_tree_root() == signed_block.message.state_root
    test_steps.append({
        'checks': {
            'time': int(store.time),
            'head': get_formatted_head_output(spec, store),
            'justified_checkpoint': {
                'epoch': int(store.justified_checkpoint.epoch),
                'root': encode_hex(store.justified_checkpoint.root),
            },
            'finalized_checkpoint': {
                'epoch': int(store.finalized_checkpoint.epoch),
                'root': encode_hex(store.finalized_checkpoint.root),
            },
            'best_justified_checkpoint': {
                'epoch': int(store.best_justified_checkpoint.epoch),
                'root': encode_hex(store.best_justified_checkpoint.root),
            },
        }
    })

    return store.block_states[signed_block.message.hash_tree_root()]


def get_formatted_head_output(spec, store):
    head = spec.get_head(store)
    slot = store.blocks[head].slot
    return {
        'slot': int(slot),
        'root': encode_hex(head),
    }


def apply_next_epoch_with_attestations(spec,
                                       state,
                                       store,
                                       fill_cur_epoch,
                                       fill_prev_epoch,
                                       participation_fn=None,
                                       test_steps=None):
    if test_steps is None:
        test_steps = []

    _, new_signed_blocks, post_state = next_epoch_with_attestations(
        spec, state, fill_cur_epoch, fill_prev_epoch, participation_fn=participation_fn)
    for signed_block in new_signed_blocks:
        block = signed_block.message
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        block_root = block.hash_tree_root()
        assert store.blocks[block_root] == block
        last_signed_block = signed_block

    assert store.block_states[block_root].hash_tree_root() == post_state.hash_tree_root()

    return post_state, store, last_signed_block


def apply_next_slots_with_attestations(spec,
                                       state,
                                       store,
                                       slots,
                                       fill_cur_epoch,
                                       fill_prev_epoch,
                                       test_steps,
                                       participation_fn=None):
    _, new_signed_blocks, post_state = next_slots_with_attestations(
        spec, state, slots, fill_cur_epoch, fill_prev_epoch, participation_fn=participation_fn)
    for signed_block in new_signed_blocks:
        block = signed_block.message
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        block_root = block.hash_tree_root()
        assert store.blocks[block_root] == block
        last_signed_block = signed_block

    assert store.block_states[block_root].hash_tree_root() == post_state.hash_tree_root()

    return post_state, store, last_signed_block
