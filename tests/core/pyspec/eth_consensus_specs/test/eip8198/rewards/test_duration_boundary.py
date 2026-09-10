from eth_consensus_specs.test.context import spec_configured_state_test, with_phases
from eth_consensus_specs.test.helpers.constants import EIP8198
from eth_consensus_specs.test.helpers.eip8198.schedule import slot_duration_schedule_entry
from eth_consensus_specs.test.helpers.rewards import run_deltas
from eth_consensus_specs.test.helpers.state import next_epoch

FORK_CONFIG = {
    "EIP8198_FORK_EPOCH": 2,
    "SLOT_DURATION_SCHEDULE": (
        slot_duration_schedule_entry(0, 6000),
        slot_duration_schedule_entry(2, 5000),
    ),
}


def run_duration_boundary_deltas(spec, state, epoch):
    while spec.get_current_epoch(state) < epoch:
        next_epoch(spec, state)
    for index in range(len(state.validators)):
        state.inactivity_scores[index] = 4
        if index % 2 == 0:
            state.previous_epoch_participation[index] = spec.ParticipationFlags(0b111)
    yield from run_deltas(spec, state)


@with_phases([EIP8198])
@spec_configured_state_test(FORK_CONFIG, activate_at_genesis=True)
def test_rewards_at_duration_boundary(spec, state):
    yield from run_duration_boundary_deltas(spec, state, 2)


@with_phases([EIP8198])
@spec_configured_state_test(FORK_CONFIG, activate_at_genesis=True)
def test_rewards_after_duration_boundary(spec, state):
    yield from run_duration_boundary_deltas(spec, state, 3)
