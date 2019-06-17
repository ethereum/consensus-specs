# Eth 2.0 Test Generators

This directory contains all the generators for YAML tests, consumed by Eth 2.0 client implementations.

Any issues with the generators and/or generated tests should be filed in the repository that hosts the generator outputs, here: [ethereum/eth2.0-spec-tests](https://github.com/ethereum/eth2.0-spec-tests).

Test-vectors are generated and published by the release-publishers for every release.

Spec-tests are unified with the executable spec: these tests are PyTest compatible, run in CI, but also enable special settings.
Settings include:
 - BLS on/off: see `ethspec.utils.bls.py > .bls_active`, and BLS-switch test decorators in `eth2spec.test.context.py`
 - "generator mode": output the relevant test data into an encoded copy (`test_my_fn(generator_mode=True)`, enabled by decorating `test_my_fn` with `ethspec.test.utils.spectest()`)

## How to run generators

Prerequisites:
- Python 3 installed
- PIP 3
- GNU Make

### Cleaning

This removes the existing virtual environments (`/test_generators/<generator>/venv`) and generated tests (`/yaml_tests/`).

```bash
make clean 
```

### Running all test generators

This runs all of the generators.

```bash
make -j 4 gen_yaml_tests
```

The `-j N` flag makes the generators run in parallel, with `N` being the amount of cores.


### Running a single generator

The makefile auto-detects generators in the `test_generators` directory and provides a tests-gen target for each generator. See example:

```bash
make ./yaml_tests/shuffling/
```

## Developing a generator

Simply open up the generator (not all at once) of choice in your favorite IDE/editor and run:

```bash
# From the root of the generator directory:
# Create a virtual environment (any venv/.venv/.venvs is git-ignored)
python3 -m venv venv
# Activate the venv, this is where dependencies are installed for the generator
. venv/bin/activate
```

Now that you have a virtual environment, write your generator.
It's recommended to extend the base-generator.

Create a `requirements.txt` in the root of your generator directory:
```
eth-utils==1.6.0
../../test_libs/gen_helpers
../../test_libs/config_helpers
../../test_libs/pyspec
```
The config helper and pyspec is optional, but preferred. We encourage generators to derive tests from the spec itself in order to prevent code duplication and outdated tests.
Applying configurations to the spec is simple and enables you to create test suites with different contexts.

*Note*: Make sure to run `make pyspec` from the root of the specs repository in order to build the pyspec requirement.

Install all the necessary requirements (re-run when you add more):
```bash
pip3 install -r requirements.txt
```

And write your initial test generator, extending the base generator:

Write a `main.py` file. See example:

```python
from gen_base import gen_runner, gen_suite, gen_typing

from eth_utils import (
    to_dict, to_tuple
)

from preset_loader import loader
from eth2spec.phase0 import spec

@to_dict
def example_test_case(v: int):
    yield "spec_SHARD_COUNT", spec.SHARD_COUNT
    yield "example", v


@to_tuple
def generate_example_test_cases():
    for i in range(10):
        yield example_test_case(i)


def example_minimal_suite(configs_path: str) -> gen_typing.TestSuiteOutput:
    presets = loader.load_presets(configs_path, 'minimal')
    spec.apply_constants_preset(presets)

    return ("mini", "core", gen_suite.render_suite(
        title="example_minimal",
        summary="Minimal example suite, testing bar.",
        forks_timeline="testing",
        forks=["phase0"],
        config="minimal",
        handler="main",
        test_cases=generate_example_test_cases()))


def example_mainnet_suite(configs_path: str) -> gen_typing.TestSuiteOutput:
    presets = loader.load_presets(configs_path, 'mainnet')
    spec.apply_constants_preset(presets)

    return ("full", "core", gen_suite.render_suite(
        title="example_main_net",
        summary="Main net based example suite.",
        forks_timeline= "mainnet",
        forks=["phase0"],
        config="testing",
        handler="main",
        test_cases=generate_example_test_cases()))


if __name__ == "__main__":
    gen_runner.run_generator("example", [example_minimal_suite, example_mainnet_suite])
```

Recommendations:
- You can have more than just one suite creator, e.g. ` gen_runner.run_generator("foo", [bar_test_suite, abc_test_suite, example_test_suite])`.
- You can concatenate lists of test cases if you don't want to split it up in suites, however, make sure they can be run with one handler.
- You can split your suite creators into different Python files/packages; this is good for code organization.
- Use config "minimal" for performance, but also implement a suite with the default config where necessary. 
- You may be able to write your test suite creator in a way where it does not make assumptions on constants.
  If so, you can generate test suites with different configurations for the same scenario (see example). 
- The test-generator accepts `--output` and `--force` (overwrite output).

## How to add a new test generator

To add a new test generator that builds `New Tests`:

1. Create a new directory `new_tests` within the `test_generators` directory.
 Note that `new_tests` is also the name of the directory in which the tests will appear in the tests repository later.
2. Your generator is assumed to have a `requirements.txt` file,
 with any dependencies it may need. Leave it empty if your generator has none.
3. Your generator is assumed to have a `main.py` file in its root.
 By adding the base generator to your requirements, you can make a generator really easily. See docs below.
4. Your generator is called with `-o some/file/path/for_testing/can/be_anything -c some/other/path/to_configs/`.
 The base generator helps you handle this; you only have to define suite headers
 and a list of tests for each suite you generate.
5. Finally, add any linting or testing commands to the
 [circleci config file](https://github.com/ethereum/eth2.0-test-generators/blob/master/.circleci/config.yml)
 if desired to increase code quality.

*Note*: You do not have to change the makefile.
However, if necessary (e.g. not using Python, or mixing in other languages), submit an issue, and it can be a special case.
Do note that generators should be easy to maintain, lean, and based on the spec.


## How to remove a test generator

If a test generator is not needed anymore, undo the steps described above and make a new release:

1. Remove the generator directory.
2. Remove the generated tests in the [`eth2.0-spec-tests`](https://github.com/ethereum/eth2.0-spec-tests) repository by opening a pull request there.
3. Make a new release.
