<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Sanity blocks testing](#sanity-blocks-testing)
  - [Test case format](#test-case-format)
    - [`meta.yaml`](#metayaml)
    - [`pre.ssz_snappy`](#pressz_snappy)
    - [`blocks_<index>.ssz_snappy`](#blocks_indexssz_snappy)
    - [`post.ssz_snappy`](#postssz_snappy)
  - [Condition](#condition)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Sanity blocks testing

Sanity tests to cover a series of one or more blocks being processed, aiming to cover common changes.

## Test case format

### `meta.yaml`

```yaml
description: string            -- Optional. Description of test case, purely for debugging purposes.
bls_setting: int               -- see general test-format spec.
reveal_deadlines_setting: int  -- see general test-format spec.
blocks_count: int              -- the number of blocks processed in this test.
```


### `pre.ssz_snappy`

An SSZ-snappy encoded `BeaconState`, the state before running the block transitions.


### `blocks_<index>.ssz_snappy`

A series of files, with `<index>` in range `[0, blocks_count)`. Blocks need to be processed in order,
 following the main transition function (i.e. process slot and epoch transitions in between blocks as normal)

Each file is a SSZ-snappy encoded `SignedBeaconBlock`.

### `post.ssz_snappy`

An SSZ-snappy encoded `BeaconState`, the state after applying the block transitions.


## Condition

The resulting state should match the expected `post` state, or if the `post` state is left blank,
 the handler should reject the series of blocks as invalid.
