# Light client data collection tests

This series of tests provides reference test vectors for validating that a full
node collects canonical data for serving to light clients implementing the light
client sync protocol to sync to the latest block header.

## Test case format

### `initial_state.ssz_snappy`

An SSZ-snappy encoded object of type `BeaconState` to initialize the blockchain
from. The state's `slot` is epoch aligned.

### `steps.yaml`

The steps to execute in sequence.

#### `new_block` execution step

The new block described by the test step should be imported, but does not become
head yet.

```yaml
{
    fork_digest: string                -- encoded `ForkDigest`-context of `block`
    data: string                       -- name of the `*.ssz_snappy` file to load
                                          as a `SignedBeaconBlock` object
}
```

#### `new_head` execution step

The given block (previously imported) should become head, leading to potential
updates to:

- The best `LightClientUpdate` for non-finalized sync committee periods.
- The latest `LightClientFinalityUpdate` and `LightClientOptimisticUpdate`.
- The latest finalized `Checkpoint` (across all branches).
- The available `LightClientBootstrap` instances for newly finalized
  `Checkpoint`s.

```yaml
{
    head_block_root: Bytes32           -- string, hex encoded, with 0x prefix
    checks: {
        latest_finalized_checkpoint: { -- tracked across all branches
            epoch: int                 -- integer, decimal
            root: Bytes32              -- string, hex encoded, with 0x prefix
        }
        bootstraps: [                  -- one entry per `LightClientBootstrap`
            block_root: Bytes32        -- string, hex encoded, with 0x prefix
            bootstrap: {               -- only exists if a `LightClientBootstrap` is available
                fork_digest: string    -- encoded `ForkDigest`-context of `data`
                data: string           -- name of the `*.ssz_snappy` file to load
                                          as a `LightClientBootstrap` object
            }
        ]
        best_updates: [                -- one entry per sync committee period
            period: int                -- integer, decimal
            update: {                  -- only exists if a best `LightClientUpdate` is available
                fork_digest: string    -- encoded `ForkDigest`-context of `data`
                data: string           -- name of the `*.ssz_snappy` file to load
                                          as a `LightClientUpdate` object
            }
        ]
        latest_finality_update: {      -- only exists if a `LightClientFinalityUpdate` is available
            fork_digest: string        -- encoded `ForkDigest`-context of `data`
            data: string               -- name of the `*.ssz_snappy` file to load
                                          as a `LightClientFinalityUpdate` object
        }
        latest_optimistic_update: {    -- only exists if a `LightClientOptimisticUpdate` is available
            fork_digest: string        -- encoded `ForkDigest`-context of `data`
            data: string               -- name of the `*.ssz_snappy` file to load
                                          as a `LightClientOptimisticUpdate` object
        }
    }
}
```

## Condition

A test-runner should initialize a simplified blockchain from `initial_state`. An
external signal is used to control fork choice. The test-runner should then
proceed to execute all the test steps in sequence, collecting light client data
during execution. After each `new_head` step, it should verify that the
collected light client data matches the provided `checks`.
