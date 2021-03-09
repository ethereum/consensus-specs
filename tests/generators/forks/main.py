from importlib import reload
from typing import Iterable

from eth2spec.test.context import LIGHTCLIENT_PATCH
from eth2spec.config import config_util
from eth2spec.test.lightclient_patch.fork import test_fork as test_altair_forks
from eth2spec.phase0 import spec as spec_phase0

from eth2spec.gen_helpers.gen_base import gen_runner, gen_typing
from eth2spec.gen_helpers.gen_from_tests.gen import generate_from_tests


pre_specs = {
    LIGHTCLIENT_PATCH: spec_phase0,
}


def create_provider(fork_name: str, tests_src, config_name: str) -> gen_typing.TestProvider:

    def prepare_fn(configs_path: str) -> str:
        config_util.prepare_config(configs_path, config_name)
        reload(pre_specs[fork_name])
        return config_name

    def cases_fn() -> Iterable[gen_typing.TestCase]:
        return generate_from_tests(
            runner_name='forks',
            handler_name='core',
            src=tests_src,
            fork_name=fork_name,
        )

    return gen_typing.TestProvider(prepare=prepare_fn, make_cases=cases_fn)


if __name__ == "__main__":
    gen_runner.run_generator("forks", [
        create_provider(LIGHTCLIENT_PATCH, test_altair_forks, 'minimal'),
        create_provider(LIGHTCLIENT_PATCH, test_altair_forks, 'minimal'),
    ])
