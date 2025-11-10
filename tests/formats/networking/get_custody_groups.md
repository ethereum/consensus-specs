# `get_custody_groups` tests

`get_custody_groups` tests provide sanity checks for the correctness of the
`get_custody_groups` helper function.

## Test case format

### `meta.yaml`

```yaml
description: string            -- optional: description of test case, purely for debugging purposes.
node_id: int                   -- argument: the NodeID input.
custody_group_count: int       -- argument: the count of custody groups.
result: list of int            -- output: the list of resulting custody group indices.
```
