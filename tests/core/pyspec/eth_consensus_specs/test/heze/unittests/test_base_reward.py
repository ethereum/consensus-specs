from eth_consensus_specs.test.context import (
    spec_configured_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.constants import HEZE
from eth_consensus_specs.test.helpers.heze.slot_duration import (
    expected_base_reward,
    fork_epoch_cases,
    heze_spec_with_slot_duration,
    SLOT_DURATIONS_MS,
)


@with_phases([HEZE])
@spec_configured_state_test({"HEZE_FORK_EPOCH": 2}, activate_at_genesis=True)
def test_base_reward_across_fork(spec, state):
    index = spec.ValidatorIndex(0)
    for slot_duration_ms in SLOT_DURATIONS_MS:
        for fork_epoch, epoch, duration_ms in fork_epoch_cases(spec, slot_duration_ms):
            heze_spec = heze_spec_with_slot_duration(spec, slot_duration_ms, fork_epoch)
            assert heze_spec.get_base_reward(state, index, spec.Epoch(epoch)) == (
                expected_base_reward(spec, state, index, duration_ms)
            )
