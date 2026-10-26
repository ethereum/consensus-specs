from eth_consensus_specs.test.context import (
    always_bls,
    spec_configured_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.block_processing import run_block_processing_to
from eth_consensus_specs.test.helpers.constants import HEZE
from eth_consensus_specs.test.helpers.heze.slot_duration import (
    expected_base_reward_per_increment,
)
from eth_consensus_specs.test.helpers.sync_committee import (
    compute_aggregate_sync_committee_signature,
    compute_committee_indices,
)


@with_phases([HEZE])
@spec_configured_state_test(
    {"HEZE_FORK_EPOCH": 2, "SLOT_DURATION_MS_HEZE": 10000}, activate_at_genesis=True
)
@always_bls
def test_sync_committee_rewards_use_current_epoch_at_heze_fork(spec, state):
    fork_slot = spec.compute_start_slot_at_epoch(spec.config.HEZE_FORK_EPOCH)

    spec.process_slots(state, fork_slot - 1)

    committee_indices = compute_committee_indices(state)
    bits = [index % 2 == 0 for index in range(spec.SYNC_COMMITTEE_SIZE)]
    block = build_empty_block_for_next_slot(spec, state)
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=spec.SyncCommitteeBits(data=bits),
        sync_committee_signature=compute_aggregate_sync_committee_signature(
            spec,
            state,
            block.slot - 1,
            [index for index, bit in zip(committee_indices, bits, strict=True) if bit],
            block_root=block.parent_root,
        ),
    )

    process = run_block_processing_to(spec, state, block, "process_sync_aggregate")

    balances = list(state.balances)
    total_balance = sum(int(validator.effective_balance) for validator in state.validators)
    base_reward_per_increment = expected_base_reward_per_increment(
        spec, state, spec.config.SLOT_DURATION_MS_HEZE
    )
    total_active_increments = total_balance // spec.EFFECTIVE_BALANCE_INCREMENT
    total_base_rewards = base_reward_per_increment * total_active_increments
    participant_reward = (
        total_base_rewards
        * spec.SYNC_REWARD_WEIGHT
        // spec.WEIGHT_DENOMINATOR
        // int(spec.SLOTS_PER_EPOCH)
        // spec.SYNC_COMMITTEE_SIZE
    )
    proposer_reward = (
        participant_reward
        * spec.PROPOSER_WEIGHT
        // (spec.WEIGHT_DENOMINATOR - spec.PROPOSER_WEIGHT)
    )
    for index, bit in zip(committee_indices, bits, strict=True):
        balances[index] = (
            balances[index] + participant_reward if bit else balances[index] - participant_reward
        )
    balances[block.proposer_index] += sum(bits) * proposer_reward

    yield "pre", state
    yield "sync_aggregate", block.body.sync_aggregate
    process(state, block)
    yield "post", state
    assert list(state.balances) == balances
