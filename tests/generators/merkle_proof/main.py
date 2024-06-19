from eth2spec.test.helpers.constants import DENEB, ELECTRA, EIP7594
from eth2spec.gen_helpers.gen_from_tests.gen import run_state_test_generators, combine_mods


if __name__ == "__main__":
    deneb_mods = {key: 'eth2spec.test.deneb.merkle_proof.test_' + key for key in [
        'single_merkle_proof',
    ]}
    _new_eip7594_mods = {key: 'eth2spec.test.eip7594.merkle_proof.test_' + key for key in [
        'single_merkle_proof',
    ]}
    electra_mods = deneb_mods
    eip_7594_mods = combine_mods(_new_eip7594_mods, deneb_mods)

    all_mods = {
        DENEB: deneb_mods,
        ELECTRA: electra_mods,
        EIP7594: eip_7594_mods,
    }

    run_state_test_generators(runner_name="merkle_proof", all_mods=all_mods)
