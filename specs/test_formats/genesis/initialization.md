# Genesis creation testing

Tests the initialization of a genesis state based on Eth1 data.

## Test case format

```yaml
description: string            -- description of test case, purely for debugging purposes
bls_setting: int               -- see general test-format spec.
eth1_block_hash: Bytes32       -- the root of the Eth-1 block, hex encoded, with prefix 0x
eth1_timestamp: int            -- the timestamp of the block, in seconds.
deposits: [Deposit]            -- list of deposits to build the genesis state with
state: BeaconState             -- the expected genesis state.
```

To process this test, build a genesis state with the provided `eth1_block_hash`, `eth1_timestamp` and `deposits`:
`initialize_beacon_state_from_eth1(eth1_block_hash, eth1_timestamp, deposits)`,
 as described in the Beacon Chain specification.

## Condition

The resulting state should match the expected `state`.
