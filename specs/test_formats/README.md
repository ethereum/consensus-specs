# General test format

This document defines the YAML format and structure used for ETH 2.0 testing.

## ToC

* [About](#about)
* [Glossary](#glossary)
* [Test format philosophy](#test-format-philosophy)
* [Test Suite](#test-suite)
* [Config](#config)
* [Fork-timeline](#fork-timeline)
* [Config sourcing](#config-sourcing)
* [Test structure](#test-structure)

## About

Ethereum 2.0 uses YAML as the format for all cross client tests. This document describes at a high level the general format to which all test files should conform.

The particular formats of specific types of tests (test suites) are defined in separate documents.

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
- Never changing: genesis data
- Changing, but reliant on old value: e.g. an epoch time may change, but if you want to do the conversion 
  `(genesis data, timestamp) -> epoch number` you end up needing both constants.
- Changing, but kept around during fork transition: finalization may take a while,
  e.g. an executable has to deal with new deposits and old deposits at the same time. Another example may be economic constants.
- Additional, back-wards compatible: new constants are introduced for later phases
- Changing: there is a very small chance some constant may really be *replaced*. 
  In this off-chance, it is likely better to include it as an additional variable,
  and some clients may simply stop supporting the old one, if they do not want to sync from genesis.

Based on these types of changes, we model the config as a list of key value pairs,
 that only grows with every fork (they may change in development versions of forks however, git manages this).
With this approach, configurations are backwards compatible (older clients ignore unknown variables), and easy to maintain.

### Fork config design

There are two types of fork-data:
1) timeline: when does a fork take place?
2) coverage: what forks are covered by a test?

The first is neat to have as a separate form: we prevent duplication, and can run with different presets
 (e.g. fork timeline for a minimal local test, for a public testnet, or for mainnet)

The second is still somewhat ambiguous: some tests may want cover multiple forks, and can do so in different ways:
- run one test, transitioning from one to the other
- run the same test for both
- run a test for every transition from one fork to the other
- more

There is a common factor here however: the options are exclusive, and give a clear idea on what test suites need to be ran to cover testing for a specific fork.
The way this list of forks is interpreted, is up to the test-runner:
State-transition test suites may want to just declare forks that are being covered in the test suite,
 whereas shuffling test suites may want to declare a list of forks to test the shuffling algorithm for individually.

Test-formats specify the following `forks` interpretation rules:

- `collective`: the test suite applies to all specified forks, and only needs to run once
- `individual`: the test suite should be ran against every fork
- more types may be specified with future test types.

### Test completeness

Tests should be independent of any sync-data. If one wants to run a test, the input data should be available from the YAML.
The aim is to provide clients with a well-defined scope of work to run a particular set of test-suites.

- Clients that are complete are expected to contribute to testing, seeking for better resources to get conformance with the spec, and other clients.
- Clients that are not complete in functionality can choose to ignore suites that use certain test-runners, or specific handlers of these test-runners.
- Clients that are on older versions can test there work based on older releases of the generated tests, and catch up with newer releases when possible.

## Test Suite

```
title: <string, short, one line> -- Display name for the test suite
summary: <string, average, 1-3 lines> -- Summarizes the test suite
forks_timeline: <string, reference to a fork definition file, without extension> -- Used to determine the forking timeline
forks: <list of strings> -- Runner decides what to do: run for each fork, or run for all at once, each fork transition, etc.
  - ... <string, first the fork name, then the spec version>
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
- Shareable between clients, for cross-client short or long lived testnets
- Minimize the amounts of different constants permutations to compile as a client.
  Note: Some clients prefer compile-time constants and optimizations.
  They should compile for each configuration once, and run the corresponding tests per build target.

The format is described in `configs/constant_presets`.


## Fork-timeline

A fork timeline is (preferably) loaded in as a configuration object into a client, as opposed to the constants configuration:
 - we do not allocate or optimize any code based on epoch numbers
 - when we transition from one fork to the other, it is preferred to stay online.
 - we may decide on an epoch number for a fork based on external events (e.g. Eth1 log event),
    a client should be able to activate a fork dynamically.

The format is described in `configs/fork_timelines`.

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
.                        <--- root of eth2.0 tests repository
├── bls                  <--- collection of handler for a specific test-runner, example runner: "bls"
│   ├── signing          <--- collection of test suites for a specific handler, example handler: "signing". If no multiple handlers, use a dummy folder (e.g. "main"), and specify that in the yaml.
│   │   ├── sign_msg.yml <--- an entry list of test suites
│   │   ...              <--- more suite files (optional)
│   ...                  <--- more handlers
...                      <--- more test types
```
