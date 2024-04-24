from typing import Iterable

from eth2spec.test.helpers.constants import (
    CAPELLA, DENEB,
    MINIMAL, MAINNET,
)
from eth2spec.test.helpers.typing import SpecForkName, PresetBaseName
from eth2spec.test.deneb.fork import test_deneb_fork_basic, test_deneb_fork_random
from eth2spec.gen_helpers.gen_base import gen_runner, gen_typing
from eth2spec.gen_helpers.gen_from_tests.gen import generate_from_tests


def create_provider(tests_src, preset_name: PresetBaseName,
                    phase: SpecForkName, fork_name: SpecForkName) -> gen_typing.TestProvider:

    def prepare_fn() -> None:
        return

    def cases_fn() -> Iterable[gen_typing.TestCase]:
        return generate_from_tests(
            runner_name='fork',
            handler_name='fork',
            src=tests_src,
            fork_name=fork_name,
            preset_name=preset_name,
            phase=phase,
        )

    return gen_typing.TestProvider(prepare=prepare_fn, make_cases=cases_fn)


def _get_fork_tests_providers():
    for preset in [MINIMAL, MAINNET]:
        yield create_provider(test_deneb_fork_basic, preset, CAPELLA, DENEB)
        yield create_provider(test_deneb_fork_random, preset, CAPELLA, DENEB)


if __name__ == "__main__":
    gen_runner.run_generator("forks", list(_get_fork_tests_providers()))
