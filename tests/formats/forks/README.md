<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Forks](#forks)
  - [Test case format](#test-case-format)
    - [`meta.yaml`](#metayaml)
      - [Fork strings](#fork-strings)
    - [`pre.ssz_snappy`](#pressz_snappy)
    - [`post.ssz_snappy`](#postssz_snappy)
  - [Processing](#processing)
  - [Condition](#condition)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Forks

The aim of the fork tests is to ensure that a pre-fork state can be transformed
 into a valid post-fork state, utilizing the `upgrade` function found in the relevant `fork.md` spec.

There is only one handler: `fork`. Each fork (after genesis) is handled with the same format,
 and the particular fork boundary being tested is noted in `meta.yaml`.

## Test case format

### `meta.yaml`

A yaml file to signify which fork boundary is being tested.

```yaml
fork: str    -- Fork being transitioned to
```

#### Fork strings

Key of valid `fork` strings that might be found in `meta.yaml`

| String ID | Pre-fork | Post-fork | Function |
| - | - | - | - |
| `altair` | Phase 0 | Altair | `upgrade_to_altair` |
| `bellatrix` | Altair | Bellatrix | `upgrade_to_bellatrix` |

### `pre.ssz_snappy`

An SSZ-snappy encoded `BeaconState`, the state before running the fork transition.

### `post.ssz_snappy`

An SSZ-snappy encoded `BeaconState`, the state after applying the fork transition.

*Note*: This type is the `BeaconState` after the fork and is *not* the same type as `pre`.

## Processing

To process this test, pass `pre` into the upgrade function defined by the `fork` in `meta.yaml`.

## Condition

The resulting state should match the expected `post`.
