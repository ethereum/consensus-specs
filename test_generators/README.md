# Eth2.0 Test Generators

This directory contains all the generators for YAML tests, consumed by Eth 2.0 client implementations.

Any issues with the generators and/or generated tests should be filed
 in the repository that hosts the generator outputs, here: [ethereum/eth2.0-tests](https://github.com/ethereum/eth2.0-tests/).

Whenever a release is made, the new tests are automatically built and
[eth2TestGenBot](https://github.com/eth2TestGenBot) commits the changes to the test repository.

## How to run generators

pre-requisites:
- Python 3 installed
- PIP 3
- GNU make

### Cleaning

This removes the existing virtual environments (`/test_generators/<generator>/venv`), and generated tests (`/yaml_tests/`).

```bash
make clean 
```

### Running all test generators

This runs all the generators.

```bash
make gen_yaml_tests
```

### Running a single generator

The make file auto-detects generators in the `test_generators/` directory,
 and provides a tests-gen target for each generator, see example.

```bash
make ./yaml_tests/shuffling/
```

## Developing a generator

Simply open up the generator (not all at once) of choice in your favorite IDE/editor, and run:

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
eth-utils==1.4.1
../../test_libs/gen_helpers
../../test_libs/config_helpers
../../test_libs/pyspec
```
The config helper and pyspec is optional, but preferred. We encourage generators to derive tests from the spec itself, to prevent code duplication and outdated tests.
Applying configurations to the spec is easy, and enables you to create test suites with different contexts.

Note: make sure to run `make pyspec` from the root of the specs repository, to build the pyspec requirement.

Install all the necessary requirements (re-run when you add more):
```bash
pip3 install -r requirements.txt
```

And write your initial test generator, extending the base generator:

Write a `main.py` file, here's an example:

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
- you can have more than just 1 suite creator, e.g. ` gen_runner.run_generator("foo", [bar_test_suite, abc_test_suite, example_test_suite])`
- you can concatenate lists of test cases, if you don't want to split it up in suites.
- you can split your suite creators into different python files/packages, good for code organization.
- use config "minimal" for performance. But also implement a suite with the default config where necessary. 
- you may be able to write your test suite creator in a way where it does not make assumptions on constants.
  If so, you can generate test suites with different configurations for the same scenario (see example). 
- the test-generator accepts `--output` and `--force` (overwrite output)

## How to add a new test generator

In order to add a new test generator that builds `New Tests`:

1. Create a new directory `new_tests`, within the `test_generators` directory.
 Note that `new_tests` is also the name of the directory in which the tests will appear in the tests repository later.
2. Your generator is assumed to have a `requirements.txt` file,
 with any dependencies it may need. Leave it empty if your generator has none.
3. Your generator is assumed to have a `main.py` file in its root.
 By adding the base generator to your requirements, you can make a generator really easily. See docs below.
4. Your generator is called with `-o some/file/path/for_testing/can/be_anything -c some/other/path/to_configs/`.
 The base generator helps you handle this; you only have to define suite headers,
 and a list of tests for each suite you generate.
5. Finally, add any linting or testing commands to the
 [circleci config file](https://github.com/ethereum/eth2.0-test-generators/blob/master/.circleci/config.yml)
 if desired to increase code quality.

Note: you do not have to change the makefile.
However, if necessary (e.g. not using python, or mixing in other languages), submit an issue, and it can be a special case.
Do note that generators should be easy to maintain, lean, and based on the spec.


## How to remove a test generator

If a test generator is not needed anymore, undo the steps described above and make a new release:

1. remove the generator directory
2. remove the generated tests in the `eth2.0-tests` repository by opening a PR there.
3. make a new release
