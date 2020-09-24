from eth2spec.phase0 import spec as phase0_spec


def get_anchor_root(spec, state):
    anchor_block_header = state.latest_block_header.copy()
    if anchor_block_header.state_root == spec.Bytes32():
        anchor_block_header.state_root = spec.hash_tree_root(state)
    return spec.hash_tree_root(anchor_block_header)


def add_block_to_store(spec, store, signed_block):
    pre_state = store.block_states[signed_block.message.parent_root]
    block_time = pre_state.genesis_time + signed_block.message.slot * spec.SECONDS_PER_SLOT

    if store.time < block_time:
        spec.on_tick(store, block_time)

    spec.on_block(store, signed_block)


def add_attestation_to_store(spec, store, attestation):
    parent_block = store.blocks[attestation.data.beacon_block_root]
    pre_state = store.block_states[spec.hash_tree_root(parent_block)]
    block_time = pre_state.genesis_time + parent_block.slot * spec.SECONDS_PER_SLOT
    next_epoch_time = block_time + spec.SLOTS_PER_EPOCH * spec.SECONDS_PER_SLOT

    if store.time < next_epoch_time:
        spec.on_tick(store, next_epoch_time)

    spec.on_attestation(store, attestation)


def get_genesis_forkchoice_store(spec, genesis_state):
    assert genesis_state.slot == spec.GENESIS_SLOT
    # The genesis block must be a Phase 0 `BeaconBlock`
    genesis_block = phase0_spec.BeaconBlock(state_root=genesis_state.hash_tree_root())
    return spec.get_forkchoice_store(genesis_state, genesis_block)
