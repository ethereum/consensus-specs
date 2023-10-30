from eth2spec.test.helpers.constants import DENEB
from eth2spec.gen_helpers.gen_from_tests.gen import run_state_test_generators


if __name__ == "__main__":
    deneb_mods = {key: 'eth2spec.test.deneb.merkle_proof.test_' + key for key in [
        'single_merkle_proof',
    ]}

    all_mods = {
        DENEB: deneb_mods,
    }

    run_state_test_generators(runner_name="merkle_proof", all_mods=all_mods)
