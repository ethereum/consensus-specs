# Transition testing

Transition tests to cover processing the chain across a fork boundary.

Each test case contains a `post_fork` key in the `meta.yaml` that indicates the
target fork which also fixes the fork the test begins in.

Clients should assume forks happen sequentially in the following manner:

0. `phase0`
1. `altair`
2. `bellatrix`
3. `capella`
4. `deneb`

For example, if a test case has `post_fork` of `altair`, the test consumer
should assume the test begins in `phase0` and use that specification to process
the initial state and any blocks up until the fork epoch. After the fork
happens, the test consumer should use the specification according to the
`altair` fork to process the remaining data.

## Test case format

### `meta.yaml`

```yaml
post_fork: string              -- String name of the spec after the fork.
fork_epoch: int                -- The epoch at which the fork takes place.
fork_block: int                -- Optional. The `<index>` of the last block on the initial fork.
blocks_count: int              -- The number of blocks processed in this test.
```

*Note*: There may be a fork transition function to run at the `fork_epoch`.
Refer to the specs for the relevant fork for further details.

### `pre.ssz_snappy`

A SSZ-snappy encoded `BeaconState` according to the specification of the initial
fork, the state before running the block transitions.

### `blocks_<index>.ssz_snappy`

A series of files, with `<index>` in range `[0, blocks_count)`. Blocks must be
processed in order, following the main transition function (i.e. process slot
and epoch transitions in between blocks as normal).

Blocks are encoded as `SignedBeaconBlock`s from the relevant spec version as
indicated by the `post_fork` and `fork_block` data in the `meta.yaml`.

As blocks span fork boundaries, a `fork_block` number is given in the
`meta.yaml` to help resolve which blocks belong to which fork.

The `fork_block` is the index in the test data of the **last** block of the
**initial** fork.

To demonstrate, the following diagram shows slots with `_` and blocks in those
slots as `x`. The fork happens at the epoch delineated by the `|`.

```
x   x     x x
_ _ _ _ | _ _ _ _
```

The `blocks_count` value in the `meta.yaml` in this case is `4` where the
`fork_block` value in the `meta.yaml` is `1`. If this particular example were
testing the fork from Phase 0 to Altair, blocks with indices `0, 1` represent
`SignedBeaconBlock`s defined in the Phase 0 spec and blocks with indices `2, 3`
represent `SignedBeaconBlock`s defined in the Altair spec.

*Note*: If `fork_block` is missing, then all block data should be interpreted as
belonging to the post fork.

### `post.ssz_snappy`

A SSZ-snappy encoded `BeaconState` according to the specification of the post
fork, the state after running the block transitions.

## Condition

The resulting state should match the expected `post` state.
