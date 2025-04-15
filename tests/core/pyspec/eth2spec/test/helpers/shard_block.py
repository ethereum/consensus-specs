from eth2spec.test.helpers.block import get_state_and_beacon_parent_root_at_slot
from eth2spec.test.helpers.keys import privkeys
from eth2spec.utils import bls
from eth2spec.utils.bls import only_with_bls


@only_with_bls()
def sign_shard_block(spec, beacon_state, shard, block, proposer_index=None):
    slot = block.message.slot
    if proposer_index is None:
        proposer_index = spec.get_shard_proposer_index(beacon_state, slot, shard)

    privkey = privkeys[proposer_index]
    domain = spec.get_domain(
        beacon_state, spec.DOMAIN_SHARD_PROPOSAL, spec.compute_epoch_at_slot(slot)
    )
    signing_root = spec.compute_signing_root(block.message, domain)
    block.signature = bls.Sign(privkey, signing_root)


def build_shard_block(
    spec, beacon_state, shard, slot=None, body=None, shard_parent_state=None, signed=False
):
    if shard_parent_state is None:
        shard_parent_state = beacon_state.shard_states[shard]

    if slot is None:
        slot = shard_parent_state.slot + 1

    if body is None:
        body = get_sample_shard_block_body(spec)

    beacon_state, beacon_parent_root = get_state_and_beacon_parent_root_at_slot(
        spec, beacon_state, slot
    )
    proposer_index = spec.get_shard_proposer_index(beacon_state, slot, shard)
    block = spec.ShardBlock(
        shard_parent_root=shard_parent_state.latest_block_root,
        beacon_parent_root=beacon_parent_root,
        slot=slot,
        shard=shard,
        proposer_index=proposer_index,
        body=body,
    )
    signed_block = spec.SignedShardBlock(
        message=block,
    )

    if signed:
        sign_shard_block(spec, beacon_state, shard, signed_block, proposer_index=proposer_index)

    return signed_block


def get_shard_transitions(spec, parent_beacon_state, shard_block_dict):
    shard_transitions = [spec.ShardTransition()] * spec.MAX_SHARDS
    on_time_slot = parent_beacon_state.slot + 1
    for shard, blocks in shard_block_dict.items():
        shard_transition = spec.get_shard_transition(parent_beacon_state, shard, blocks)
        offset_slots = spec.compute_offset_slots(
            spec.get_latest_slot_for_shard(parent_beacon_state, shard),
            on_time_slot,
        )
        len_offset_slots = len(offset_slots)
        shard_transition = spec.get_shard_transition(parent_beacon_state, shard, blocks)

        if len(blocks) > 0:
            shard_block_root = blocks[-1].message.hash_tree_root()
            assert (
                shard_transition.shard_states[len_offset_slots - 1].latest_block_root
                == shard_block_root
            )
            assert shard_transition.shard_states[len_offset_slots - 1].slot == offset_slots[-1]
        shard_transitions[shard] = shard_transition

    return shard_transitions


def get_committee_index_of_shard(spec, state, slot, shard):  # Optional[CommitteeIndex]
    active_shard_count = spec.get_active_shard_count(state)
    committee_count = spec.get_committee_count_per_slot(state, spec.compute_epoch_at_slot(slot))
    start_shard = spec.get_start_shard(state, slot)
    for committee_index in range(committee_count):
        if (start_shard + committee_index) % active_shard_count == shard:
            return committee_index
    return None


def get_sample_shard_block_body(spec, is_max=False):
    size = spec.MAX_SHARD_BLOCK_SIZE if is_max else 128
    return b"\x56" * size
