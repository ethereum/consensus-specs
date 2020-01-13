# Genesis creation testing

Tests the initialization of a genesis state based on Eth1 data.

## Test case format

### `eth1_block_hash.yaml`

A `Bytes32` hex encoded, with prefix 0x. The root of the Eth1 block.

Also available as `eth1_block_hash.ssz`.

### `eth1_timestamp.yaml`

An integer. The timestamp of the block, in seconds.

### `meta.yaml`

A yaml file to help read the deposit count:

```yaml
deposits_count: int    -- Amount of deposits.
```

### `deposits_<index>.yaml`

A series of files, with `<index>` in range `[0, deposits_count)`. Deposits need to be processed in order.
Each file is a YAML-encoded `Deposit` object.

Each deposit is also available as `deposits_<index>.ssz`.

###  `state.yaml`

The expected genesis state. A YAML-encoded `BeaconState` object.

Also available as `state.ssz`.

## Processing

To process this test, build a genesis state with the provided `eth1_block_hash`, `eth1_timestamp` and `deposits`:
`initialize_beacon_state_from_eth1(eth1_block_hash, eth1_timestamp, deposits)`,
 as described in the Beacon Chain specification.

## Condition

The resulting state should match the expected `state`.
