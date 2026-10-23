from math import isqrt

from eth_consensus_specs.test.context import get_copy_of_spec, spec_with_config_overrides

SLOT_DURATIONS_MS = [1000, 2000, 4000, 5000, 6000, 8000, 9000, 10000, 11000, 12000, 16000]
FORK_EPOCH = 2


def heze_spec_with_slot_duration(spec, slot_duration_ms, fork_epoch=FORK_EPOCH):
    heze_spec, _ = spec_with_config_overrides(
        get_copy_of_spec(spec),
        {"HEZE_FORK_EPOCH": fork_epoch, "SLOT_DURATION_MS_HEZE": slot_duration_ms},
    )
    return heze_spec


def expected_base_reward_per_increment(spec, state, slot_duration_ms):
    total_active_balance = sum(
        int(state.validators[i].effective_balance)
        for i in range(len(state.validators))
        if spec.is_active_validator(state.validators[i], spec.get_current_epoch(state))
    )
    total_active_balance = max(spec.EFFECTIVE_BALANCE_INCREMENT, total_active_balance)
    return (
        spec.EFFECTIVE_BALANCE_INCREMENT
        * spec.BASE_REWARD_FACTOR
        * slot_duration_ms
        // int(spec.config.SLOT_DURATION_MS)
        // isqrt(total_active_balance)
    )


def expected_base_reward(spec, state, index, slot_duration_ms):
    increments = int(state.validators[index].effective_balance) // spec.EFFECTIVE_BALANCE_INCREMENT
    return increments * expected_base_reward_per_increment(spec, state, slot_duration_ms)


def fork_epoch_cases(spec, slot_duration_ms):
    genesis_ms = int(spec.config.SLOT_DURATION_MS)
    return [
        (FORK_EPOCH, FORK_EPOCH - 1, genesis_ms),
        (FORK_EPOCH, FORK_EPOCH, slot_duration_ms),
        (0, 0, slot_duration_ms),
        (0, 1, slot_duration_ms),
    ]
