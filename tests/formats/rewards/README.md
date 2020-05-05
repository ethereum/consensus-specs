# Rewards tests

The different rewards deltas sub-functions are testing individually with the test handlers, each returning the related `rewards`/`penalties`.
There is no "change" factor, the rewards/penalties outputs are pure functions with just the pre-state as input.
Hence, the format is shared between each test-handler. (See test condition documentation on how to run the tests.)

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

### `deltas.yaml`

A YAML-encoded `Deltas` representing the rewards and penalties returned by the rewards sub-function

Where `Deltas` is defined as:
```python
class Deltas(Container):
    rewards: List[uint64, VALIDATOR_REGISTRY_LIMIT]
    penalties: List[uint64, VALIDATOR_REGISTRY_LIMIT]
```

Also available as `rewards.ssz`.

## Condition

A handler of the `rewards` test-runner should process these cases, 
 calling the corresponding rewards deltas function (same name in spec).
This excludes all other parts of `process_rewards_and_penalties`

The provided pre-state is ready to be input into the designated handler.

The provided `deltas` should match the return values of the
 handler. Specifically the following must hold true:

```python
    deltas.rewards == handler(state)[0]
    deltas.penalties == handler(state)[1]
```
