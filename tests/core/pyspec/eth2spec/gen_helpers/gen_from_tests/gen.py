from importlib import import_module
from inspect import getmembers, isfunction
from pkgutil import walk_packages
from typing import Any, Callable, Dict, Iterable, Optional, List, Union

from eth2spec.utils import bls
from eth2spec.test.helpers.constants import ALL_PRESETS, TESTGEN_FORKS
from eth2spec.test.helpers.typing import SpecForkName, PresetBaseName

from eth2spec.gen_helpers.gen_base import gen_runner
from eth2spec.gen_helpers.gen_base.gen_typing import TestCase, TestProvider


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
    phase: Optional[str] = None,
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

    print("generating test vectors from tests source: %s" % src.__name__)
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


def get_provider(
    create_provider_fn: Callable[[SpecForkName, PresetBaseName, str, str], TestProvider],
    fork_name: SpecForkName,
    preset_name: PresetBaseName,
    all_mods: Dict[str, Dict[str, Union[List[str], str]]],
) -> Iterable[TestProvider]:
    for key, mod_name in all_mods[fork_name].items():
        if not isinstance(mod_name, List):
            mod_name = [mod_name]
        yield create_provider_fn(
            fork_name=fork_name,
            preset_name=preset_name,
            handler_name=key,
            tests_src_mod_name=mod_name,
        )


def get_create_provider_fn(
    runner_name: str,
) -> Callable[[SpecForkName, str, str, PresetBaseName], TestProvider]:
    def prepare_fn() -> None:
        bls.use_fastest()
        return

    def create_provider(
        fork_name: SpecForkName,
        preset_name: PresetBaseName,
        handler_name: str,
        tests_src_mod_name: List[str],
    ) -> TestProvider:
        def cases_fn() -> Iterable[TestCase]:
            for mod_name in tests_src_mod_name:
                tests_src = import_module(mod_name)
                yield from generate_from_tests(
                    runner_name=runner_name,
                    handler_name=handler_name,
                    src=tests_src,
                    fork_name=fork_name,
                    preset_name=preset_name,
                )

        return TestProvider(prepare=prepare_fn, make_cases=cases_fn)

    return create_provider


def run_state_test_generators(
    runner_name: str,
    all_mods: Dict[str, Dict[str, str]],
    presets: Iterable[PresetBaseName] = ALL_PRESETS,
    forks: Iterable[SpecForkName] = TESTGEN_FORKS,
) -> None:
    """
    Generate all available state tests of `TESTGEN_FORKS` forks of `ALL_PRESETS` presets of the given runner.
    """
    for preset_name in presets:
        for fork_name in forks:
            if fork_name in all_mods:
                gen_runner.run_generator(
                    runner_name,
                    get_provider(
                        create_provider_fn=get_create_provider_fn(runner_name),
                        fork_name=fork_name,
                        preset_name=preset_name,
                        all_mods=all_mods,
                    ),
                )


def combine_mods(dict_1, dict_2):
    """
    Return the merged dicts, where the result value would be a list of the values from two dicts.
    """
    # The duplicate dict_1 items would be ignored here.
    dict_3 = {**dict_1, **dict_2}

    intersection = dict_1.keys() & dict_2.keys()
    for key in intersection:
        # To list
        if not isinstance(dict_3[key], List):
            dict_3[key] = [dict_3[key]]
        # Append dict_1 value to list
        if isinstance(dict_1[key], List):
            dict_3[key] += dict_1[key]
        else:
            dict_3[key].append(dict_1[key])

    return dict_3


def check_mods(all_mods, pkg):
    """
    Raise an exception if there is a missing/unexpected module in all_mods.
    """

    def get_expected_modules(package, absolute=False):
        """
        Return all modules (which are not packages) inside the given package.
        """
        modules = []
        eth2spec = import_module("eth2spec")
        prefix = eth2spec.__name__ + "."
        for _, modname, ispkg in walk_packages(eth2spec.__path__, prefix):
            s = package if absolute else f".{package}."
            if s in modname and not ispkg:
                modules.append(modname)
        return modules

    mods = []
    for fork in all_mods:
        for mod in all_mods[fork].values():
            # If this key has a single value, normalize to list.
            if isinstance(mod, str):
                mod = [mod]

            # For each submodule, check if it is package.
            # This is a "trick" we do to reuse a test format.
            for sub in mod:
                is_package = ".test_" not in sub
                if is_package:
                    mods.extend(get_expected_modules(sub, absolute=True))
                else:
                    mods.append(sub)

    problems = []
    expected_mods = get_expected_modules(pkg)
    if mods != expected_mods:
        for e in expected_mods:
            # Skip forks which are not in all_mods.
            # The fork name is the 3rd item in the path.
            fork = e.split(".")[2]
            if fork not in all_mods:
                continue
            # Skip modules in the unittests package.
            # These are not associated with generators.
            if ".unittests." in e:
                continue
            # The expected module is not in our list of modules.
            # Add it to our list of problems.
            if e not in mods:
                problems.append("missing: " + e)

        for t in mods:
            # Skip helper modules.
            # These do not define test functions.
            if t.startswith("eth2spec.test.helpers"):
                continue
            # There is a module not defined in eth2spec.
            # Add it to our list of problems.
            if t not in expected_mods:
                print("unexpected:", t)
                problems.append("unexpected: " + t)

    if problems:
        raise Exception("[ERROR] module problems:\n " + "\n ".join(problems))
