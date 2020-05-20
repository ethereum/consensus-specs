# Epoch processing tests

The different epoch sub-transitions are tested individually with test handlers.
The format is similar to block-processing state-transition tests.
There is no "change" factor however, the transitions are pure functions with just the pre-state as input.
Hence, the format is shared between each test-handler. (See test condition documentation on how to run the tests.)

## Test case format

### `meta.yaml`

```yaml
description: string    -- Optional description of test case, purely for debugging purposes.
                          Tests should use the directory name of the test case as identifier, not the description.
bls_setting: int       -- see general test-format spec.
```

### `pre.yaml`

A YAML-encoded `BeaconState`, the state before running the epoch sub-transition.

Also available as `pre.ssz`.


### `post.yaml`

A YAML-encoded `BeaconState`, the state after applying the epoch sub-transition.

Also available as `post.ssz`.

## Condition

A handler of the `epoch_processing` test-runner should process these cases, 
 calling the corresponding processing implementation (same name, prefixed with `process_`).
This excludes the other parts of the epoch-transition.
The provided pre-state is already transitioned to just before the specific sub-transition of focus of the handler.

Sub-transitions:

- `justification_and_finalization`
- `rewards_and_penalties` (limited to `minimal` config)
- `registry_updates`
- `slashings`
- `final_updates`

The resulting state should match the expected `post` state.
