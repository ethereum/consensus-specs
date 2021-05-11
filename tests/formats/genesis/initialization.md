# Genesis creation testing

Tests the initialization of a genesis state based on Eth1 data.

## Test case format

### `eth1.yaml`

```yaml
eth1_block_hash: Bytes32  -- A `Bytes32` hex encoded, with prefix 0x. The root of the Eth1 block. E.g. "0x4242424242424242424242424242424242424242424242424242424242424242"
eth1_timestamp: int       -- An integer. The timestamp of the block, in seconds.
```


### `meta.yaml`

A yaml file to help read the deposit count:

```yaml
description: string    -- Optional. Description of test case, purely for debugging purposes.
deposits_count: int    -- Amount of deposits.
```

### `deposits_<index>.ssz_snappy`

A series of files, with `<index>` in range `[0, deposits_count)`. Deposits need to be processed in order.
Each file is a SSZ-snappy encoded `Deposit` object.

###  `state.ssz_snappy`

The expected genesis state. An SSZ-snappy encoded `BeaconState` object.


## Processing

To process this test, build a genesis state with the provided `eth1_block_hash`, `eth1_timestamp` and `deposits`:
`initialize_beacon_state_from_eth1(eth1_block_hash, eth1_timestamp, deposits)`,
 as described in the Beacon Chain specification.

## Condition

The resulting state should match the expected `state`.
