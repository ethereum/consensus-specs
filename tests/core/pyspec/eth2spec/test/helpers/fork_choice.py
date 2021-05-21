from eth_utils import encode_hex


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


def tick_and_run_on_block(spec, store, signed_block, test_steps=None):
    if test_steps is None:
        test_steps = []

    pre_state = store.block_states[signed_block.message.parent_root]
    block_time = pre_state.genesis_time + signed_block.message.slot * spec.config.SECONDS_PER_SLOT

    if store.time < block_time:
        on_tick_and_append_step(spec, store, block_time, test_steps)

    yield from run_on_block(spec, store, signed_block, test_steps)


def tick_and_run_on_attestation(spec, store, attestation, test_steps=None):
    if test_steps is None:
        test_steps = []

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


def run_on_block(spec, store, signed_block, test_steps, valid=True):
    if not valid:
        try:
            spec.on_block(store, signed_block)

        except AssertionError:
            return
        else:
            assert False

    spec.on_block(store, signed_block)
    yield get_block_file_name(signed_block), signed_block
    test_steps.append({'block': get_block_file_name(signed_block)})

    # An on_block step implies receiving block's attestations
    for attestation in signed_block.message.body.attestations:
        spec.on_attestation(store, attestation)

    assert store.blocks[signed_block.message.hash_tree_root()] == signed_block.message
    test_steps.append({
        'checks': {
            'time': int(store.time),
            'head': get_formatted_head_output(spec, store),
            'justified_checkpoint_root': encode_hex(store.justified_checkpoint.root),
            'finalized_checkpoint_root': encode_hex(store.finalized_checkpoint.root),
            'best_justified_checkpoint': encode_hex(store.best_justified_checkpoint.root),
        }
    })


def get_formatted_head_output(spec, store):
    head = spec.get_head(store)
    slot = store.blocks[head].slot
    return {
        'slot': int(slot),
        'root': encode_hex(head),
    }
