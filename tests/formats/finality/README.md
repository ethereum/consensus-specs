# Finality tests

The aim of the tests for the finality rules.

- `finality`: transitions triggered by one or more blocks.

## Test case format

### `meta.yaml`

```yaml
description: string    -- Optional. Description of test case, purely for debugging purposes.
bls_setting: int       -- see general test-format spec.
blocks_count: int      -- the number of blocks processed in this test.
```

### `pre.ssz_snappy`

An SSZ-snappy encoded `BeaconState`, the state before running the block
transitions.

Also available as `pre.ssz_snappy`.

### `blocks_<index>.yaml`

A series of files, with `<index>` in range `[0, blocks_count)`. Blocks need to
be processed in order, following the main transition function (i.e. process slot
and epoch transitions in between blocks as normal)

Each file is a YAML-encoded `SignedBeaconBlock`.

Each block is also available as `blocks_<index>.ssz_snappy`

### `post.ssz_snappy`

An SSZ-snappy encoded `BeaconState`, the state after applying the block
transitions.

## Condition

The resulting state should match the expected `post` state, or if the `post`
state is left blank, the handler should reject the series of blocks as invalid.
