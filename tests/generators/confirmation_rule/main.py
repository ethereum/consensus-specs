from eth2spec.gen_helpers.gen_from_tests.gen import run_state_test_generators
from eth2spec.test.helpers.constants import BELLATRIX, CAPELLA, DENEB, EIP6110


if __name__ == "__main__":
    # Note: Confirmation rule tests start from Bellatrix
    bellatrix_mods = {key: 'eth2spec.test.bellatrix.confirmation_rule.test_' + key for key in [
        'confirmation_rule'
    ]}

    capella_mods = bellatrix_mods  # No additional Capella specific fork choice tests
    deneb_mods = capella_mods  # No additional Deneb specific fork choice tests
    eip6110_mods = deneb_mods  # No additional EIP6110 specific fork choice tests

    all_mods = {
        BELLATRIX: bellatrix_mods,
        CAPELLA: capella_mods,
        DENEB: deneb_mods,
        EIP6110: eip6110_mods,
    }

    run_state_test_generators(runner_name="confirmation_rule", all_mods=all_mods)
