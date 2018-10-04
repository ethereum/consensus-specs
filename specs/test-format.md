# General test format

This document defines the general YAML format to which all tests should conform.

## ToC

* [About](#about)
* [YAML Fields](#yaml-fields)
* [Example test suite](#example-test-suite)

## About
Ethereum 2.0 uses YAML as the format for all cross client tests. This document describes at a high level the general format to which all test files should conform.

The particular formats of specific types of tests (test suites) are defined in separate documents.

## YAML fields
`title` _(required)_

`summary` _(optional)_

`test_suite` _(required)_ string defining the test suite to which the test cases conform

`fork` _(required)_ production release versioning

`version` _(required)_ version for particular test document

`test_cases` _(required)_ list of test cases each of which is formatted to conform to the `test_case` standard defined by `test_suite`. All test cases have optional `name` and `description` string fields.

## Example test suite
`shuffle` is a test suite that defines test cases for the `shuffle()` helper function defined in the `beacon-chain` spec.

Test cases that conform to the `shuffle` test suite have the following fields:

* `input` _(required)_ the list of items passed into `shuffle()`
* `output` _(required)_ the expected list returned by `shuffle()`
* `seed` _(required)_ the seed of entropy passed into `shuffle()`

As for all test cases, `name` and `description` are optional string fields.

The following is a sample YAML document for the `shuffle` test suite:

```yaml
title: Shuffling Algorithm Tests
summary: Test vectors for shuffling a list based upon a seed using `shuffle`
test_suite: shuffle
fork: tchaikovsky
version: 1.0

test_cases:
- input: []
  output: []
  seed: !!binary ""
- name: boring_list
  description: List with a single element, 0
  input: [0]
  output: [0]
  seed: !!binary ""
- input: [255]
  output: [255]
  seed: !!binary ""
- input: [4, 6, 2, 6, 1, 4, 6, 2, 1, 5]
  output: [1, 6, 4, 1, 6, 6, 2, 2, 4, 5]
  seed: !!binary ""
- input: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
  output: [4, 7, 10, 13, 3, 1, 2, 9, 12, 6, 11, 8, 5]
  seed: !!binary ""
- input: [65, 6, 2, 6, 1, 4, 6, 2, 1, 5]
  output: [6, 65, 2, 5, 4, 2, 6, 6, 1, 1]
  seed: !!binary |
    JlAYJ5H2j8g7PLiPHZI/rTS1uAvKiieOrifPN6Moso0=
```