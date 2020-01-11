from eth2spec.test.helpers.phase1.shard_block import sign_shard_block


def configure_shard_state(spec, beacon_state, shard=0):
    beacon_state.slot = spec.Slot(spec.SHARD_GENESIS_EPOCH * spec.SLOTS_PER_EPOCH)
    shard_state = spec.get_genesis_shard_state(spec.Shard(shard))
    shard_state.slot = spec.ShardSlot(spec.SHARD_GENESIS_EPOCH * spec.SHARD_SLOTS_PER_EPOCH)
    return beacon_state, shard_state


def shard_state_transition_and_sign_block(spec, beacon_state, shard_state, block):
    """
    Shard state transition via the provided ``block``
    then package the block with the state root and signature.
    """
    spec.shard_state_transition(beacon_state, shard_state, block)
    block.state_root = shard_state.hash_tree_root()
    sign_shard_block(spec, beacon_state, shard_state, block)
