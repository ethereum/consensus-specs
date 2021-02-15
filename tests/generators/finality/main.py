from typing import Iterable
from importlib import reload, import_module

from gen_base import gen_runner, gen_typing
from gen_from_tests.gen import generate_from_tests, get_provider

from eth2spec.test.context import PHASE0, PHASE1, LIGHTCLIENT_PATCH, TESTGEN_FORKS, ALL_CONFIGS
from eth2spec.config import config_util
from eth2spec.phase0 import spec as spec_phase0
from eth2spec.lightclient_patch import spec as spec_lightclient_patch
from eth2spec.phase1 import spec as spec_phase1
from eth2spec.utils import bls


def create_provider(fork_name: str, handler_name: str,
                    tests_src_mod_name: str, config_name: str) -> gen_typing.TestProvider:

    def prepare_fn(configs_path: str) -> str:
        config_util.prepare_config(configs_path, config_name)
        reload(spec_phase0)
        reload(spec_lightclient_patch)
        reload(spec_phase1)
        bls.use_milagro()
        return config_name

    def cases_fn() -> Iterable[gen_typing.TestCase]:
        tests_src = import_module(tests_src_mod_name)
        return generate_from_tests(
            runner_name='finality',
            handler_name=handler_name,
            src=tests_src,
            fork_name=fork_name,
        )

    return gen_typing.TestProvider(prepare=prepare_fn, make_cases=cases_fn)


if __name__ == "__main__":
    phase_0_mods = {'finality': 'eth2spec.test.phase0.finality.test_finality'}
    # No additional lightclient_patch or phase 1 specific finality tests, yet.
    lightclient_patch_mods = phase_0_mods
    phase_1_mods = phase_0_mods

    all_mods = {
        PHASE0: phase_0_mods,
        LIGHTCLIENT_PATCH: lightclient_patch_mods,
        PHASE1: phase_1_mods,
    }

    for config_name in ALL_CONFIGS:
        for fork_name in TESTGEN_FORKS:
            if fork_name in all_mods:
                gen_runner.run_generator(f"finality", get_provider(
                    create_provider_fn=create_provider, config_name=config_name,
                    fork_name=fork_name, all_mods=all_mods,
                ))
