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

### `pre.ssz_snappy`

An SSZ-snappy encoded `BeaconState`, the state before running the epoch sub-transition.

### `post.ssz_snappy`

An SSZ-snappy encoded `BeaconState`, the state after applying the epoch sub-transition. No value if the sub-transition processing is aborted.

## Condition

A handler of the `epoch_processing` test-runner should process these cases, 
 calling the corresponding processing implementation (same name, prefixed with `process_`).
This excludes the other parts of the epoch-transition.
The provided pre-state is already transitioned to just before the specific sub-transition of focus of the handler.

Sub-transitions:

- `justification_and_finalization`
- `inactivity_updates` (Altair)
- `rewards_and_penalties`
- `registry_updates`
- `slashings`
- `eth1_data_reset`
- `effective_balance_updates`
- `slashings_reset`
- `randao_mixes_reset`
- `historical_roots_update`
- `participation_record_updates` (Phase 0 only)
- `participation_flag_updates` (Altair)
- `sync_committee_updates` (Altair)

The resulting state should match the expected `post` state.
