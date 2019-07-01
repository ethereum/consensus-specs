from typing import Callable, Iterable

from eth2spec.test.genesis import test_initialization, test_validity

from gen_base import gen_runner, gen_suite, gen_typing
from gen_from_tests.gen import generate_from_tests
from preset_loader import loader
from eth2spec.phase0 import spec as spec


def create_suite(handler_name: str, config_name: str, get_cases: Callable[[], Iterable[gen_typing.TestCase]]) \
        -> Callable[[str], gen_typing.TestSuiteOutput]:
    def suite_definition(configs_path: str) -> gen_typing.TestSuiteOutput:
        presets = loader.load_presets(configs_path, config_name)
        spec.apply_constants_preset(presets)

        return ("genesis_%s_%s" % (handler_name, config_name), handler_name, gen_suite.render_suite(
            title="genesis testing",
            summary="Genesis test suite, %s type, generated from pytests" % handler_name,
            forks_timeline="testing",
            forks=["phase0"],
            config=config_name,
            runner="genesis",
            handler=handler_name,
            test_cases=get_cases()))
    return suite_definition


if __name__ == "__main__":
    gen_runner.run_generator("genesis", [
        create_suite('initialization', 'minimal', lambda: generate_from_tests(test_initialization, 'phase0')),
        create_suite('validity', 'minimal', lambda: generate_from_tests(test_validity, 'phase0')),
    ])
