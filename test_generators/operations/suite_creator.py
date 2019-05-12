from typing import Callable, Iterable
from inspect import getmembers, isfunction
from gen_base import gen_suite, gen_typing
from preset_loader import loader
from eth2spec.phase0 import spec


def generate_from_tests(pkg):
    fn_names = [
        name for (name, _) in getmembers(pkg, isfunction)
        if name.startswith('test_')
    ]
    out = []
    print("generating test vectors from tests package: %s" % pkg.__name__)
    for name in fn_names:
        tfn = getattr(pkg, name)
        try:
            out.append(tfn(generator_mode=True))
        except AssertionError:
            print("ERROR: failed to generate vector from test: %s (pkg: %s)" % (name, pkg.__name__))
    return out


def create_suite(operation_name: str, config_name: str, get_cases: Callable[[], Iterable[gen_typing.TestCase]])\
        -> Callable[[str], gen_typing.TestSuiteOutput]:
    def suite_definition(configs_path: str) -> gen_typing.TestSuiteOutput:
        presets = loader.load_presets(configs_path, config_name)
        spec.apply_constants_preset(presets)

        return ("%s_%s" % (operation_name, config_name), operation_name, gen_suite.render_suite(
            title="%s operation" % operation_name,
            summary="Test suite for %s type operation processing" % operation_name,
            forks_timeline="testing",
            forks=["phase0"],
            config=config_name,
            runner="operations",
            handler=config_name,
            test_cases=get_cases()))
    return suite_definition
