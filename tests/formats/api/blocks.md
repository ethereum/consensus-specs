# Beacon API testing

Sanity tests to cover a series of one or more blocks being processed, aiming to cover common changes.

## Test case format

### `hive.yaml`

TBD.


### `meta.yaml`

```yaml
description: string            -- Optional. Description of test case, purely for debugging purposes.
bls_setting: int               -- see general test-format spec.
reveal_deadlines_setting: int  -- see general test-format spec.
blocks_count: int              -- the number of blocks processed in this test.
```


### `genesis.ssz_snappy`

An SSZ-snappy encoded `BeaconState` of the Beacon chain genesis.


### `blocks_<index>.ssz_snappy`

A series of files, with `<index>` in range `[0, blocks_count)`. Blocks need to be processed in order,
 following the main transition function (i.e. process slot and epoch transitions in between blocks as normal)

Each file is a SSZ-snappy encoded `SignedBeaconBlock`.

### `post.ssz_snappy`

An SSZ-snappy encoded `BeaconState`, the state after applying the block transitions.


## Condition

The beacon API verifications have to match the expected result after the post-state has been applied.
