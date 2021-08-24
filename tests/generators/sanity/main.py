from eth2spec.test.helpers.constants import PHASE0, ALTAIR, MERGE
from eth2spec.gen_helpers.gen_from_tests.gen import run_state_test_generators


if __name__ == "__main__":
    phase_0_mods = {key: 'eth2spec.test.phase0.sanity.test_' + key for key in [
        'blocks',
        'slots',
    ]}
    altair_mods = {**{key: 'eth2spec.test.altair.sanity.test_' + key for key in [
        'blocks',
    ]}, **phase_0_mods}  # also run the previous phase 0 tests

    # Altair-specific test cases are ignored, but should be included after the Merge is rebased onto Altair work.
    merge_mods = {**{key: 'eth2spec.test.merge.sanity.test_' + key for key in [
        'blocks',
    ]}, **phase_0_mods}  # TODO: Merge inherits phase0 tests for now.

    all_mods = {
        PHASE0: phase_0_mods,
        ALTAIR: altair_mods,
        MERGE: merge_mods,
    }

    run_state_test_generators(runner_name="sanity", all_mods=all_mods)
