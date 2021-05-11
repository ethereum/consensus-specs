from importlib import reload, import_module
from inspect import getmembers, isfunction
from typing import Any, Callable, Dict, Iterable, Optional

from eth2spec.config import config_util
from eth2spec.utils import bls
from eth2spec.test.helpers.constants import ALL_CONFIGS, TESTGEN_FORKS
from eth2spec.test.helpers.typing import SpecForkName, ConfigName

from eth2spec.gen_helpers.gen_base import gen_runner
from eth2spec.gen_helpers.gen_base.gen_typing import TestCase, TestProvider


def generate_from_tests(runner_name: str, handler_name: str, src: Any,
                        fork_name: SpecForkName, bls_active: bool = True,
                        phase: Optional[str]=None) -> Iterable[TestCase]:
    """
    Generate a list of test cases by running tests from the given src in generator-mode.
    :param runner_name: to categorize the test in general as.
    :param handler_name: to categorize the test specialization as.
    :param src: to retrieve tests from (discovered using inspect.getmembers).
    :param fork_name: the folder name for these tests.
           (if multiple forks are applicable, indicate the last fork)
    :param bls_active: optional, to override BLS switch preference. Defaults to True.
    :param phase: optional, to run tests against a particular spec version. Default to `fork_name` value.
    :return: an iterable of test cases.
    """
    fn_names = [
        name for (name, _) in getmembers(src, isfunction)
        if name.startswith('test_')
    ]

    if phase is None:
        phase = fork_name

    print("generating test vectors from tests source: %s" % src.__name__)
    for name in fn_names:
        tfn = getattr(src, name)

        # strip off the `test_`
        case_name = name
        if case_name.startswith('test_'):
            case_name = case_name[5:]

        yield TestCase(
            fork_name=fork_name,
            runner_name=runner_name,
            handler_name=handler_name,
            suite_name='pyspec_tests',
            case_name=case_name,
            # TODO: with_all_phases and other per-phase tooling, should be replaced with per-fork equivalent.
            case_fn=lambda: tfn(generator_mode=True, phase=phase, bls_active=bls_active)
        )


def get_provider(create_provider_fn: Callable[[SpecForkName, str, str, ConfigName], TestProvider],
                 config_name: ConfigName,
                 fork_name: SpecForkName,
                 all_mods: Dict[str, Dict[str, str]]) -> Iterable[TestProvider]:
    for key, mod_name in all_mods[fork_name].items():
        yield create_provider_fn(
            fork_name=fork_name,
            handler_name=key,
            tests_src_mod_name=mod_name,
            config_name=config_name,
        )


def get_create_provider_fn(
        runner_name: str, config_name: ConfigName, specs: Iterable[Any]
) -> Callable[[SpecForkName, str, str, ConfigName], TestProvider]:
    def prepare_fn(configs_path: str) -> str:
        config_util.prepare_config(configs_path, config_name)
        for spec in specs:
            reload(spec)
        bls.use_milagro()
        return config_name

    def create_provider(fork_name: SpecForkName, handler_name: str,
                        tests_src_mod_name: str, config_name: ConfigName) -> TestProvider:
        def cases_fn() -> Iterable[TestCase]:
            tests_src = import_module(tests_src_mod_name)
            return generate_from_tests(
                runner_name=runner_name,
                handler_name=handler_name,
                src=tests_src,
                fork_name=fork_name,
            )

        return TestProvider(prepare=prepare_fn, make_cases=cases_fn)
    return create_provider


def run_state_test_generators(runner_name: str, specs: Iterable[Any], all_mods: Dict[str, Dict[str, str]]) -> None:
    """
    Generate all available state tests of `TESTGEN_FORKS` forks of `ALL_CONFIGS` configs of the given runner.
    """
    for config_name in ALL_CONFIGS:
        for fork_name in TESTGEN_FORKS:
            if fork_name in all_mods:
                gen_runner.run_generator(runner_name, get_provider(
                    create_provider_fn=get_create_provider_fn(runner_name, config_name, specs),
                    config_name=config_name,
                    fork_name=fork_name,
                    all_mods=all_mods,
                ))
