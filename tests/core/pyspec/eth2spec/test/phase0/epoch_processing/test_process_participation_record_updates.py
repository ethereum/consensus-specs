from eth2spec.utils.ssz.ssz_typing import Bitvector, List

from eth2spec.test.context import spec_state_test, with_all_phases, PHASE0
from eth2spec.test.phase0.epoch_processing.run_epoch_process_base import (
    run_epoch_processing_with
)


def run_process_participation_record_updates(spec, state):
    yield from run_epoch_processing_with(spec, state, 'process_participation_record_updates')


@with_all_phases
@spec_state_test
def test_updated_participation_record(spec, state):
    if spec.fork == PHASE0:
        state.previous_epoch_attestations = [spec.PendingAttestation(proposer_index=100)]
        current_epoch_attestations = [spec.PendingAttestation(proposer_index=200)]
        state.current_epoch_attestations = current_epoch_attestations

        yield from run_process_participation_record_updates(spec, state)

        assert state.previous_epoch_attestations == current_epoch_attestations
        assert state.current_epoch_attestations == []
    else:
        # shard_transition_candidates
        state.previous_shard_transition_candidates = [
            spec.ShardTransitionCandidate(data=spec.AttestationData(slot=100))
        ]
        current_shard_transition_candidates = [spec.ShardTransitionCandidate(data=spec.AttestationData(slot=200))]
        state.current_shard_transition_candidates = current_shard_transition_candidates

        # epoch_reward_flags
        state.previous_epoch_reward_flags = [Bitvector[8](1, 0, 1, 0, 1, 0, 1, 0)]
        current_epoch_reward_flags = [Bitvector[8](1, 1, 1, 1, 1, 1, 0, 0)]
        state.current_epoch_reward_flags = current_epoch_reward_flags

        yield from run_process_participation_record_updates(spec, state)

        assert state.previous_epoch_reward_flags == current_epoch_reward_flags
        assert state.current_epoch_reward_flags == List[Bitvector[8], spec.MAX_ACTIVE_VALIDATORS](
            Bitvector[8]() for _ in spec.get_active_validator_indices(state, spec.get_current_epoch(state) + 1)
        )
