# Confirmation rule tests

The aim of the confirmation rule tests is to provide test coverage of the various components of the confirmation rule.

## Test case format

### `meta.yaml`

```yaml
description: string    -- Optional. Description of test case, purely for debugging purposes.
bls_setting: int       -- see general test-format spec.
```

### `anchor_state.ssz_snappy`

An SSZ-snappy encoded `BeaconState`, the state to initialize store with `get_forkchoice_store(anchor_state: BeaconState, anchor_block: BeaconBlock)` helper.

### `anchor_block.ssz_snappy`

An SSZ-snappy encoded `BeaconBlock`, the block to initialize store with `get_forkchoice_store(anchor_state: BeaconState, anchor_block: BeaconBlock)` helper.

### `steps.yaml`

The steps to execute in sequence. There may be multiple items of the following types:

#### `on_tick` execution step

The parameter that is required for executing `on_tick(store, time)`.

```yaml
{
    tick: int       -- to execute `on_tick(store, time)`.
}
```

After this step, the `store` object may have been updated.

#### `on_attestation` execution step

The parameter that is required for executing `on_attestation(store, attestation)`.

```yaml
{
    attestation: string  -- the name of the `attestation_<32-byte-root>.ssz_snappy` file.
                            To execute `on_attestation(store, attestation)` with the given attestation.
}
```
The file is located in the same folder (see below).

After this step, the `store` object may have been updated.

#### `on_block` execution step

The parameter that is required for executing `on_block(store, block)`.

```yaml
{
    block: string  -- the name of the `block_<32-byte-root>.ssz_snappy` file.
                      To execute `on_block(store, block)` with the given attestation.
}  
```
The file is located in the same folder (see below).

After this step, the `store` object may have been updated.

#### `on_attester_slashing` execution step

The parameter that is required for executing `on_attester_slashing(store, attester_slashing)`.

```yaml
{
    attester_slashing: string  -- the name of the `attester_slashing_<32-byte-root>.ssz_snappy` file.
                            To execute `on_attester_slashing(store, attester_slashing)` with the given attester slashing.
}
```

The file is located in the same folder (see below).

After this step, the `store` object may have been updated.

#### Checks step

The checks to verify the execution of the confirmation rule algorithm

```yaml
    check_is_confirmed: {
        result: bool,          -- return value of `is_confirmed(store, block_root)`
        block_root: string     -- block to execute is_confirmed on
    }
```

## Condition

1. Deserialize `anchor_state.ssz_snappy` and `anchor_block.ssz_snappy` to initialize the local store object by with `get_forkchoice_store(anchor_state, anchor_block)` helper.
2. Iterate sequentially through `steps.yaml`
    - For each execution, look up the corresponding ssz_snappy file. Execute the corresponding helper function on the current store.
        - For the `on_block` execution step: if `len(block.message.body.attestations) > 0`, execute each attestation with `on_attestation(store, attestation)` after executing `on_block(store, block)`.
    - For each `checks` step, the assertions on the values returned by the confirmation rule algorithm must be satisfied.
