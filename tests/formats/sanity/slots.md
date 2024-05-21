<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Sanity slots testing](#sanity-slots-testing)
  - [Test case format](#test-case-format)
    - [`meta.yaml`](#metayaml)
    - [`pre.ssz_snappy`](#pressz_snappy)
    - [`slots.yaml`](#slotsyaml)
    - [`post.ssz_snappy`](#postssz_snappy)
    - [Processing](#processing)
  - [Condition](#condition)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Sanity slots testing

Sanity tests to cover a series of one or more empty-slot transitions being processed, aiming to cover common changes.

## Test case format

### `meta.yaml`

```yaml
description: string    -- Optional. Description of test case, purely for debugging purposes.
bls_setting: int       -- see general test-format spec.
```


### `pre.ssz_snappy`

An SSZ-snappy `BeaconState`, the state before running the transitions.

Also available as `pre.ssz_snappy`.


### `slots.yaml`

An integer. The amount of slots to process (i.e. the difference in slots between pre and post), always a positive number.

### `post.ssz_snappy`

An SSZ-snappy `BeaconState`, the state after applying the transitions.

Also available as `post.ssz_snappy`.


### Processing

The transition with pure time, no blocks, is known as `process_slots(state, slot)` in the spec.
This runs state-caching (pure slot transition) and epoch processing (every E slots).

To process the data, call `process_slots(pre, pre.slot + N)`.

## Condition

The resulting state should match the expected `post` state.
