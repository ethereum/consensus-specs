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
    return size,


def add_mock_attestations(spec, state, epoch, att_count, att_ratio):
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
    total = 0
    for i in range(spec.SLOTS_PER_EPOCH):
        for shard in get_shards_for_slot(spec, state, state.slot + i):
            size = get_committee_size(spec, epoch_start_shard, shard, committee_count, indices)
            # Create a bitfield filled with the given count per attestation,
            #  exactly on the right-most part of the committee field.
            attesting_count = math.ceil(size * att_ratio)
            aggregation_bitfield = ((1 << attesting_count) - 1).to_bytes(length=((size + 7) // 8), byteorder='big')

            attestations.append(spec.PendingAttestation(
                aggregation_bitfield=aggregation_bitfield,
                data=spec.AttestationData(
                    beacon_block_root=b'\xaa' * 32,
                    source_epoch=0,
                    source_root=b'\xbb' * 32,
                    target_root=b'\xbb' * 32,
                    crosslink=spec.Crosslink()
                ),
                inclusion_delay=1,
            ))
            total += 1
            if total >= att_count:
                return

    raise Exception(f"could not fill state with {att_count} attestations for epoch {epoch}")


@with_all_phases
@spec_state_test
def test_rule_1(spec, state):
    # previous_epoch = spec.get_previous_epoch(state)
    # current_epoch = spec.get_current_epoch(state)

    # TODO
    # add_mock_attestations(spec, state, ...)
    # get indices attesting e.g. current_epoch_attestations
    # set their balances
    # yield from run_process_just_and_fin(spec, state)
    # check finalization
    pass
