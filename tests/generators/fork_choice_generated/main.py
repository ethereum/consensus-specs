from eth2spec.gen_helpers.gen_from_tests.gen import run_state_test_generators, combine_mods
from eth2spec.test.helpers.constants import ALTAIR, BELLATRIX, CAPELLA, DENEB, EIP6110

if __name__ == "__main__":
    generated_modes = {key: 'eth2spec.test.phase0.fork_choice.test_' + key for key in [
        'sm_links_tree_model',
    ]}

    fork_choice_compliance_testing_modes = {
        ALTAIR: generated_modes,
        BELLATRIX: generated_modes,
        CAPELLA: generated_modes,
        DENEB: generated_modes
    }

    run_state_test_generators(runner_name="fork_choice_generated", all_mods=fork_choice_compliance_testing_modes)
