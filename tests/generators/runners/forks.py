from importlib import import_module
from typing import Iterable

from eth2spec.gen_helpers.gen_base.gen_typing import TestCase
from eth2spec.gen_helpers.gen_from_tests.gen import get_expected_modules, generate_from_tests
from eth2spec.test.helpers.constants import ALL_PRESETS, POST_FORK_OF


def get_test_cases() -> Iterable[TestCase]:
    test_cases = []
    for preset in ALL_PRESETS:
        for prefork, postfork in POST_FORK_OF.items():
            for mod in get_expected_modules("fork"):
                tests_src = import_module(mod)
                test_cases.extend(
                    generate_from_tests(
                        runner_name="fork",
                        handler_name="fork",
                        src=tests_src,
                        fork_name=postfork,
                        preset_name=preset,
                        phase=prefork,
                    )
                )
    return test_cases
