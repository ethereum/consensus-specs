# `get_custody_columns` tests

`get_custody_columns` tests provide sanity check of the correctness of `get_custody_columns` helper.

## Test case format

### `meta.yaml`

```yaml
description: string            -- optional: description of test case, purely for debugging purposes.
node_id: int                   -- argument: the NodeID input.
custody_subnet_count: int      -- argument: the count of custody subnets.
result: list of int            -- output: the list of resulting column indices.
```
