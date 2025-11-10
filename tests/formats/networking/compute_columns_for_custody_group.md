# `compute_columns_for_custody_group` tests

`compute_columns_for_custody_group` tests provide sanity checks for the
correctness of the `compute_columns_for_custody_group` helper function.

## Test case format

### `meta.yaml`

```yaml
description: string            -- optional: description of test case, purely for debugging purposes.
custody_group: int             -- argument: the custody group index.
result: list of int            -- output: the list of resulting column indices.
```
