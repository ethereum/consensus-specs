from eth2spec.gen_helpers.gen_from_tests.gen import run_state_test_generators
from eth2spec.test.helpers.constants import PHASE0, ALTAIR, MERGE


if __name__ == "__main__":
    phase_0_mods = {key: 'eth2spec.test.phase0.rewards.test_' + key for key in [
        'basic',
        'leak',
        'random',
    ]}
    # No additional altair specific rewards tests, yet.
    altair_mods = phase_0_mods

    # No additional merge specific rewards tests, yet.
    # Note: Block rewards are non-epoch rewards and are tested as part of block processing tests.
    # Transaction fees are part of the execution-layer.
    merge_mods = phase_0_mods

    all_mods = {
        PHASE0: phase_0_mods,
        ALTAIR: altair_mods,
        MERGE: merge_mods,
    }

    run_state_test_generators(runner_name="rewards", all_mods=all_mods)
