from importlib import import_module
from inspect import getmembers, isfunction
from typing import Any, Callable, Dict, Iterable, Optional

from eth2spec.utils import bls
from eth2spec.test.helpers.constants import ALL_PRESETS, TESTGEN_FORKS
from eth2spec.test.helpers.typing import SpecForkName, PresetBaseName

from eth2spec.gen_helpers.gen_base import gen_runner
from eth2spec.gen_helpers.gen_base.gen_typing import TestCase, TestProvider


def generate_from_tests(runner_name: str, handler_name: str, src: Any,
                        fork_name: SpecForkName, preset_name: PresetBaseName,
                        bls_active: bool = True,
                        phase: Optional[str]=None) -> Iterable[TestCase]:
    """
    Generate a list of test cases by running tests from the given src in generator-mode.
    :param runner_name: to categorize the test in general as.
    :param handler_name: to categorize the test specialization as.
    :param src: to retrieve tests from (discovered using inspect.getmembers).
    :param fork_name: the folder name for these tests.
           (if multiple forks are applicable, indicate the last fork)
    :param preset_name: to select a preset. Tests that do not support the preset will be skipped.
    :param bls_active: optional, to override BLS switch preference. Defaults to True.
    :param phase: optional, to run tests against a particular spec version. Default to `fork_name` value.
           Set to the pre-fork (w.r.t. fork_name) in multi-fork tests.
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
            preset_name=preset_name,
            runner_name=runner_name,
            handler_name=handler_name,
            suite_name='pyspec_tests',
            case_name=case_name,
            # TODO: with_all_phases and other per-phase tooling, should be replaced with per-fork equivalent.
            case_fn=lambda: tfn(generator_mode=True, phase=phase, preset=preset_name, bls_active=bls_active)
        )


def get_provider(create_provider_fn: Callable[[SpecForkName, PresetBaseName, str, str], TestProvider],
                 fork_name: SpecForkName,
                 preset_name: PresetBaseName,
                 all_mods: Dict[str, Dict[str, str]]) -> Iterable[TestProvider]:
    for key, mod_name in all_mods[fork_name].items():
        yield create_provider_fn(
            fork_name=fork_name,
            preset_name=preset_name,
            handler_name=key,
            tests_src_mod_name=mod_name,
        )


def get_create_provider_fn(runner_name: str) -> Callable[[SpecForkName, str, str, PresetBaseName], TestProvider]:
    def prepare_fn() -> None:
        bls.use_milagro()
        return

    def create_provider(fork_name: SpecForkName, preset_name: PresetBaseName,
                        handler_name: str, tests_src_mod_name: str) -> TestProvider:
        def cases_fn() -> Iterable[TestCase]:
            tests_src = import_module(tests_src_mod_name)
            return generate_from_tests(
                runner_name=runner_name,
                handler_name=handler_name,
                src=tests_src,
                fork_name=fork_name,
                preset_name=preset_name,
            )

        return TestProvider(prepare=prepare_fn, make_cases=cases_fn)
    return create_provider


def run_state_test_generators(runner_name: str,
                              all_mods: Dict[str, Dict[str, str]],
                              presets: Iterable[PresetBaseName] = ALL_PRESETS,
                              forks: Iterable[SpecForkName] = TESTGEN_FORKS) -> None:
    """
    Generate all available state tests of `TESTGEN_FORKS` forks of `ALL_PRESETS` presets of the given runner.
    """
    for preset_name in presets:
        for fork_name in forks:
            if fork_name in all_mods:
                gen_runner.run_generator(runner_name, get_provider(
                    create_provider_fn=get_create_provider_fn(runner_name),
                    fork_name=fork_name,
                    preset_name=preset_name,
                    all_mods=all_mods,
                ))
