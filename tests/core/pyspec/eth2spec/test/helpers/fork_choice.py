from eth_utils import encode_hex

from eth2spec.phase0 import spec as phase0_spec


def get_anchor_root(spec, state):
    anchor_block_header = state.latest_block_header.copy()
    if anchor_block_header.state_root == spec.Bytes32():
        anchor_block_header.state_root = spec.hash_tree_root(state)
    return spec.hash_tree_root(anchor_block_header)


def add_block_to_store(spec, store, signed_block, test_steps=None):
    if test_steps is None:
        test_steps = []

    pre_state = store.block_states[signed_block.message.parent_root]
    block_time = pre_state.genesis_time + signed_block.message.slot * spec.SECONDS_PER_SLOT

    if store.time < block_time:
        spec.on_tick(store, block_time)
        test_steps.append({'tick': int(block_time)})

    spec.on_block(store, signed_block)
    test_steps.append({'block': get_block_file_name(signed_block)})


def add_attestation_to_store(spec, store, attestation, test_steps=None):
    if test_steps is None:
        test_steps = []

    parent_block = store.blocks[attestation.data.beacon_block_root]
    pre_state = store.block_states[spec.hash_tree_root(parent_block)]
    block_time = pre_state.genesis_time + parent_block.slot * spec.SECONDS_PER_SLOT
    next_epoch_time = block_time + spec.SLOTS_PER_EPOCH * spec.SECONDS_PER_SLOT

    if store.time < next_epoch_time:
        spec.on_tick(store, next_epoch_time)
        test_steps.append({'tick': int(next_epoch_time)})

    spec.on_attestation(store, attestation)
    test_steps.append({'attestation': get_attestation_file_name(attestation)})


def get_genesis_forkchoice_store(spec, genesis_state):
    store, _ = get_genesis_forkchoice_store_and_block(spec, genesis_state)
    return store


def get_genesis_forkchoice_store_and_block(spec, genesis_state):
    assert genesis_state.slot == spec.GENESIS_SLOT
    # The genesis block must be a Phase 0 `BeaconBlock`
    genesis_block = phase0_spec.BeaconBlock(state_root=genesis_state.hash_tree_root())
    return spec.get_forkchoice_store(genesis_state, genesis_block), genesis_block


def get_block_file_name(block):
    return f"block_{encode_hex(block.hash_tree_root())}"


def get_attestation_file_name(attestation):
    return f"attestation_{encode_hex(attestation.hash_tree_root())}"
