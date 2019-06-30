# Genesis validity testing

Tests if a genesis state is valid, i.e. if it counts as trigger to launch.

## Test case format

```yaml
description: string    -- description of test case, purely for debugging purposes
bls_setting: int       -- see general test-format spec.
genesis: BeaconState   -- state to validate.
is_valid: bool         -- true if the genesis state is deemed valid as to launch with, false otherwise.
```

To process the data, call `is_valid_genesis_state(genesis)`.


## Condition

The result of calling `is_valid_genesis_state(genesis)` should match the expected `is_valid` boolean.
