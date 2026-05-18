# `LightClientUpdate` ranking tests

This series of tests provides reference test vectors for validating that
`LightClientUpdate` instances are ranked in a canonical order.

## Test case format

### `meta.yaml`

```yaml
updates_count: int  -- integer, decimal
```

### `updates_<index>.ssz_snappy`

A series of files, with `<index>` in range `[0, updates_count)`, ordered by
descending precedence according to `is_better_update` (best update at index 0).

Each file is a SSZ-snappy encoded `LightClientUpdate`.

## Condition

A test-runner should load the provided `update` objects and verify that the
local implementation ranks them in the same order. Note that the `update`
objects are not restricted to a single sync committee period for the scope of
this test.
