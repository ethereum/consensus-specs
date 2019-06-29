import math
from eth2spec.test.context import spec_state_test, with_all_phases
from eth2spec.test.phase_0.epoch_processing.run_epoch_process_base import (
    run_epoch_processing_with
)


def run_process_just_and_fin(spec, state):
    yield from run_epoch_processing_with(spec, state, 'process_justification_and_finalization')


def get_shards_for_slot(spec, state, slot):
    epoch = spec.slot_to_epoch(slot)
    epoch_start_shard = spec.get_epoch_start_shard(state, epoch)
    committees_per_slot = spec.get_epoch_committee_count(state, epoch) // spec.SLOTS_PER_EPOCH
    shard = (epoch_start_shard + committees_per_slot * (slot % spec.SLOTS_PER_EPOCH)) % spec.SHARD_COUNT
    return [shard + i for i in range(committees_per_slot)]


def get_committee_size(spec, epoch_start_shard, shard, committee_count, indices):
    committee_index = (shard + spec.SHARD_COUNT - epoch_start_shard) % spec.SHARD_COUNT
    start = (len(indices) * committee_index) // committee_count
    end = (len(indices) * (committee_index + 1)) // committee_count
    size = end - start
    return size


def add_mock_attestations(spec, state, epoch, att_ratio, source, target):
    # we must be at the end of the epoch
    assert (state.slot + 1) % spec.SLOTS_PER_EPOCH == 0

    previous_epoch = spec.get_previous_epoch(state)
    current_epoch = spec.get_current_epoch(state)

    if current_epoch == epoch:
        attestations = state.current_epoch_attestations
    elif previous_epoch == epoch:
        attestations = state.previous_epoch_attestations
    else:
        raise Exception(f"cannot include attestations in epoch ${epoch} from epoch ${current_epoch}")

    committee_count = spec.get_epoch_committee_count(state, epoch)
    indices = spec.get_active_validator_indices(state, epoch)
    epoch_start_shard = spec.get_epoch_start_shard(state, epoch)
    epoch_start_slot = spec.get_epoch_start_slot(epoch)
    for slot in range(epoch_start_slot, epoch_start_slot + spec.SLOTS_PER_EPOCH):
        for shard in get_shards_for_slot(spec, state, slot):
            size = get_committee_size(spec, epoch_start_shard, shard, committee_count, indices)
            # Create a bitfield filled with the given count per attestation,
            #  exactly on the right-most part of the committee field.
            attesting_count = math.ceil(size * att_ratio)
            aggregation_bits = [i < attesting_count for i in range(size)]

            attestations.append(spec.PendingAttestation(
                aggregation_bits=aggregation_bits,
                data=spec.AttestationData(
                    beacon_block_root=b'\xaa' * 32,
                    source=source,
                    target=target,
                    crosslink=spec.Crosslink()
                ),
                inclusion_delay=1,
            ))


def finalize_on_234(spec, state, epoch, support):
    assert epoch > 4
    state.slot = (spec.SLOTS_PER_EPOCH * epoch) - 1  # skip ahead to just before epoch

    # 43210 -- epochs ago
    # 3210x -- justification bitfield indices
    # 11*0. -- justification bitfield contents, . = this epoch, * is being justified now
    # checkpoints for the epochs ago:
    c4 = spec.Checkpoint(epoch=epoch - 4, root=b'\xaa' * 32)
    c3 = spec.Checkpoint(epoch=epoch - 3, root=b'\xaa' * 32)
    c2 = spec.Checkpoint(epoch=epoch - 2, root=b'\xbb' * 32)
    # c1 = spec.Checkpoint(epoch=epoch - 1, root=b'\xcc' * 32)

    old_finalized = state.finalized_checkpoint
    state.previous_justified_checkpoint = c4
    state.current_justified_checkpoint = c3
    bits = state.justification_bits = spec.Bitvector[spec.JUSTIFICATION_BITS_LENGTH]()
    bits[3:4] = [1, 1]  # mock 3rd and 4th latest epochs as justified
    # mock the 2nd latest epoch as justifiable, with 4th as source
    add_mock_attestations(spec, state,
                          epoch=epoch - 2,
                          att_ratio=support,
                          source=c4,
                          target=c2)

    # process!
    yield from run_process_just_and_fin(spec, state)

    if support >= (2 / 3):
        assert state.previous_justified_checkpoint == c3  # changed to old current
        assert state.current_justified_checkpoint == c2  # changed to 2nd latest
        assert state.finalized_checkpoint == c4  # finalized old previous justified epoch
    else:
        assert state.previous_justified_checkpoint == c3  # changed to old current
        assert state.current_justified_checkpoint == c3  # still old current
        assert state.finalized_checkpoint == old_finalized  # no new finalized


def finalize_on_23(spec, state, epoch, support):
    assert epoch > 3
    state.slot = (spec.SLOTS_PER_EPOCH * epoch) - 1  # skip ahead to just before epoch

    # 43210 -- epochs ago
    # 3210x -- justification bitfield indices
    # 01*0. -- justification bitfield contents, . = this epoch, * is being justified now
    # checkpoints for the epochs ago:
    # c4 = spec.Checkpoint(epoch=epoch - 4, root=b'\xaa' * 32)
    c3 = spec.Checkpoint(epoch=epoch - 3, root=b'\xaa' * 32)
    c2 = spec.Checkpoint(epoch=epoch - 2, root=b'\xbb' * 32)
    # c1 = spec.Checkpoint(epoch=epoch - 1, root=b'\xcc' * 32)

    old_finalized = state.finalized_checkpoint
    state.previous_justified_checkpoint = c3
    state.current_justified_checkpoint = c3
    bits = state.justification_bits = spec.Bitvector[spec.JUSTIFICATION_BITS_LENGTH]()
    bits[2] = 1  # mock 3rd latest epoch as justified
    # mock the 2nd latest epoch as justifiable, with 3rd as source
    add_mock_attestations(spec, state,
                          epoch=epoch - 2,
                          att_ratio=support,
                          source=c3,
                          target=c2)

    # process!
    yield from run_process_just_and_fin(spec, state)

    if support >= (2 / 3):
        assert state.previous_justified_checkpoint == c3  # changed to old current
        assert state.current_justified_checkpoint == c2  # changed to 2nd latest
        assert state.finalized_checkpoint == c3  # finalized old previous justified epoch
    else:
        assert state.previous_justified_checkpoint == c3  # changed to old current
        assert state.current_justified_checkpoint == c3  # still old current
        assert state.finalized_checkpoint == old_finalized  # no new finalized


def finalize_on_123(spec, state, epoch, support):
    assert epoch > 3
    state.slot = (spec.SLOTS_PER_EPOCH * epoch) - 1  # skip ahead to just before epoch

    # 43210 -- epochs ago
    # 3210x -- justification bitfield indices
    # 011*. -- justification bitfield contents, . = this epoch, * is being justified now
    # checkpoints for the epochs ago:
    # c4 = spec.Checkpoint(epoch=epoch - 4, root=b'\xaa' * 32)
    c3 = spec.Checkpoint(epoch=epoch - 3, root=b'\xaa' * 32)
    c2 = spec.Checkpoint(epoch=epoch - 2, root=b'\xbb' * 32)
    c1 = spec.Checkpoint(epoch=epoch - 1, root=b'\xcc' * 32)

    old_finalized = state.finalized_checkpoint
    state.previous_justified_checkpoint = c3
    state.current_justified_checkpoint = c2
    bits = state.justification_bits = spec.Bitvector[spec.JUSTIFICATION_BITS_LENGTH]()
    bits[1:2] = [1, 1]  # mock 2rd and 3th latest epochs as justified
    # mock the 1st latest epoch as justifiable, with 3rd as source
    add_mock_attestations(spec, state,
                          epoch=epoch - 1,
                          att_ratio=support,
                          source=c3,
                          target=c1)

    # process!
    yield from run_process_just_and_fin(spec, state)

    if support >= (2 / 3):
        assert state.previous_justified_checkpoint == c2  # changed to old current
        assert state.current_justified_checkpoint == c1  # changed to 1st latest
        assert state.finalized_checkpoint == c2  # finalized old current
    else:
        assert state.previous_justified_checkpoint == c2  # changed to old current
        assert state.current_justified_checkpoint == c2  # still old current
        assert state.finalized_checkpoint == old_finalized  # no new finalized


def finalize_on_12(spec, state, epoch, support):
    assert epoch > 2
    state.slot = (spec.SLOTS_PER_EPOCH * epoch) - 1  # skip ahead to just before epoch

    # 43210 -- epochs ago
    # 3210  -- justification bitfield indices
    # 001*. -- justification bitfield contents, . = this epoch, * is being justified now
    # checkpoints for the epochs ago:
    # c4 = spec.Checkpoint(epoch=epoch - 4, root=b'\xaa' * 32)
    # c3 = spec.Checkpoint(epoch=epoch - 3, root=b'\xaa' * 32)
    c2 = spec.Checkpoint(epoch=epoch - 2, root=b'\xbb' * 32)
    c1 = spec.Checkpoint(epoch=epoch - 1, root=b'\xcc' * 32)
    state.block_roots[spec.get_epoch_start_slot(c2.epoch) % spec.SLOTS_PER_HISTORICAL_ROOT] = c2.root
    state.block_roots[spec.get_epoch_start_slot(c1.epoch) % spec.SLOTS_PER_HISTORICAL_ROOT] = c1.root

    old_finalized = state.finalized_checkpoint
    state.previous_justified_checkpoint = c2
    state.current_justified_checkpoint = c2
    state.justification_bits = spec.Bitvector[spec.JUSTIFICATION_BITS_LENGTH]()
    state.justification_bits[0] = 1  # mock latest epoch as justified
    # mock the 1st latest epoch as justifiable, with 2nd as source
    add_mock_attestations(spec, state,
                          epoch=epoch - 1,
                          att_ratio=support,
                          source=c2,
                          target=c1)

    # process!
    yield from run_process_just_and_fin(spec, state)

    if support >= (2 / 3):
        assert state.previous_justified_checkpoint == c2  # changed to old current
        assert state.current_justified_checkpoint == c1  # changed to 1st latest
        assert state.finalized_checkpoint == c2  # finalized previous justified epoch
    else:
        assert state.previous_justified_checkpoint == c2  # changed to old current
        assert state.current_justified_checkpoint == c2  # still old current
        assert state.finalized_checkpoint == old_finalized  # no new finalized


@with_all_phases
@spec_state_test
def test_234_ok_support(spec, state):
    yield from finalize_on_234(spec, state, 5, 1.0)


@with_all_phases
@spec_state_test
def test_234_poor_support(spec, state):
    yield from finalize_on_234(spec, state, 5, 0.6)


@with_all_phases
@spec_state_test
def test_23_ok_support(spec, state):
    yield from finalize_on_23(spec, state, 4, 1.0)


@with_all_phases
@spec_state_test
def test_23_poor_support(spec, state):
    yield from finalize_on_23(spec, state, 4, 0.6)


@with_all_phases
@spec_state_test
def test_123_ok_support(spec, state):
    yield from finalize_on_123(spec, state, 4, 1.0)


@with_all_phases
@spec_state_test
def test_123_poor_support(spec, state):
    yield from finalize_on_123(spec, state, 4, 0.6)


@with_all_phases
@spec_state_test
def test_12_ok_support(spec, state):
    yield from finalize_on_12(spec, state, 3, 1.0)


@with_all_phases
@spec_state_test
def test_12_poor_support(spec, state):
    yield from finalize_on_12(spec, state, 3, 0.6)


# TODO: bring ratios closer to 2/3 for edge case testing.
