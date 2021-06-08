import random
from collections import defaultdict
from eth2spec.utils.ssz.ssz_typing import Bitvector
from eth2spec.test.helpers.block import build_empty_block
from eth2spec.test.helpers.keys import pubkey_to_privkey
from eth2spec.test.helpers.state import transition_to
from eth2spec.test.helpers.sync_committee import compute_sync_committee_signature
from eth2spec.utils.bls import only_with_bls
from eth2spec.test.context import (
    with_altair_and_later,
    with_presets,
    with_state,
)
from eth2spec.test.helpers.constants import (
    MINIMAL,
)

rng = random.Random(1337)


def ensure_assignments_in_sync_committee(
    spec, state, epoch, sync_committee, active_pubkeys
):
    assert len(sync_committee.pubkeys) >= 3
    some_pubkeys = rng.sample(sync_committee.pubkeys, 3)
    for pubkey in some_pubkeys:
        validator_index = active_pubkeys.index(pubkey)
        assert spec.is_assigned_to_sync_committee(state, epoch, validator_index)


@with_altair_and_later
@with_state
def test_is_assigned_to_sync_committee(phases, spec, state):
    epoch = spec.get_current_epoch(state)
    validator_indices = spec.get_active_validator_indices(state, epoch)
    validator_count = len(validator_indices)

    query_epoch = epoch + 1
    next_query_epoch = query_epoch + spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD
    active_pubkeys = [state.validators[index].pubkey for index in validator_indices]

    ensure_assignments_in_sync_committee(
        spec, state, query_epoch, state.current_sync_committee, active_pubkeys
    )
    ensure_assignments_in_sync_committee(
        spec, state, next_query_epoch, state.next_sync_committee, active_pubkeys
    )

    sync_committee_pubkeys = set(
        list(state.current_sync_committee.pubkeys)
        + list(state.next_sync_committee.pubkeys)
    )
    disqualified_pubkeys = set(
        filter(lambda key: key not in sync_committee_pubkeys, active_pubkeys)
    )
    # NOTE: only check `disqualified_pubkeys` if SYNC_COMMITEE_SIZE < validator count
    if disqualified_pubkeys:
        sample_size = 3
        assert validator_count >= sample_size
        some_pubkeys = rng.sample(disqualified_pubkeys, sample_size)
        for pubkey in some_pubkeys:
            validator_index = active_pubkeys.index(pubkey)
            is_current = spec.is_assigned_to_sync_committee(
                state, query_epoch, validator_index
            )
            is_next = spec.is_assigned_to_sync_committee(
                state, next_query_epoch, validator_index
            )
            is_current_or_next = is_current or is_next
            assert not is_current_or_next


def _get_sync_committee_signature(
    spec,
    state,
    target_slot,
    target_block_root,
    subcommittee_index,
    index_in_subcommittee,
):
    subcommittee_size = spec.SYNC_COMMITTEE_SIZE // spec.SYNC_COMMITTEE_SUBNET_COUNT
    sync_committee_index = (
        subcommittee_index * subcommittee_size + index_in_subcommittee
    )
    pubkey = state.current_sync_committee.pubkeys[sync_committee_index]
    privkey = pubkey_to_privkey[pubkey]

    return compute_sync_committee_signature(
        spec, state, target_slot, privkey, block_root=target_block_root
    )


@only_with_bls()
@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_state
def test_process_sync_committee_contributions(phases, spec, state):
    # skip over slots at genesis
    transition_to(spec, state, state.slot + 3)

    # build a block and attempt to assemble a sync aggregate
    # from some sync committee contributions
    block = build_empty_block(spec, state)
    previous_slot = state.slot - 1
    target_block_root = spec.get_block_root_at_slot(state, previous_slot)
    aggregation_bits = Bitvector[
        spec.SYNC_COMMITTEE_SIZE // spec.SYNC_COMMITTEE_SUBNET_COUNT
    ]()
    aggregation_index = 0
    aggregation_bits[aggregation_index] = True

    contributions = [
        spec.SyncCommitteeContribution(
            slot=block.slot,
            beacon_block_root=target_block_root,
            subcommittee_index=i,
            aggregation_bits=aggregation_bits,
            signature=_get_sync_committee_signature(
                spec, state, previous_slot, target_block_root, i, aggregation_index
            ),
        )
        for i in range(spec.SYNC_COMMITTEE_SUBNET_COUNT)
    ]

    # ensure the block has an empty sync aggregate...
    empty_sync_aggregate = spec.SyncAggregate()
    empty_sync_aggregate.sync_committee_signature = spec.G2_POINT_AT_INFINITY
    assert block.body.sync_aggregate == empty_sync_aggregate
    spec.process_sync_committee_contributions(block, set(contributions))

    # and that after processing, it is no longer empty
    assert len(block.body.sync_aggregate.sync_committee_bits) != 0
    assert (
        block.body.sync_aggregate.sync_committee_signature != spec.G2_POINT_AT_INFINITY
    )
    # moreover, ensure the sync aggregate is valid if the block is accepted
    spec.process_block(state, block)


def _validator_index_for_pubkey(state, pubkey):
    return list(map(lambda v: v.pubkey, state.validators)).index(pubkey)


def _subnet_for_sync_committee_index(spec, i):
    return i // (spec.SYNC_COMMITTEE_SIZE // spec.SYNC_COMMITTEE_SUBNET_COUNT)


def _get_expected_subnets_by_pubkey(sync_committee_members):
    # Build deduplicated set for each pubkey
    expected_subnets_by_pubkey = defaultdict(set)
    for (subnet, pubkey) in sync_committee_members:
        expected_subnets_by_pubkey[pubkey].add(subnet)
    return expected_subnets_by_pubkey


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_state
def test_compute_subnets_for_sync_committee(state, spec, phases):
    # Transition to the head of the next period
    transition_to(spec, state, spec.SLOTS_PER_EPOCH * spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD)

    next_slot_epoch = spec.compute_epoch_at_slot(state.slot + 1)
    assert (
        spec.compute_sync_committee_period(spec.get_current_epoch(state))
        == spec.compute_sync_committee_period(next_slot_epoch)
    )
    some_sync_committee_members = list(
        (
            _subnet_for_sync_committee_index(spec, i),
            pubkey,
        )
        # use current_sync_committee
        for i, pubkey in enumerate(state.current_sync_committee.pubkeys)
    )
    expected_subnets_by_pubkey = _get_expected_subnets_by_pubkey(some_sync_committee_members)

    for _, pubkey in some_sync_committee_members:
        validator_index = _validator_index_for_pubkey(state, pubkey)
        subnets = spec.compute_subnets_for_sync_committee(state, validator_index)
        expected_subnets = expected_subnets_by_pubkey[pubkey]
        assert subnets == expected_subnets


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_state
def test_compute_subnets_for_sync_committee_slot_period_boundary(state, spec, phases):
    # Transition to the end of the period
    transition_to(spec, state, spec.SLOTS_PER_EPOCH * spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD - 1)

    next_slot_epoch = spec.compute_epoch_at_slot(state.slot + 1)
    assert (
        spec.compute_sync_committee_period(spec.get_current_epoch(state))
        != spec.compute_sync_committee_period(next_slot_epoch)
    )
    some_sync_committee_members = list(
        (
            _subnet_for_sync_committee_index(spec, i),
            pubkey,
        )
        # use next_sync_committee
        for i, pubkey in enumerate(state.next_sync_committee.pubkeys)
    )
    expected_subnets_by_pubkey = _get_expected_subnets_by_pubkey(some_sync_committee_members)

    for _, pubkey in some_sync_committee_members:
        validator_index = _validator_index_for_pubkey(state, pubkey)
        subnets = spec.compute_subnets_for_sync_committee(state, validator_index)
        expected_subnets = expected_subnets_by_pubkey[pubkey]
        assert subnets == expected_subnets
