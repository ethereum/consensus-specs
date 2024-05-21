<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`LightClientUpdate` ranking tests](#lightclientupdate-ranking-tests)
  - [Test case format](#test-case-format)
    - [`meta.yaml`](#metayaml)
    - [`updates_<index>.ssz_snappy`](#updates_indexssz_snappy)
  - [Condition](#condition)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# `LightClientUpdate` ranking tests

This series of tests provides reference test vectors for validating that `LightClientUpdate` instances are ranked in a canonical order.

## Test case format

### `meta.yaml`

```yaml
updates_count: int  -- integer, decimal
```

### `updates_<index>.ssz_snappy`

A series of files, with `<index>` in range `[0, updates_count)`, ordered by descending precedence according to `is_better_update` (best update at index 0).

Each file is a SSZ-snappy encoded `LightClientUpdate`.

## Condition

A test-runner should load the provided `update` objects and verify that the local implementation ranks them in the same order. Note that the `update` objects are not restricted to a single sync committee period for the scope of this test.
