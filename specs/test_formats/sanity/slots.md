# Sanity slots testing

Sanity tests to cover a series of one or more empty-slot transitions being processed, aiming to cover common changes.

## Test case format

```yaml
description: string    -- description of test case, purely for debugging purposes
bls_setting: int       -- see general test-format spec.
pre: BeaconState       -- state before running through the transitions.
slots: N               -- amount of slots to process, N being a positive number.
post: BeaconState      -- state after applying all the transitions.
```

The transition with pure time, no blocks, is known as `process_slots(state, slot)` in the spec.
This runs state-caching (pure slot transition) and epoch processing (every E slots).

To process the data, call `process_slots(pre, pre.slot + N)`.

## Condition

The resulting state should match the expected `post` state.
