from eth2spec.gen_helpers.gen_from_tests.gen import run_state_test_generators, combine_mods
from eth2spec.test.helpers.constants import PHASE0, ALTAIR, BELLATRIX, CAPELLA, DENEB, EIP6110


if __name__ == "__main__":
    phase_0_mods = {key: 'eth2spec.test.phase0.genesis.test_' + key for key in [
        'initialization',
        'validity',
    ]}

    altair_mods = phase_0_mods

    # we have new unconditional lines in `initialize_beacon_state_from_eth1` and we want to test it
    _new_bellatrix_mods = {key: 'eth2spec.test.bellatrix.genesis.test_' + key for key in [
        'initialization',
    ]}
    bellatrix_mods = combine_mods(_new_bellatrix_mods, altair_mods)
    capella_mods = bellatrix_mods  # No additional Capella specific genesis tests
    deneb_mods = capella_mods  # No additional Deneb specific genesis tests
    eip6110_mods = deneb_mods  # No additional EIP6110 specific genesis tests
    all_mods = {
        PHASE0: phase_0_mods,
        ALTAIR: altair_mods,
        BELLATRIX: bellatrix_mods,
        CAPELLA: capella_mods,
        DENEB: deneb_mods,
        EIP6110: eip6110_mods,
    }

    run_state_test_generators(runner_name="genesis", all_mods=all_mods)
