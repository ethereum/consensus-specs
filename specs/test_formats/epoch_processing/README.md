# Epoch processing tests

The different epoch sub-transitions are tested individually with test handlers.
The format is similar to block-processing state-transition tests.
There is no "change" factor however, the transitions are pure functions with just the pre-state as input.
Hence, the format is shared between each test-handler. (See test condition documentation on how to run the tests.)

## Test case format

```yaml
description: string    -- description of test case, purely for debugging purposes
bls_setting: int       -- see general test-format spec.
pre: BeaconState       -- state before running the sub-transition
post: BeaconState      -- state after applying the epoch sub-transition.
```

## Condition

A handler of the `epoch_processing` test-runner should process these cases, 
 calling the corresponding processing implementation (same name, prefixed with `process_`).
This excludes the other parts of the epoch-transition.
The provided pre-state is already transitioned to just before the specific sub-transition of focus of the handler.

Sub-transitions:

- `justification_and_finalization`
- `crosslinks`
- *`justification_and_finalization` - planned testing extension*
- `registry_updates`
- `slashings`
- `final_updates`

The resulting state should match the expected `post` state.
