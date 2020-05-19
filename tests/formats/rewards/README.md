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

### `pre.yaml`

A YAML-encoded `BeaconState`, the state before running the rewards sub-function.

Also available as `pre.ssz`.

### `source_deltas.yaml`

A YAML-encoded `Deltas` representing the rewards and penalties returned by the rewards the `get_source_deltas` function

Also available as `source_deltas.ssz`.

### `target_deltas.yaml`

A YAML-encoded `Deltas` representing the rewards and penalties returned by the rewards the `get_target_deltas` function

Also available as `target_deltas.ssz`.

### `head_deltas.yaml`

A YAML-encoded `Deltas` representing the rewards and penalties returned by the rewards the `get_head_deltas` function

Also available as `head_deltas.ssz`.

### `inclusion_delay_deltas.yaml`

A YAML-encoded `Deltas` representing the rewards and penalties returned by the rewards the `get_inclusion_delay_deltas` function

Also available as `inclusion_delay_deltas.ssz`.

### `inactivity_penalty_deltas.yaml`

A YAML-encoded `Deltas` representing the rewards and penalties returned by the rewards the `get_inactivity_penalty_deltas` function

Also available as `inactivity_penalty_deltas.ssz`.

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
