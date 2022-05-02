# Light client sync tests

This series of tests provides reference test vectors for validating that a light client implementing the sync protocol can sync to the latest block header.

## Test case format

### `meta.yaml`

```yaml
genesis_validators_root: Bytes32  -- string, hex encoded, with 0x prefix
trusted_block_root: Bytes32       -- string, hex encoded, with 0x prefix
```

### `bootstrap.ssz_snappy`

An SSZ-snappy encoded `bootstrap` object of type `LightClientBootstrap` to initialize a local `store` object of type `LightClientStore` using `initialize_light_client_store(trusted_block_rooot, bootstrap)`.

### `steps.yaml`

The steps to execute in sequence. There may be multiple items of the following types:

#### `process_slot` execution step

The function `process_slot_for_light_client_store(store, current_slot)`
should be executed with the specified parameters:

```yaml
{
    current_slot: int  -- integer, decimal
}
```

After this step, the `store` object may have been updated.

#### `process_update` execution step

The function `process_light_client_update(store, update, current_slot, genesis_validators_root)` should be executed with the specified parameters:

```yaml
{
    update: string             -- name of the `*.ssz_snappy` file to load
                                  as a `LightClientUpdate` object
    current_slot: int          -- integer, decimal
}
```

After this step, the `store` object may have been updated.

### `expected_finalized_header.ssz_snappy`

An SSZ-snappy encoded `expected_finalized_header` object of type `BeaconBlockHeader` that represents the expected `store.finalized_header` after applying all the test steps.

### `expected_optimistic_header.ssz_snappy`

An SSZ-snappy encoded `expected_optimistic_header` object of type `BeaconBlockHeader` that represents the expected `store.finalized_header` after applying all the test steps.

## Condition

A test-runner should initialize a local `LightClientStore` using the provided `bootstrap` object. It should then proceed to execute all the test steps in sequence. Finally, it should verify that the resulting `store` refers to the provided `expected_finalized_header` and `expected_optimistic_header`.
