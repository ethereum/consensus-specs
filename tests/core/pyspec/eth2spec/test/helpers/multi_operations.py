from random import Random

from eth2spec.test.helpers.keys import privkeys, pubkeys
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
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
    state.slot += spec.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

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
    num_slashings = rng.randrange(spec.MAX_PROPOSER_SLASHINGS)
    indices = spec.get_active_validator_indices(state, spec.get_current_epoch(state)).copy()
    slashings = [
        get_valid_proposer_slashing(
            spec, state,
            slashed_index=indices.pop(rng.randrange(len(indices))), signed_1=True, signed_2=True,
        )
        for _ in range(num_slashings)
    ]
    return slashings


def get_random_attester_slashings(spec, state, rng):
    num_slashings = rng.randrange(spec.MAX_ATTESTER_SLASHINGS)
    indices = spec.get_active_validator_indices(state, spec.get_current_epoch(state)).copy()
    slot_range = list(range(state.slot - spec.SLOTS_PER_HISTORICAL_ROOT + 1, state.slot))
    slashings = [
        get_valid_attester_slashing_by_indices(
            spec, state,
            sorted([indices.pop(rng.randrange(len(indices))) for _ in range(rng.randrange(1, 4))]),
            slot=slot_range.pop(rng.randrange(len(slot_range))),
            signed_1=True, signed_2=True,
        )
        for _ in range(num_slashings)
    ]
    return slashings


def get_random_attestations(spec, state, rng):
    num_attestations = rng.randrange(spec.MAX_ATTESTATIONS)

    attestations = [
        get_valid_attestation(
            spec, state,
            slot=rng.randrange(state.slot - spec.SLOTS_PER_EPOCH + 1, state.slot),
            signed=True,
        )
        for _ in range(num_attestations)
    ]
    return attestations


def prepare_state_and_get_random_deposits(spec, state, rng):
    num_deposits = rng.randrange(spec.MAX_DEPOSITS)

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

    state.eth1_data.deposit_root = root
    state.eth1_data.deposit_count += num_deposits

    # Then for that context, build deposits/proofs
    for i in range(num_deposits):
        index = len(state.validators) + i
        deposit, _, _ = deposit_from_context(spec, deposit_data_leaves, index)
        deposits.append(deposit)

    return deposits


def get_random_voluntary_exits(spec, state, to_be_slashed_indices, rng):
    num_exits = rng.randrange(spec.MAX_VOLUNTARY_EXITS)
    indices = set(spec.get_active_validator_indices(state, spec.get_current_epoch(state)).copy())
    eligible_indices = indices - to_be_slashed_indices
    exit_indices = [eligible_indices.pop() for _ in range(num_exits)]
    return prepare_signed_exits(spec, state, exit_indices)


def run_test_full_random_operations(spec, state, rng=Random(2080)):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    # prepare state for deposits before building block
    deposits = prepare_state_and_get_random_deposits(spec, state, rng)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.proposer_slashings = get_random_proposer_slashings(spec, state, rng)
    block.body.attester_slashings = get_random_attester_slashings(spec, state, rng)
    block.body.attestations = get_random_attestations(spec, state, rng)
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

    yield 'pre', state

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state
