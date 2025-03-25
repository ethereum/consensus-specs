from collections import Counter

from eth2spec.test.context import (
    expect_assertion_error,
)
from eth2spec.test.helpers.keys import privkeys
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.block_processing import run_block_processing_to
from eth2spec.utils import bls


def compute_sync_committee_signature(spec, state, slot, privkey, block_root=None, domain_type=None):
    if not domain_type:
        domain_type = spec.DOMAIN_SYNC_COMMITTEE
    domain = spec.get_domain(state, domain_type, spec.compute_epoch_at_slot(slot))
    if block_root is None:
        if slot == state.slot:
            block_root = build_empty_block_for_next_slot(spec, state).parent_root
        else:
            block_root = spec.get_block_root_at_slot(state, slot)
    signing_root = spec.compute_signing_root(block_root, domain)
    return bls.Sign(privkey, signing_root)


def compute_aggregate_sync_committee_signature(
    spec, state, slot, participants, block_root=None, domain_type=None
):
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
                domain_type=domain_type,
            )
        )
    return bls.Aggregate(signatures)


def compute_sync_committee_inclusion_reward(spec, state):
    total_active_increments = (
        spec.get_total_active_balance(state) // spec.EFFECTIVE_BALANCE_INCREMENT
    )
    total_base_rewards = spec.get_base_reward_per_increment(state) * total_active_increments
    max_participant_rewards = (
        total_base_rewards
        * spec.SYNC_REWARD_WEIGHT
        // spec.WEIGHT_DENOMINATOR
        // spec.SLOTS_PER_EPOCH
    )
    return max_participant_rewards // spec.SYNC_COMMITTEE_SIZE


def compute_sync_committee_participant_reward_and_penalty(
    spec, state, participant_index, committee_indices, committee_bits
):
    inclusion_reward = compute_sync_committee_inclusion_reward(spec, state)

    included_indices = [index for index, bit in zip(committee_indices, committee_bits) if bit]
    not_included_indices = [
        index for index, bit in zip(committee_indices, committee_bits) if not bit
    ]
    included_multiplicities = Counter(included_indices)
    not_included_multiplicities = Counter(not_included_indices)
    return (
        spec.Gwei(inclusion_reward * included_multiplicities[participant_index]),
        spec.Gwei(inclusion_reward * not_included_multiplicities[participant_index]),
    )


def compute_sync_committee_proposer_reward(spec, state, committee_indices, committee_bits):
    proposer_reward_denominator = spec.WEIGHT_DENOMINATOR - spec.PROPOSER_WEIGHT
    inclusion_reward = compute_sync_committee_inclusion_reward(spec, state)
    participant_number = committee_bits.count(True)
    participant_reward = inclusion_reward * spec.PROPOSER_WEIGHT // proposer_reward_denominator
    return spec.Gwei(participant_reward * participant_number)


def compute_committee_indices(state, committee=None):
    """
    Given a ``committee``, calculate and return the related indices
    """
    if committee is None:
        committee = state.current_sync_committee
    all_pubkeys = [v.pubkey for v in state.validators]
    return [all_pubkeys.index(pubkey) for pubkey in committee.pubkeys]


def validate_sync_committee_rewards(
    spec, pre_state, post_state, committee_indices, committee_bits, proposer_index
):
    for index in range(len(post_state.validators)):
        reward = 0
        penalty = 0
        if index in committee_indices:
            _reward, _penalty = compute_sync_committee_participant_reward_and_penalty(
                spec,
                pre_state,
                index,
                committee_indices,
                committee_bits,
            )
            reward += _reward
            penalty += _penalty

        if proposer_index == index:
            reward += compute_sync_committee_proposer_reward(
                spec,
                pre_state,
                committee_indices,
                committee_bits,
            )

        balance = pre_state.balances[index] + reward
        assert post_state.balances[index] == (0 if balance < penalty else balance - penalty)


def run_sync_committee_processing(
    spec, state, block, expect_exception=False, skip_reward_validation=False
):
    """
    Processes everything up to the sync committee work, then runs the sync committee work in isolation, and
    produces a pre-state and post-state (None if exception) specifically for sync-committee processing changes.
    """
    pre_state = state.copy()
    # process up to the sync committee work
    call = run_block_processing_to(spec, state, block, "process_sync_aggregate")
    yield "pre", state
    yield "sync_aggregate", block.body.sync_aggregate
    if expect_exception:
        expect_assertion_error(lambda: call(state, block))
        yield "post", None
    else:
        call(state, block)
        yield "post", state
    if expect_exception:
        assert pre_state.balances == state.balances
    else:
        committee_indices = compute_committee_indices(state, state.current_sync_committee)
        committee_bits = block.body.sync_aggregate.sync_committee_bits
        if not skip_reward_validation:
            validate_sync_committee_rewards(
                spec,
                pre_state,
                state,
                committee_indices,
                committee_bits,
                block.proposer_index,
            )


def _build_block_for_next_slot_with_sync_participation(
    spec, state, committee_indices, committee_bits
):
    block = build_empty_block_for_next_slot(spec, state)
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=committee_bits,
        sync_committee_signature=compute_aggregate_sync_committee_signature(
            spec,
            state,
            block.slot - 1,
            [index for index, bit in zip(committee_indices, committee_bits) if bit],
            block_root=block.parent_root,
        ),
    )
    return block


def run_successful_sync_committee_test(
    spec, state, committee_indices, committee_bits, skip_reward_validation=False
):
    block = _build_block_for_next_slot_with_sync_participation(
        spec, state, committee_indices, committee_bits
    )
    yield from run_sync_committee_processing(
        spec, state, block, skip_reward_validation=skip_reward_validation
    )
