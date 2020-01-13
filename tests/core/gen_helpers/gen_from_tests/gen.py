from inspect import getmembers, isfunction
from typing import Any, Iterable

from gen_base.gen_typing import TestCase


def generate_from_tests(runner_name: str, handler_name: str, src: Any,
                        fork_name: str, bls_active: bool = True) -> Iterable[TestCase]:
    """
    Generate a list of test cases by running tests from the given src in generator-mode.
    :param runner_name: to categorize the test in general as.
    :param handler_name: to categorize the test specialization as.
    :param src: to retrieve tests from (discovered using inspect.getmembers).
    :param fork_name: to run tests against particular phase and/or fork.
           (if multiple forks are applicable, indicate the last fork)
    :param bls_active: optional, to override BLS switch preference. Defaults to True.
    :return: an iterable of test cases.
    """
    fn_names = [
        name for (name, _) in getmembers(src, isfunction)
        if name.startswith('test_')
    ]
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
            case_fn=lambda: tfn(generator_mode=True, phase=fork_name, bls_active=bls_active)
        )
