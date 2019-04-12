from uint_test_cases import (
    generate_random_uint_test_cases,
    generate_uint_wrong_length_test_cases,
    generate_uint_bounds_test_cases,
    generate_uint_out_of_bounds_test_cases
)

from gen_base import gen_runner, gen_suite, gen_typing

def ssz_random_uint_suite(configs_path: str) -> gen_typing.TestSuiteOutput:
    return ("uint_random", "uint", gen_suite.render_suite(
        title="UInt Random",
        summary="Random integers chosen uniformly over the allowed value range",
        forks_timeline= "mainnet",
        forks=["phase0"],
        config="mainnet",
        handler="core",
        test_cases=generate_random_uint_test_cases()))

def ssz_wrong_uint_suite(configs_path: str) -> gen_typing.TestSuiteOutput:
    return ("uint_wrong_length", "uint", gen_suite.render_suite(
        title="UInt Wrong Length",
        summary="Serialized integers that are too short or too long",
        forks_timeline= "mainnet",
        forks=["phase0"],
        config="mainnet",
        handler="core",
        test_cases=generate_uint_wrong_length_test_cases()))

def ssz_uint_bounds_suite(configs_path: str) -> gen_typing.TestSuiteOutput:
    return ("uint_bounds", "uint", gen_suite.render_suite(
        title="UInt Bounds",
        summary="Integers right at or beyond the bounds of the allowed value range",
        forks_timeline= "mainnet",
        forks=["phase0"],
        config="mainnet",
        handler="core",
        test_cases=generate_uint_bounds_test_cases() + generate_uint_out_of_bounds_test_cases()))


if __name__ == "__main__":
    gen_runner.run_generator("ssz", [ssz_random_uint_suite, ssz_wrong_uint_suite, ssz_uint_bounds_suite])
