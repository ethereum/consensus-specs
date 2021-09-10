from random import Random

from eth2spec.test.helpers.keys import privkeys, pubkeys
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.sync_committee import (
    compute_committee_indices,
    compute_aggregate_sync_committee_signature,
)
from eth2spec.test.helpers.proposer_slashings import get_valid_proposer_slashing
from eth2spec.test.helpers.attester_slashings import get_valid_attester_slashing_by_indices
from eth2spec.test.helpers.attestations import get_valid_attestation
from eth2spec.test.helpers.deposits import build_deposit, deposit_from_context
from eth2spec.test.helpers.voluntary_exits import prepare_signed_exits


def run_slash_and_exit(spec, state, slash_index, exit_index, valid=True):
    """
    Helper function to run a test that slashes and exits two validators
    """
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)

    proposer_slashing = get_valid_proposer_slashing(
        spec, state, slashed_index=slash_index, signed_1=True, signed_2=True)
    signed_exit = prepare_signed_exits(spec, state, [exit_index])[0]

    block.body.proposer_slashings.append(proposer_slashing)
    block.body.voluntary_exits.append(signed_exit)

    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=(not valid))

    yield 'blocks', [signed_block]

    if not valid:
        yield 'post', None
        return

    yield 'post', state


def get_random_proposer_slashings(spec, state, rng):
    num_slashings = rng.randrange(1, spec.MAX_PROPOSER_SLASHINGS)
    active_indices = spec.get_active_validator_indices(state, spec.get_current_epoch(state)).copy()
    indices = [
        index for index in active_indices
        if not state.validators[index].slashed
    ]
    slashings = [
        get_valid_proposer_slashing(
            spec, state,
            slashed_index=indices.pop(rng.randrange(len(indices))), signed_1=True, signed_2=True,
        )
        for _ in range(num_slashings)
    ]
    return slashings


def get_random_attester_slashings(spec, state, rng, slashed_indices=[]):
    """
    Caller can supply ``slashed_indices`` if they are aware of other indices
    that will be slashed by other operations in the same block as the one that
    contains the output of this function.
    """
    # ensure at least one attester slashing, the max count
    # is small so not much room for random inclusion
    num_slashings = rng.randrange(1, spec.MAX_ATTESTER_SLASHINGS)
    active_indices = spec.get_active_validator_indices(state, spec.get_current_epoch(state)).copy()
    indices = [
        index for index in active_indices
        if (
            not state.validators[index].slashed
            and index not in slashed_indices
        )
    ]
    sample_upper_bound = 4
    max_slashed_count = num_slashings * sample_upper_bound - 1
    if len(indices) < max_slashed_count:
        return []

    slot_range = list(range(state.slot - spec.SLOTS_PER_HISTORICAL_ROOT + 1, state.slot))
    slashings = [
        get_valid_attester_slashing_by_indices(
            spec, state,
            sorted([indices.pop(rng.randrange(len(indices))) for _ in range(rng.randrange(1, sample_upper_bound))]),
            slot=slot_range.pop(rng.randrange(len(slot_range))),
            signed_1=True, signed_2=True,
        )
        for _ in range(num_slashings)
    ]
    return slashings


def get_random_attestations(spec, state, rng):
    num_attestations = rng.randrange(1, spec.MAX_ATTESTATIONS)

    attestations = [
        get_valid_attestation(
            spec, state,
            slot=rng.randrange(state.slot - spec.SLOTS_PER_EPOCH + 1, state.slot),
            signed=True,
        )
        for _ in range(num_attestations)
    ]
    return attestations


def get_random_deposits(spec, state, rng, num_deposits=None):
    if not num_deposits:
        num_deposits = rng.randrange(1, spec.MAX_DEPOSITS)

    if num_deposits == 0:
        return [], b"\x00" * 32

    deposit_data_leaves = [spec.DepositData() for _ in range(len(state.validators))]
    deposits = []

    # First build deposit data leaves
    for i in range(num_deposits):
        index = len(state.validators) + i
        _, root, deposit_data_leaves = build_deposit(
            spec,
            deposit_data_leaves,
            pubkeys[index],
            privkeys[index],
            spec.MAX_EFFECTIVE_BALANCE,
            withdrawal_credentials=b'\x00' * 32,
            signed=True,
        )

    # Then for that context, build deposits/proofs
    for i in range(num_deposits):
        index = len(state.validators) + i
        deposit, _, _ = deposit_from_context(spec, deposit_data_leaves, index)
        deposits.append(deposit)

    return deposits, root


def prepare_state_and_get_random_deposits(spec, state, rng, num_deposits=None):
    deposits, root = get_random_deposits(spec, state, rng, num_deposits=num_deposits)
    state.eth1_data.deposit_root = root
    state.eth1_data.deposit_count += len(deposits)
    return deposits


def _eligible_for_exit(spec, state, index):
    validator = state.validators[index]

    not_slashed = not validator.slashed

    current_epoch = spec.get_current_epoch(state)
    activation_epoch = validator.activation_epoch
    active_for_long_enough = current_epoch >= activation_epoch + spec.config.SHARD_COMMITTEE_PERIOD

    not_exited = validator.exit_epoch == spec.FAR_FUTURE_EPOCH

    return not_slashed and active_for_long_enough and not_exited


def get_random_voluntary_exits(spec, state, to_be_slashed_indices, rng):
    num_exits = rng.randrange(1, spec.MAX_VOLUNTARY_EXITS)
    active_indices = set(spec.get_active_validator_indices(state, spec.get_current_epoch(state)).copy())
    indices = set(
        index for index in active_indices
        if _eligible_for_exit(spec, state, index)
    )
    eligible_indices = indices - to_be_slashed_indices
    indices_count = min(num_exits, len(eligible_indices))
    exit_indices = [eligible_indices.pop() for _ in range(indices_count)]
    return prepare_signed_exits(spec, state, exit_indices)


def get_random_sync_aggregate(spec, state, slot, block_root=None, fraction_participated=1.0, rng=Random(2099)):
    committee_indices = compute_committee_indices(spec, state, state.current_sync_committee)
    participant_count = int(len(committee_indices) * fraction_participated)
    participant_indices = rng.sample(range(len(committee_indices)), participant_count)
    participants = [
        committee_indices[index]
        for index in participant_indices
    ]
    signature = compute_aggregate_sync_committee_signature(
        spec,
        state,
        slot,
        participants,
        block_root=block_root,
    )
    return spec.SyncAggregate(
        sync_committee_bits=[index in participant_indices for index in range(len(committee_indices))],
        sync_committee_signature=signature,
    )


def build_random_block_from_state_for_next_slot(spec, state, rng=Random(2188), deposits=None):
    block = build_empty_block_for_next_slot(spec, state)
    proposer_slashings = get_random_proposer_slashings(spec, state, rng)
    block.body.proposer_slashings = proposer_slashings
    slashed_indices = [
        slashing.signed_header_1.message.proposer_index
        for slashing in proposer_slashings
    ]
    block.body.attester_slashings = get_random_attester_slashings(spec, state, rng, slashed_indices)
    block.body.attestations = get_random_attestations(spec, state, rng)
    if deposits:
        block.body.deposits = deposits

    # cannot include to be slashed indices as exits
    slashed_indices = set([
        slashing.signed_header_1.message.proposer_index
        for slashing in block.body.proposer_slashings
    ])
    for attester_slashing in block.body.attester_slashings:
        slashed_indices = slashed_indices.union(attester_slashing.attestation_1.attesting_indices)
        slashed_indices = slashed_indices.union(attester_slashing.attestation_2.attesting_indices)
    block.body.voluntary_exits = get_random_voluntary_exits(spec, state, slashed_indices, rng)

    return block


def run_test_full_random_operations(spec, state, rng=Random(2080)):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    # prepare state for deposits before building block
    deposits = prepare_state_and_get_random_deposits(spec, state, rng)
    block = build_random_block_from_state_for_next_slot(spec, state, rng, deposits=deposits)

    yield 'pre', state

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state
