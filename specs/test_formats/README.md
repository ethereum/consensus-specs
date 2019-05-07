# General test format

This document defines the YAML format and structure used for Eth 2.0 testing.

## Table of contents
<!-- TOC -->

- [General test format](#general-test-format)
    - [Table of contents](#table-of-contents)
    - [About](#about)
        - [Test-case formats](#test-case-formats)
    - [Glossary](#glossary)
    - [Test format philosophy](#test-format-philosophy)
        - [Config design](#config-design)
        - [Fork config design](#fork-config-design)
        - [Test completeness](#test-completeness)
    - [Test suite](#test-suite)
    - [Config](#config)
    - [Fork-timeline](#fork-timeline)
    - [Config sourcing](#config-sourcing)
    - [Test structure](#test-structure)
    - [Note for implementers](#note-for-implementers)

<!-- /TOC -->

## About

Ethereum 2.0 uses YAML as the format for all cross client tests. This document describes at a high level the general format to which all test files should conform.

### Test-case formats

The particular formats of specific types of tests (test suites) are defined in separate documents.

Test formats:
- [`bls`](./bls/README.md)
- [`operations`](./operations/README.md)
- [`shuffling`](./shuffling/README.md)
- [`ssz`](./ssz/README.md)
- More formats are planned, see tracking issues for CI/testing

## Glossary

- `generator`: a program that outputs one or more `suite` files.
  - A generator should only output one `type` of test.
  - A generator is free to output multiple `suite` files, optionally with different `handler`s.
- `type`: the specialization of one single `generator`.
- `suite`: a YAML file with:
  - a header: describes the `suite`, and defines what the `suite` is for
  - a list of test cases
- `runner`: where a generator is a *"producer"*, this is the *"consumer"*.
  - A `runner` focuses on *only one* `type`, and each type has *only one* `runner`.
- `handler`: a `runner` may be too limited sometimes, you may have a `suite` with a specific focus that requires a different format.
  To facilitate this, you specify a `handler`: the runner can deal with the format by using the specified handler.
  Using a `handler` in a `runner` is optional.
- `case`: a test case, an entry in the `test_cases` list of a `suite`. A case can be anything in general, 
  but its format should be well-defined in the documentation corresponding to the `type` (and `handler`).\
  A test has the same exact configuration and fork context as the other entries in the `case` list of its `suite`.
- `forks_timeline`: a fork timeline definition, a YAML file containing a key for each fork-name, and an epoch number as value.

## Test format philosophy

### Config design

After long discussion, the following types of configured constants were identified:
- Never changing: genesis data.
- Changing, but reliant on old value: e.g. an epoch time may change, but if you want to do the conversion 
  `(genesis data, timestamp) -> epoch number`, you end up needing both constants.
- Changing, but kept around during fork transition: finalization may take a while,
  e.g. an executable has to deal with new deposits and old deposits at the same time. Another example may be economic constants.
- Additional, backwards compatible: new constants are introduced for later phases.
- Changing: there is a very small chance some constant may really be *replaced*. 
  In this off-chance, it is likely better to include it as an additional variable,
  and some clients may simply stop supporting the old one if they do not want to sync from genesis.

Based on these types of changes, we model the config as a list of key value pairs,
 that only grows with every fork (they may change in development versions of forks, however; git manages this).
With this approach, configurations are backwards compatible (older clients ignore unknown variables) and easy to maintain.

### Fork config design

There are two types of fork-data:
1) Timeline: When does a fork take place?
2) Coverage: What forks are covered by a test?

The first is neat to have as a separate form: we prevent duplication, and can run with different presets
 (e.g. fork timeline for a minimal local test, for a public testnet, or for mainnet).

The second does not affect the result of the tests, it just states what is covered by the tests,
 so that the right suites can be executed to see coverage for a certain fork.
For some types of tests, it may be beneficial to ensure it runs exactly the same, with any given fork "active".
Test-formats can be explicit on the need to repeat a test with different forks being "active",
 but generally tests run only once.

### Test completeness

Tests should be independent of any sync-data. If one wants to run a test, the input data should be available from the YAML.
The aim is to provide clients with a well-defined scope of work to run a particular set of test-suites.

- Clients that are complete are expected to contribute to testing, seeking for better resources to get conformance with the spec, and other clients.
- Clients that are not complete in functionality can choose to ignore suites that use certain test-runners, or specific handlers of these test-runners.
- Clients that are on older versions can test their work based on older releases of the generated tests, and catch up with newer releases when possible.

## Test suite

```
title: <string, short, one line> -- Display name for the test suite
summary: <string, average, 1-3 lines> -- Summarizes the test suite
forks_timeline: <string, reference to a fork definition file, without extension> -- Used to determine the forking timeline
forks: <list of strings> -- Defines the coverage. Test-runner code may decide to re-run with the different forks "activated", when applicable.
config: <string, reference to a config file, without extension> -- Used to determine which set of constants to run (possibly compile time) with
runner: <string, no spaces, python-like naming format> *MUST be consistent with folder structure*
handler: <string, no spaces, python-like naming format> *MUST be consistent with folder structure*

test_cases: <list, values being maps defining a test case each>
   ...

```

## Config

A configuration is a separate YAML file.
Separation of configuration and tests aims to:
- Prevent duplication of configuration
- Make all tests easy to upgrade (e.g. when a new config constant is introduced)
- Clearly define which constants to use
- Shareable between clients, for cross-client short- or long-lived testnets
- Minimize the amounts of different constants permutations to compile as a client.
  *Note*: Some clients prefer compile-time constants and optimizations.
  They should compile for each configuration once, and run the corresponding tests per build target.

The format is described in [`configs/constant_presets`](../../configs/constant_presets/README.md#format).


## Fork-timeline

A fork timeline is (preferably) loaded in as a configuration object into a client, as opposed to the constants configuration:
 - We do not allocate or optimize any code based on epoch numbers.
 - When we transition from one fork to the other, it is preferred to stay online.
 - We may decide on an epoch number for a fork based on external events (e.g. Eth1 log event);
    a client should be able to activate a fork dynamically.

The format is described in [`configs/fork_timelines`](../../configs/fork_timelines/README.md#format).

## Config sourcing

The constants configurations are located in:

```
<specs repo root>/configs/constant_presets/<config name>.yaml
```

And copied by CI for testing purposes to:

```
<tests repo root>/configs/constant_presets/<config name>.yaml
```


The fork timelines are located in:

```
<specs repo root>/configs/fork_timelines/<timeline name>.yaml
```

And copied by CI for testing purposes to:

```
<tests repo root>/configs/fork_timelines/<timeline name>.yaml
```

## Test structure

To prevent parsing of hundreds of different YAML files to test a specific test type, 
 or even more specific, just a handler, tests should be structured in the following nested form: 

```
.                             <--- root of eth2.0 tests repository
├── bls                       <--- collection of handler for a specific test-runner, example runner: "bls"
│   ├── verify_msg            <--- collection of test suites for a specific handler, example handler: "verify_msg". If no multiple handlers, use a dummy folder (e.g. "core"), and specify that in the yaml.
│   │   ├── verify_valid.yml    .
│   │   ├── special_cases.yml   . a list of test suites
│   │   ├── domains.yml         .
│   │   ├── invalid.yml         .
│   │   ...                   <--- more suite files (optional)
│   ...                       <--- more handlers
...                           <--- more test types
```


## Note for implementers

The basic pattern for test-suite loading and running is:

Iterate suites for given test-type, or sub-type (e.g. `operations > deposits`):
1. Filter test-suite, options:
    - Config: Load first few lines, load into YAML, and check `config`, either:
        - Pass the suite to the correct compiled target
        - Ignore the suite if running tests as part of a compiled target with different configuration
        - Load the correct configuration for the suite dynamically before running the suite
    - Select by file name
    - Filter for specific suites (e.g. for a specific fork)
2. Load the YAML
    - Optionally translate the data into applicable naming, e.g. `snake_case` to `PascalCase`
3. Iterate through the `test_cases`
4. Ask test-runner to allocate a new test-case (i.e. objectify the test-case, generalize it with a `TestCase` interface) 
    Optionally pass raw test-case data to enable dynamic test-case allocation.
    1. Load test-case data into it.
    2. Make the test-case run.
