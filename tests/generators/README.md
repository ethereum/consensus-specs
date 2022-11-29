# Consensus test generators

This directory contains all the generators for tests, consumed by consensus-layer client implementations.

Any issues with the generators and/or generated tests should be filed in the repository that hosts the generator outputs,
 here: [ethereum/consensus-spec-tests](https://github.com/ethereum/consensus-spec-tests).

On releases, test generators are run by the release manager. Test-generation of mainnet tests can take a significant amount of time, and is better left out of a CI setup.

An automated nightly tests release system, with a config filter applied, is being considered as implementation needs mature.  

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [How to run generators](#how-to-run-generators)
  - [Cleaning](#cleaning)
  - [Running all test generators](#running-all-test-generators)
  - [Running a single generator](#running-a-single-generator)
- [Developing a generator](#developing-a-generator)
- [How to add a new test generator](#how-to-add-a-new-test-generator)
- [How to remove a test generator](#how-to-remove-a-test-generator)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->



## How to run generators

Prerequisites:
- Python 3 installed
- PIP 3
- GNU Make

### Cleaning

This removes the existing virtual environments (`/tests/generators/<generator>/venv`) and generated tests (`../consensus-spec-tests/tests`).

```bash
make clean 
```

### Running all test generators

This runs all of the generators.

```bash
make -j 4 generate_tests
```

The `-j N` flag makes the generators run in parallel, with `N` being the amount of cores.


### Running a single generator

The makefile auto-detects generators in the `tests/generators` directory and provides a tests-gen target (gen_<generator_name>) for each generator. See example:

```bash
make gen_ssz_static
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
pytest>=4.4
../../../[generator]
```

The config helper and pyspec is optional, but preferred. We encourage generators to derive tests from the spec itself in order to prevent code duplication and outdated tests.
Applying configurations to the spec is simple and enables you to create test suites with different contexts.

*Note*: Make sure to run `make pyspec` from the root of the specs repository in order to build the pyspec requirement.

Install all the necessary requirements (re-run when you add more):
```bash
pip3 install -r requirements.txt
```

Note that you may need `PYTHONPATH` to include the pyspec directory, as with running normal tests,
 to run test generators manually. The makefile handles this for you already.

And write your initial test generator, extending the base generator:

Write a `main.py` file. The shuffling test generator is a good minimal starting point:

```python
from eth2spec.phase0 import spec as spec
from eth_utils import to_tuple
from eth2spec.gen_helpers.gen_base import gen_runner, gen_typing
from preset_loader import loader
from typing import Iterable


def shuffling_case_fn(seed, count):
    yield 'mapping', 'data', {
        'seed': '0x' + seed.hex(),
        'count': count,
        'mapping': [int(spec.compute_shuffled_index(i, count, seed)) for i in range(count)]
    }


def shuffling_case(seed, count):
    return f'shuffle_0x{seed.hex()}_{count}', lambda: shuffling_case_fn(seed, count)


@to_tuple
def shuffling_test_cases():
    for seed in [spec.hash(seed_init_value.to_bytes(length=4, byteorder='little')) for seed_init_value in range(30)]:
        for count in [0, 1, 2, 3, 5, 10, 33, 100, 1000, 9999]:
            yield shuffling_case(seed, count)


def create_provider(config_name: str) -> gen_typing.TestProvider:

    def prepare_fn(configs_path: str) -> str:
        presets = loader.load_presets(configs_path, config_name)
        spec.apply_constants_preset(presets)
        return config_name

    def cases_fn() -> Iterable[gen_typing.TestCase]:
        for (case_name, case_fn) in shuffling_test_cases():
            yield gen_typing.TestCase(
                fork_name='phase0',
                runner_name='shuffling',
                handler_name='core',
                suite_name='shuffle',
                case_name=case_name,
                case_fn=case_fn
            )

    return gen_typing.TestProvider(prepare=prepare_fn, make_cases=cases_fn)


if __name__ == "__main__":
    gen_runner.run_generator("shuffling", [create_provider("minimal"), create_provider("mainnet")])
```

This generator:
- builds off of `gen_runner.run_generator` to handle configuration / filter / output logic.
- parametrized the creation of a test-provider to support multiple configs.
- Iterates through tests cases.
- Each test case provides a `case_fn`, to be executed by the `gen_runner.run_generator` if the case needs to be generated. But skipped otherwise.

To extend this, one could decide to parametrize the `shuffling_test_cases` function, and create test provider for any test-yielding function.

Another example, to generate tests from pytests:

```python
from eth2spec.phase0 import spec as spec_phase0
from eth2spec.altair import spec as spec_altair
from eth2spec.test.helpers.constants import PHASE0, ALTAIR

from eth2spec.gen_helpers.gen_from_tests.gen import run_state_test_generators


specs = (spec_phase0, spec_altair)


if __name__ == "__main__":
    phase_0_mods = {key: 'eth2spec.test.phase0.sanity.test_' + key for key in [
        'blocks',
        'slots',
    ]}
    altair_mods = {**{key: 'eth2spec.test.altair.sanity.test_' + key for key in [
        'blocks',
    ]}, **phase_0_mods}  # also run the previous phase 0 tests

    all_mods = {
        PHASE0: phase_0_mods,
        ALTAIR: altair_mods,
    }

    run_state_test_generators(runner_name="sanity", all_mods=all_mods)
```

Here multiple phases load the configuration, and the stream of test cases is derived from a pytest file using the `eth2spec.gen_helpers.gen_from_tests.gen.run_state_test_generators` utility. Note that this helper generates all available tests of `TESTGEN_FORKS` forks of `ALL_CONFIGS` configs of the given runner.

Recommendations:
- You can have more than just one test provider.
- Your test provider is free to output any configuration and combination of runner/handler/fork/case name.
- You can split your test case generators into different Python files/packages; this is good for code organization.
- Use config `minimal` for performance and simplicity, but also implement a suite with the `mainnet` config where necessary. 
- You may be able to write your test case provider in a way where it does not make assumptions on constants.
  If so, you can generate test cases with different configurations for the same scenario (see example). 
- See [`tests/core/gen_helpers/README.md`](../core/pyspec/eth2spec/gen_helpers/README.md) for command line options for generators.

## How to add a new test generator

To add a new test generator that builds `New Tests`:

1. Create a new directory `new_tests` within the `tests/generators` directory.
 Note that `new_tests` is also the name of the directory in which the tests will appear in the tests repository later.
2. Your generator is assumed to have a `requirements.txt` file,
 with any dependencies it may need. Leave it empty if your generator has none.
3. Your generator is assumed to have a `main.py` file in its root.
 By adding the base generator to your requirements, you can make a generator really easily. See docs below.
4. Your generator is called with `-o some/file/path/for_testing/can/be_anything --preset-list mainnet minimal`.
 The base generator helps you handle this; you only have to define test case providers.
5. Finally, add any linting or testing commands to the
 [circleci config file](../../.circleci/config.yml) if desired to increase code quality.
 Or add it to the [`Makefile`](../../Makefile), if it can be run locally.

*Note*: You do not have to change the makefile.
However, if necessary (e.g. not using Python, or mixing in other languages), submit an issue, and it can be a special case.
Do note that generators should be easy to maintain, lean, and based on the spec.


## How to remove a test generator

If a test generator is not needed anymore, undo the steps described above and make a new release:

1. Remove the generator directory.
2. Remove the generated tests in the [`consensus-spec-tests`](https://github.com/ethereum/consensus-spec-tests) repository by opening a pull request there.
3. Make a new release.
