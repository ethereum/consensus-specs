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

### `pre_epoch.ssz_snappy`

An SSZ-snappy encoded `BeaconState`, the state before running the epoch transition.

### `post_epoch.ssz_snappy`

An SSZ-snappy encoded `BeaconState`, the state after applying the epoch transition. No value if the transition processing is aborted.

## Condition

A handler of the `epoch_processing` test-runner should process these cases,
 calling the corresponding processing implementation (same name, prefixed with `process_`).
This excludes the other parts of the epoch-transition.
The provided pre-state is already transitioned to just before the specific sub-transition of focus of the handler.

Sub-transitions:

- `eth1_data_reset` (>=Phase0)
- `historical_roots_update` (>=Phase0,<=Bellatrix)
- `justification_and_finalization` (>=Phase0)
- `participation_record_updates` (==Phase0)
- `randao_mixes_reset` (>=Phase0)
- `registry_updates` (>=Phase0)
- `rewards_and_penalties` (>=Phase0)
- `slashings_reset` (>=Phase0)
- `slashings` (>=Phase0)
- `inactivity_updates` (>=Altair)
- `participation_flag_updates` (>=Altair)
- `sync_committee_updates` (>=Altair)
- `historical_summaries_update` (>=Capella)
- `effective_balance_updates` (>=Electra)
- `pending_consolidations` (>=Electra)
- `pending_deposits` (>=Electra)

The resulting state should match the expected `post` state.

## Condition (alternative)

Instead of having a different handler for each sub-transition, a single handler for all cases should load `pre_full` state, call `process_epoch` and then assert that the result state should match `post_full` state.

This has the advantages:

- Less code to maintain for the epoch processing handler.
- Works with single pass epoch processing.
- Can detect bugs related to data dependencies between different sub-transitions.

As a disadvantage this condition takes more resources to compute, but just a constant amount per test vector.
