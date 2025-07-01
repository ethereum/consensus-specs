# Light client sync tests

This series of tests provides reference test vectors for validating that a light
client implementing the sync protocol can sync to the latest block header.

## Test case format

### `meta.yaml`

```yaml
genesis_validators_root: Bytes32  -- string, hex encoded, with 0x prefix
trusted_block_root: Bytes32       -- string, hex encoded, with 0x prefix
bootstrap_fork_digest: string     -- encoded `ForkDigest`-context of `bootstrap`
store_fork_digest: string         -- encoded `ForkDigest`-context of `store` object being tested
```

### `bootstrap.ssz_snappy`

An SSZ-snappy encoded `bootstrap` object of type `LightClientBootstrap` to
initialize a local `store` object of type `LightClientStore` with
`store_fork_digest` using
`initialize_light_client_store(trusted_block_rooot, bootstrap)`. The SSZ type
can be determined from `bootstrap_fork_digest`.

If `store_fork_digest` differs from `bootstrap_fork_digest`, the `bootstrap`
object may need to be upgraded before initializing the store.

### `steps.yaml`

The steps to execute in sequence.

#### Checks to run after each step

Each step includes checks to verify the expected impact on the `store` object.

```yaml
finalized_header: {
    slot: int,                -- Integer value from store.finalized_header.beacon.slot
    beacon_root: string,      -- Encoded 32-byte value from store.finalized_header.beacon.hash_tree_root()
    execution_root: string,   -- From Capella onward; get_lc_execution_root(store.finalized_header)
}
optimistic_header: {
    slot: int,                -- Integer value from store.optimistic_header.beacon.slot
    beacon_root: string,      -- Encoded 32-byte value from store.optimistic_header.beacon.hash_tree_root()
    execution_root: string,   -- From Capella onward; get_lc_execution_root(store.optimistic_header)
}
```

#### `force_update` execution step

The function `process_light_client_store_force_update(store, current_slot)`
should be executed with the specified parameters:

```yaml
{
    current_slot: int                   -- integer, decimal
    checks: {<store_attribute>: value}  -- the assertions.
}
```

After this step, the `store` object may have been updated.

#### `process_update` execution step

The function
`process_light_client_update(store, update, current_slot, genesis_validators_root)`
should be executed with the specified parameters:

```yaml
{
    update_fork_digest: string          -- encoded `ForkDigest`-context of `update`
    update: string                      -- name of the `*.ssz_snappy` file to load
                                           as a `LightClientUpdate` object
    current_slot: int                   -- integer, decimal
    checks: {<store_attribute>: value}  -- the assertions.
}
```

If `store_fork_digest` differs from `update_fork_digest`, the `update` object
may need to be upgraded before processing the update.

After this step, the `store` object may have been updated.

#### `upgrade_store`

The `store` should be upgraded to reflect the new `store_fork_digest`:

```yaml
{
    store_fork_digest: string           -- encoded `ForkDigest`-context of `store`
    checks: {<store_attribute>: value}  -- the assertions.
}
```

After this step, the `store` object may have been updated.

## Condition

A test-runner should initialize a local `LightClientStore` using the provided
`bootstrap` object. It should then proceed to execute all the test steps in
sequence. After each step, it should verify that the resulting `store` verifies
against the provided `checks`.
