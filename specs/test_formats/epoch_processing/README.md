# Epoch processing tests

The different epoch sub-transitions are tested individually with test handlers.
The format is similar to block-processing state-transition tests.
There is no "change" factor however, the transitions are pure functions with just the pre-state as input.
Hence, the format is shared between each test-handler. (See test condition documentation on how to run the tests.)

## Test case format

```yaml
description: string    -- description of test case, purely for debugging purposes
bls_required: bool     -- optional, true if the test validity is strictly dependent on BLS being ON. False otherwise.
bls_ignored: bool      -- optional, true if the test validity is strictly dependent on BLS being OFF. False otherwise.
pre: BeaconState       -- state before running the sub-transition
post: BeaconState      -- state after applying the epoch sub-transition.
```

Note: if both `bls_required` and `bls_ignored` are false (or simply not included),
 then the test consumer can freely choose to run with BLS ON or OFF.
One may choose for OFF for performance reasons during repeated testing. Otherwise it is recommended to run with BLS ON.

## Condition

A handler of the `epoch_processing` test-runner should process these cases, 
 calling the corresponding processing implementation.

Sub-transitions:

| *`sub-transition-name`* | *`processing call`*               |
|-------------------------|-----------------------------------|
| `crosslinks`            | `process_crosslinks(state)`       |
| `registry_updates`      | `process_registry_updates(state)` |

The resulting state should match the expected `post` state.
