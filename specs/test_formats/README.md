# General test format

This document defines the YAML format and structure used for Eth2 testing.

## Table of contents
<!-- TOC -->

* [About](#about)
  + [Test-case formats](#test-case-formats)
* [Glossary](#glossary)
* [Test format philosophy](#test-format-philosophy)
  + [Config design](#config-design)
  + [Test completeness](#test-completeness)
* [Test structure](#test-structure)
  + [`<config name>/`](#--config-name---)
  + [`<fork or phase name>/`](#--fork-or-phase-name---)
  + [`<test runner name>/`](#--test-runner-name---)
  + [`<test handler name>/`](#--test-handler-name---)
  + [`<test suite name>/`](#--test-suite-name---)
  + [`<test case>/`](#--test-case---)
  + [`<output part>`](#--output-part--)
    - [Special output parts](#special-output-parts)
      * [`meta.yaml`](#-metayaml-)
* [Config](#config)
* [Config sourcing](#config-sourcing)
* [Note for implementers](#note-for-implementers)

<!-- /TOC -->

## About

Ethereum 2.0 uses YAML as the format for all cross client tests. This document describes at a high level the general format to which all test files should conform.

### Test-case formats

The particular formats of specific types of tests (test suites) are defined in separate documents.

Test formats:
- [`bls`](./bls/README.md)
- [`epoch_processing`](./epoch_processing/README.md)
- [`genesis`](./genesis/README.md)
- [`operations`](./operations/README.md)
- [`sanity`](./sanity/README.md)
- [`shuffling`](./shuffling/README.md)
- [`ssz_generic`](./ssz_generic/README.md)
- [`ssz_static`](./ssz_static/README.md)
- More formats are planned, see tracking issues for CI/testing


## Glossary

- `generator`: a program that outputs one or more test-cases, each organized into a `config > runner > handler > suite` hierarchy.
- `config`: tests are grouped by configuration used for spec presets. In addition to the standard configurations, 
  `general` may be used as a catch-all for tests not restricted to one configuration. (E.g. BLS).
- `type`: the specialization of one single `generator`. E.g. epoch processing.
- `runner`: where a generator is a *"producer"*, this is the *"consumer"*.
  - A `runner` focuses on *only one* `type`, and each type has *only one* `runner`.
- `handler`: a `runner` may be too limited sometimes, you may have a set of tests with a specific focus that requires a different format.
  To facilitate this, you specify a `handler`: the runner can deal with the format by using the specified handler.
- `suite`: a directory containing test cases that are coherent. Each `suite` under the same `handler` shares the same format.
  This is an organizational/cosmetic hierarchy layer.
- `case`: a test case, a directory in a `suite`. A case can be anything in general, 
  but its format should be well-defined in the documentation corresponding to the `type` (and `handler`).
- `case part`: a test case consists of different files, possibly in different formats, to facilitate the specific test case format better.
  Optionally, a `meta.yaml` is included to declare meta-data for the test, e.g. BLS requirements. 

## Test format philosophy

### Config design

The configuration constant types are:
- Never changing: genesis data.
- Changing, but reliant on old value: e.g. an epoch time may change, but if you want to do the conversion 
  `(genesis data, timestamp) -> epoch number`, you end up needing both constants.
- Changing, but kept around during fork transition: finalization may take a while,
  e.g. an executable has to deal with new deposits and old deposits at the same time. Another example may be economic constants.
- Additional, backwards compatible: new constants are introduced for later phases.
- Changing: there is a very small chance some constant may really be *replaced*. 
  In this off-chance, it is likely better to include it as an additional variable,
  and some clients may simply stop supporting the old one if they do not want to sync from genesis.
  The change of functionality goes through a phase of deprecation of the old constant, and eventually only the new constant is kept around in the config (when old state is not supported anymore).

Based on these types of changes, we model the config as a list of key value pairs,
 that only grows with every fork (they may change in development versions of forks, however; git manages this).
With this approach, configurations are backwards compatible (older clients ignore unknown variables) and easy to maintain.

### Test completeness

Tests should be independent of any sync-data. If one wants to run a test, the input data should be available from the YAML.
The aim is to provide clients with a well-defined scope of work to run a particular set of test-suites.

- Clients that are complete are expected to contribute to testing, seeking for better resources to get conformance with the spec, and other clients.
- Clients that are not complete in functionality can choose to ignore suites that use certain test-runners, or specific handlers of these test-runners.
- Clients that are on older versions can test their work based on older releases of the generated tests, and catch up with newer releases when possible.


## Test structure

```
File path structure:
tests/<config name>/<fork or phase name>/<test runner name>/<test handler name>/<test suite name>/<test case>/<output part>
```

### `<config name>/`

Configs are upper level. Some clients want to run minimal first, and useful for sanity checks during development too.
As a top level dir, it is not duplicated, and the used config can be copied right into this directory as reference.

### `<fork or phase name>/`

This would be: "phase0", "transferparty", "phase1", etc. Each introduces new tests, but does not copy tests that do not change. 
If you like to test phase 1, you run phase 0 tests, with the configuration that includes phase 1 changes. Out of scope for now however.

### `<test runner name>/`

The well known bls/shuffling/ssz_static/operations/epoch_processing/etc. Handlers can change the format, but there is a general target to test.


### `<test handler name>/`

Specialization within category. All suites in here will have the same test case format.
Using a `handler` in a `runner` is optional. A `core` (or other generic) handler may be used if the `runner` does not have different formats.

### `<test suite name>/`

Suites are split up. Suite size (i.e. the amount of tests) does not change the maximum memory requirement, as test cases can be loaded one by one.
This also makes filtered sets of tests fast and easy to load.

### `<test case>/`

Cases are split up too. This enables diffing of parts of the test case, tracking changes per part, while still using LFS. Also enables different formats for some parts.

### `<output part>`

E.g. `pre.yaml`, `deposit.yaml`, `post.yaml`.

Diffing a `pre.yaml` and `post.yaml` provides all the information for testing, good for readability of the change. 
Then the difference between pre and post can be compared to anything that changes the pre state, e.g. `deposit.yaml`

These files allow for custom formats for some parts of the test. E.g. something encoded in SSZ.

Some yaml files have copies, but formatted as raw SSZ bytes: `pre.ssz`, `deposit.ssz`, `post.ssz`.
The yaml files are intended to be deprecated, and clients should shift to ssz inputs for efficiency.
Deprecation will start once a viewer of SSZ test-cases is in place, to maintain a standard of readable test cases.
This also means that some clients can drop legacy YAML -> JSON/other -> SSZ work-arounds.
(These were implemented to support the uint64 YAML, hex strings, etc. Things that were not idiomatic to their language.)

Yaml will not be deprecated for tests that do not use SSZ: e.g. shuffling and BLS tests.
In this case, there is no work around for loading necessary anyway, and the size and efficiency of yaml is acceptable.

#### Special output parts

##### `meta.yaml`

If present (it is optional), the test is enhanced with extra data to describe usage. Specialized data is described in the documentation of the specific test format. 

Common data is documented here:

Some test-case formats share some common key-value pair patterns, and these are documented here:

```
bls_setting: int     -- optional, can have 3 different values:
                            0: (default, applies if key-value pair is absent). Free to choose either BLS ON or OFF.
                                 Tests are generated with valid BLS data in this case,
                                 but there is no change of outcome when running the test if BLS is ON or OFF.
                            1: known as "BLS required" - if the test validity is strictly dependent on BLS being ON
                            2: known as "BLS ignored"  - if the test validity is strictly dependent on BLS being OFF
```


## Config

A configuration is a separate YAML file.
Separation of configuration and tests aims to:
- Prevent duplication of configuration
- Make all tests easy to upgrade (e.g. when a new config constant is introduced)
- Clearly define which constants to use
- Be easily shareable between clients, for cross-client short- or long-lived testnets
- Minimize the amount of different constants permutations to compile as a client.
  *Note*: Some clients prefer compile-time constants and optimizations.
  They should compile for each configuration once, and run the corresponding tests per build target.
- Include constants to coordinate forking with

The format is described in [`/configs`](../../configs/README.md#format).


## Config sourcing

The constants configurations are located in:

```
<specs repo root>/configs/<config name>.yaml
```

And copied by CI for testing purposes to:

```
<tests repo root>/tests/<config name>/<config name>.yaml
```

The first `<config name>` is a directory, which contains exactly all tests that make use of the given config.


## Note for implementers

The basic pattern for test-suite loading and running is:

1. For a specific config, load it first (and only need to do so once),
    then continue with the tests defined in the config folder.
2. Select a fork. Repeat for each fork if running tests for multiple forks.  
3. Select the category and specialization of interest (e.g. `operations > deposits`). Again, repeat for each if running all.
4. Select a test suite. Or repeat for each.
5. Select a test case. Or repeat for each.
6. Load the parts of the case. And `meta.yaml` if present.
7. Run the test, as defined by the test format.

Step 1 may be a step with compile time selection of a configuration, if desired for optimization.
The base requirement is just to use the same set of constants, independent of the loading process. 
