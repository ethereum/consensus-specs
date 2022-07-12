from eth2spec.test.helpers.constants import ALTAIR, BELLATRIX
from eth2spec.gen_helpers.gen_from_tests.gen import run_state_test_generators


if __name__ == "__main__":
    altair_mods = {key: 'eth2spec.test.altair.sync_protocol.test_' + key for key in [
        'update_ranking',
    ]}
    bellatrix_mods = altair_mods

    all_mods = {
        ALTAIR: altair_mods,
        BELLATRIX: bellatrix_mods,
    }

    run_state_test_generators(runner_name="sync_protocol", all_mods=all_mods)
