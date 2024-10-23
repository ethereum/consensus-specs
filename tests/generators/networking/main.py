
from eth2spec.test.helpers.constants import EIP7594
from eth2spec.gen_helpers.gen_from_tests.gen import run_state_test_generators, check_mods


if __name__ == "__main__":
    eip7594_mods = {key: 'eth2spec.test.eip7594.networking.test_' + key for key in [
        'compute_columns_for_custody_group',
        'get_custody_groups',
    ]}
    all_mods = {
        EIP7594: eip7594_mods
    }
    check_mods(all_mods, "networking")

    run_state_test_generators(runner_name="networking", all_mods=all_mods)
