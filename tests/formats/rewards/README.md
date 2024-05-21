<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Rewards tests](#rewards-tests)
  - [Test case format](#test-case-format)
    - [`meta.yaml`](#metayaml)
    - [`pre.ssz_snappy`](#pressz_snappy)
    - [`source_deltas.ssz_snappy`](#source_deltasssz_snappy)
    - [`target_deltas.ssz_snappy`](#target_deltasssz_snappy)
    - [`head_deltas.ssz_snappy`](#head_deltasssz_snappy)
    - [`inclusion_delay_deltas.ssz_snappy`](#inclusion_delay_deltasssz_snappy)
    - [`inactivity_penalty_deltas.ssz_snappy`](#inactivity_penalty_deltasssz_snappy)
  - [Condition](#condition)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Rewards tests

All rewards deltas sub-functions are tested for each test case.
There is no "change" factor, the rewards/penalties outputs are pure functions with just the pre-state as input.
(See test condition documentation on how to run the tests.)

`Deltas` is defined as:
```python
class Deltas(Container):
    rewards: List[Gwei, VALIDATOR_REGISTRY_LIMIT]
    penalties: List[Gwei, VALIDATOR_REGISTRY_LIMIT]
```

## Test case format

### `meta.yaml`

```yaml
description: string    -- Optional description of test case, purely for debugging purposes.
                          Tests should use the directory name of the test case as identifier, not the description.
```

_Note_: No signature verification happens within rewards sub-functions. These
 tests can safely be run with or without BLS enabled.

### `pre.ssz_snappy`

An SSZ-snappy encoded `BeaconState`, the state before running the rewards sub-function.

### `source_deltas.ssz_snappy`

An SSZ-snappy encoded `Deltas` representing the rewards and penalties returned by the rewards the `get_source_deltas` function

### `target_deltas.ssz_snappy`

An SSZ-snappy encoded `Deltas` representing the rewards and penalties returned by the rewards the `get_target_deltas` function

### `head_deltas.ssz_snappy`

An SSZ-snappy encoded `Deltas` representing the rewards and penalties returned by the rewards the `get_head_deltas` function

### `inclusion_delay_deltas.ssz_snappy`

An SSZ-snappy encoded `Deltas` representing the rewards and penalties returned by the rewards the `get_inclusion_delay_deltas` function

### `inactivity_penalty_deltas.ssz_snappy`

An SSZ-snappy encoded `Deltas` representing the rewards and penalties returned by the rewards the `get_inactivity_penalty_deltas` function

## Condition

A handler of the `rewards` test-runner should process these cases, 
 calling the corresponding rewards deltas function for each set of deltas.

The provided pre-state is ready to be input into each rewards deltas function.

The provided `deltas` should match the return values of the
 deltas function. Specifically the following must hold true for each set of deltas:

```python
    deltas.rewards == deltas_function(state)[0]
    deltas.penalties == deltas_function(state)[1]
```
