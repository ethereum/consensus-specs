# Rewards tests

The different rewards deltas sub-functions are testing individually with the test handlers, each returning the related `rewards`/`penalties`.
There is no "change" factor, the rewards/penalties outputs are pure functions with just the pre-state as input.
Hence, the format is shared between each test-handler. (See test condition documentation on how to run the tests.)


## Test case format

### `meta.yaml`

```yaml
description: string    -- Optional description of test case, purely for debugging purposes.
                          Tests should use the directory name of the test case as identifier, not the description.
bls_setting: int       -- see general test-format spec.
```

### `pre.yaml`

A YAML-encoded `BeaconState`, the state before running the rewards sub-function.

Also available as `pre.ssz`.


### `rewards.yaml`

A YAML-encoded list of integers representing the 0th item in the return value (i.e. the rewards deltas)

### `penalties.yaml`

A YAML-encoded list of integers representing the 1st item in the return value (i.e. the penalties deltas)

## Condition

A handler of the `rewards` test-runner should process these cases, 
 calling the corresponding rewards deltas function (same name in spec).
This excludes all other parts of `process_rewards_and_penalties`

The provided pre-state is ready to be input into the designated handler.

The resulting `rewards`/`penalties` should match the return values of the
handler. Specifically the following must hold true:

```python
    rewards == handler(state)[0]
    penalties == handler(state)[1]
```
