# Transition testing

Transition tests to cover processing the chain across a fork boundary.

Each test case contains a `post_fork` key in the `meta.yaml` that indicates the target fork which also fixes the fork the test begins in.

Clients should assume forks happen sequentially in the following manner:

0. `phase0`
1. `altair`

For example, if a test case has `post_fork` of `altair`, the test consumer should assume the test begins in `phase0` and use that specification to process the initial state and any blocks up until the fork epoch. After the fork happens, the test consumer should use the specification according to the `altair` fork to process the remaining data.

## Encoding notes

This test type contains objects that span fork boundaries.
In general, it may not be clear which objects belong to which fork so each
object is prefixed with a SSZ `boolean` to indicate if the object belongs to the post fork or if it belongs to the initial fork.
This "flagged" data should be used to select the appropriate version of the spec when interpreting the enclosed object.

```python
class FlaggedContainer(Container):
    flag: boolean
    obj: Container
```

If `flag` is `False`, then the `obj` belongs to the **initial** fork.
If `flag` is `True`, then the `obj` belongs to the **post** fork.

Unless stated otherwise, all references to spec types below refer to SSZ-snappy
encoded data `obj` with the relevant `flag` set:
`FlaggedContainer(flag=flag, obj=obj)`.

For example, when testing the fork from Phase 0 to Altair, an Altair block is given
as the encoding of `FlaggedContainer(flag=True, obj=SignedBeaconBlock())` where
`SignedBeaconBlock` is the type defined in the Altair spec.

## Test case format

### `meta.yaml`

```yaml
post_fork: string              -- String name of the spec after the fork.
fork_epoch: int                -- The epoch at which the fork takes place.
blocks_count: int              -- The number of blocks processed in this test.
```

*Note*: There may be a fork transition function to run at the `fork_epoch`. Refer to the specs for the relevant fork for further details.

### `pre.ssz_snappy`

A SSZ-snappy encoded `BeaconState` according to the specification of the initial fork, the state before running the block transitions.

*NOTE*: This object is _not_ "flagged" as it is assumed to always belong to the post fork.

### `blocks_<index>.ssz_snappy`

A series of files, with `<index>` in range `[0, blocks_count)`.
Blocks must be processed in order, following the main transition function
(i.e. process slot and epoch transitions in between blocks as normal).

Blocks are encoded as `SignedBeaconBlock`s from the relevant spec version indicated by flag data as described in the `Encoding notes`.

### `post.ssz_snappy`

A SSZ-snappy encoded `BeaconState` according to the specification of the post fork, the state after running the block transitions.

*NOTE*: This object is _not_ "flagged" as it is assumed to always belong to the post fork.

## Condition

The resulting state should match the expected `post` state.
