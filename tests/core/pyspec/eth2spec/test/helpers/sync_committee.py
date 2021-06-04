from collections import Counter

from eth2spec.test.helpers.keys import privkeys
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.utils import bls


def compute_sync_committee_signature(spec, state, slot, privkey, block_root=None):
    domain = spec.get_domain(state, spec.DOMAIN_SYNC_COMMITTEE, spec.compute_epoch_at_slot(slot))
    if block_root is None:
        if slot == state.slot:
            block_root = build_empty_block_for_next_slot(spec, state).parent_root
        else:
            block_root = spec.get_block_root_at_slot(state, slot)
    signing_root = spec.compute_signing_root(block_root, domain)
    return bls.Sign(privkey, signing_root)


def compute_aggregate_sync_committee_signature(spec, state, slot, participants, block_root=None):
    if len(participants) == 0:
        return spec.G2_POINT_AT_INFINITY

    signatures = []
    for validator_index in participants:
        privkey = privkeys[validator_index]
        signatures.append(
            compute_sync_committee_signature(
                spec,
                state,
                slot,
                privkey,
                block_root=block_root,
            )
        )
    return bls.Aggregate(signatures)


def compute_sync_committee_inclusion_reward(spec, state):
    total_active_increments = spec.get_total_active_balance(state) // spec.EFFECTIVE_BALANCE_INCREMENT
    total_base_rewards = spec.get_base_reward_per_increment(state) * total_active_increments
    max_participant_rewards = (total_base_rewards * spec.SYNC_REWARD_WEIGHT
                               // spec.WEIGHT_DENOMINATOR // spec.SLOTS_PER_EPOCH)
    return max_participant_rewards // spec.SYNC_COMMITTEE_SIZE


def compute_sync_committee_participant_reward_and_penalty(
        spec, state, participant_index, committee_indices, committee_bits):
    inclusion_reward = compute_sync_committee_inclusion_reward(spec, state)

    included_indices = [index for index, bit in zip(committee_indices, committee_bits) if bit]
    not_included_indices = [index for index, bit in zip(committee_indices, committee_bits) if not bit]
    included_multiplicities = Counter(included_indices)
    not_included_multiplicities = Counter(not_included_indices)
    return (
        spec.Gwei(inclusion_reward * included_multiplicities[participant_index]),
        spec.Gwei(inclusion_reward * not_included_multiplicities[participant_index])
    )


def compute_sync_committee_proposer_reward(spec, state, committee_indices, committee_bits):
    proposer_reward_denominator = spec.WEIGHT_DENOMINATOR - spec.PROPOSER_WEIGHT
    inclusion_reward = compute_sync_committee_inclusion_reward(spec, state)
    participant_number = committee_bits.count(True)
    participant_reward = inclusion_reward * spec.PROPOSER_WEIGHT // proposer_reward_denominator
    return spec.Gwei(participant_reward * participant_number)


def compute_committee_indices(spec, state, committee):
    """
    Given a ``committee``, calculate and return the related indices
    """
    all_pubkeys = [v.pubkey for v in state.validators]
    committee_indices = [all_pubkeys.index(pubkey) for pubkey in committee.pubkeys]
    return committee_indices
