import random

from eth2spec.phase0.spec import *
from eth_utils import (
    to_dict, to_tuple
)
from gen_base import gen_runner, gen_suite, gen_typing
from preset_loader import loader


@to_dict
def active_exited_validator_case(idx_max: int):
    validators = []

    # Standard deviation, around 8% validators will activate or exit within
    # ENTRY_EXIT_DELAY inclusive from EPOCH thus creating an edge case for validator
    # shuffling
    RAND_EPOCH_STD = 35

    # TODO: fix epoch numbers
    
    slot = 1000 * SLOTS_PER_EPOCH
    # The epoch, also a mean for the normal distribution
    epoch = slot_to_epoch(slot)
    MAX_EXIT_EPOCH = epoch + 5000  # Maximum exit_epoch for easier reading

    for idx in range(idx_max):
        v = Validator(
            pubkey=bytes(random.randint(0, 255) for _ in range(48)),
            withdrawal_credentials=bytes(random.randint(0, 255) for _ in range(32)),
            activation_epoch=FAR_FUTURE_EPOCH,
            exit_epoch=FAR_FUTURE_EPOCH,
            withdrawable_epoch=FAR_FUTURE_EPOCH,
            initiated_exit=False,
            slashed=False,
            high_balance=0
        )
        # 4/5 of all validators are active
        if random.random() < 0.8:
            # Choose a normally distributed epoch number
            rand_epoch = round(random.gauss(epoch, RAND_EPOCH_STD))

            # for 1/2 of *active* validators rand_epoch is the activation epoch
            if random.random() < 0.5:
                v.activation_epoch = rand_epoch

                # 1/4 of active validators will exit in forseeable future
                if random.random() < 0.5:
                    v.exit_epoch = random.randint(
                        rand_epoch + ACTIVATION_EXIT_DELAY + 1, MAX_EXIT_EPOCH)
                # 1/4 of active validators in theory remain in the set indefinitely
                else:
                    v.exit_epoch = FAR_FUTURE_EPOCH
            # for the other active 1/2 rand_epoch is the exit epoch
            else:
                v.activation_epoch = random.randint(
                    0, rand_epoch - ACTIVATION_EXIT_DELAY)
                v.exit_epoch = rand_epoch

        # The remaining 1/5 of all validators is not activated
        else:
            v.activation_epoch = FAR_FUTURE_EPOCH
            v.exit_epoch = FAR_FUTURE_EPOCH

        validators.append(v)

    query_slot = slot + random.randint(-1, 1)
    state = get_genesis_beacon_state([], 0, None)
    state.validator_registry = validators
    state.latest_randao_mixes = [b'\xde\xad\xbe\xef' * 8 for _ in range(LATEST_RANDAO_MIXES_LENGTH)]
    state.slot = slot
    state.latest_start_shard = random.randint(0, SHARD_COUNT - 1)
    randao_mix = bytes(random.randint(0, 255) for _ in range(32))
    state.latest_randao_mixes[slot_to_epoch(query_slot) % LATEST_RANDAO_MIXES_LENGTH] = randao_mix

    committees = get_crosslink_committees_at_slot(state, query_slot)
    yield 'validator_registry', [
        {
            'activation_epoch': v.activation_epoch,
            'exit_epoch': v.exit_epoch
        } for v in state.validator_registry
    ]
    yield 'randao_mix', '0x'+randao_mix.hex()
    yield 'state_slot', state.slot
    yield 'query_slot', query_slot
    yield 'latest_start_shard', state.latest_start_shard
    yield 'crosslink_committees', committees


@to_tuple
def active_exited_validator_cases():
    for i in range(3):
        yield active_exited_validator_case(random.randint(100, min(200, SHARD_COUNT * 2)))


def mini_shuffling_suite(configs_path: str) -> gen_typing.TestSuiteOutput:
    presets = loader.load_presets(configs_path, 'minimal')
    apply_constants_preset(presets)

    return ("shuffling_minimal", "core", gen_suite.render_suite(
        title="Shuffling Algorithm Tests with minimal config",
        summary="Test vectors for validator shuffling with different validator registry activity status and set size."
                " Note: only relevant fields are defined.",
        forks_timeline="testing",
        forks=["phase0"],
        config="minimal",
        handler="core",
        test_cases=active_exited_validator_cases()))


def full_shuffling_suite(configs_path: str) -> gen_typing.TestSuiteOutput:
    presets = loader.load_presets(configs_path, 'mainnet')
    apply_constants_preset(presets)

    return ("shuffling_full", "core", gen_suite.render_suite(
        title="Shuffling Algorithm Tests with mainnet config",
        summary="Test vectors for validator shuffling with different validator registry activity status and set size."
                " Note: only relevant fields are defined.",
        forks_timeline="mainnet",
        forks=["phase0"],
        config="mainnet",
        handler="core",
        test_cases=active_exited_validator_cases()))


if __name__ == "__main__":
    gen_runner.run_generator("shuffling", [mini_shuffling_suite, full_shuffling_suite])
