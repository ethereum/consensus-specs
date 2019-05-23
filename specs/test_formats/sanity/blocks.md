# Sanity blocks testing

Sanity tests to cover a series of one or more blocks being processed, aiming to cover common changes.

## Test case format

```yaml
description: string    -- description of test case, purely for debugging purposes
bls_required: bool     -- optional, true if the test validity is strictly dependent on BLS being ON. False otherwise.
bls_ignored: bool      -- optional, true if the test validity is strictly dependent on BLS being OFF. False otherwise.
pre: BeaconState       -- state before running through the transitions triggered by the blocks.
blocks: [BeaconBlock]  -- blocks to process, in given order, following the main transition function (i.e. process slot and epoch transitions in between blocks as normal)
post: BeaconState      -- state after applying all the transitions triggered by the blocks.
```

## Condition

The resulting state should match the expected `post` state, or if the `post` state is left blank,
 the handler should reject the series of blocks as invalid.
