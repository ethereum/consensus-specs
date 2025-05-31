from collections.abc import Iterable
from importlib import import_module
from inspect import getmembers, isfunction
from pkgutil import walk_packages
from typing import Any

from eth2spec.gen_helpers.gen_base.gen_typing import TestCase
from eth2spec.test.helpers.constants import ALL_PRESETS, TESTGEN_FORKS
from eth2spec.test.helpers.typing import PresetBaseName, SpecForkName


def generate_case_fn(tfn, generator_mode, phase, preset, bls_active):
    return lambda: tfn(
        generator_mode=generator_mode, phase=phase, preset=preset, bls_active=bls_active
    )


def generate_from_tests(
    runner_name: str,
    handler_name: str,
    src: Any,
    fork_name: SpecForkName,
    preset_name: PresetBaseName,
    bls_active: bool = True,
    phase: str | None = None,
) -> Iterable[TestCase]:
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
    fn_names = [name for (name, _) in getmembers(src, isfunction) if name.startswith("test_")]

    if phase is None:
        phase = fork_name

    for name in fn_names:
        tfn = getattr(src, name)

        # strip off the `test_`
        case_name = name
        if case_name.startswith("test_"):
            case_name = case_name[5:]

        yield TestCase(
            fork_name=fork_name,
            preset_name=preset_name,
            runner_name=runner_name,
            handler_name=handler_name,
            suite_name=getattr(tfn, "suite_name", "pyspec_tests"),
            case_name=case_name,
            # TODO: with_all_phases and other per-phase tooling, should be replaced with per-fork equivalent.
            case_fn=generate_case_fn(
                tfn, generator_mode=True, phase=phase, preset=preset_name, bls_active=bls_active
            ),
        )


def get_expected_modules(package, absolute=False):
    """
    Return all modules (which are not packages) inside the given package.
    """
    modules = []
    eth2spec = import_module("eth2spec")
    prefix = eth2spec.__name__ + "."
    for _, modname, ispkg in walk_packages(eth2spec.__path__, prefix):
        s = package if absolute else f".{package}."
        # Skip modules in the unittests package.
        # These are not associated with generators.
        if ".unittests." in modname:
            continue
        if s in modname and not ispkg:
            modules.append(modname)
    return modules


def default_handler_name_fn(mod):
    return mod.split(".")[-1].replace("test_", "")


def get_test_cases_for(
    runner_name: str,
    pkg: str = None,
    handler_name_fn=default_handler_name_fn,
) -> Iterable[TestCase]:
    test_cases = []
    for preset in ALL_PRESETS:
        for fork in TESTGEN_FORKS:
            for mod in get_expected_modules(pkg or runner_name):
                tests_src = import_module(mod)
                test_cases.extend(
                    generate_from_tests(
                        runner_name=runner_name,
                        handler_name=handler_name_fn(mod),
                        src=tests_src,
                        fork_name=fork,
                        preset_name=preset,
                    )
                )
    return test_cases
