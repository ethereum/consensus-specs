# Genesis validity testing

Tests if a genesis state is valid, i.e. if it counts as trigger to launch.

## Test case format

### `meta.yaml`

A yaml file to help read the deposit count:

```yaml
description: string    -- Optional. Description of test case, purely for debugging purposes.
```

### `genesis.ssz_snappy`

An SSZ-snappy encoded `BeaconState`, the state to validate as genesis candidate.

### `is_valid.yaml`

A boolean, true if the genesis state is deemed valid as to launch with, false
otherwise.

## Processing

To process the data, call `is_valid_genesis_state(genesis)`.

## Condition

The result of calling `is_valid_genesis_state(genesis)` should match the
expected `is_valid` boolean.
