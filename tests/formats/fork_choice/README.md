# Fork choice tests

The aim of the fork choice tests is to provide test coverage of the various components of the fork choice.

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
{ tick: int }  --  to execute `on_tick(store, time)`
```

After this step, the `store` object may have been updated.

#### `on_attestation` execution step

The parameter that is required for executing `on_attestation(store, attestation)`.

```yaml
{ attestation: string }  -- the name of the `attestation_<32-byte-root>.ssz_snappy` file. To execute `on_attestation(store, attestation)` with the given attestation.
```
The file is located in the same folder (see below).

After this step, the `store` object may have been updated.

#### `on_block` execution step

The parameter that is required for executing `on_block(store, block)`.

```yaml
{ block: string }  -- the name of the `block_<32-byte-root>.ssz_snappy` file. To execute `on_block(store, block)` with the given attestation.
```
The file is located in the same folder (see below).

After this step, the `store` object may have been updated.

#### Checks step

The checks to verify the current status of `store`.

```yaml
checks: {<store_attibute>: value}  -- the assertions.
```

`<store_attibute>` is the field member or property of [`Store`](../../../specs/phase0/fork-choice.md#store) object that maintained by client implementation. Currently, the possible fields included:

```yaml
head: {                                     -- Encoded 32-byte value from get_head(store)
    slot: slot,
    root: string,
}
time: int                                   -- store.time
genesis_time: int                           -- store.genesis_time
justified_checkpoint_root: string           -- Encoded 32-byte value from store.justified_checkpoint.root
finalized_checkpoint_root: string           -- Encoded 32-byte value from store.finalized_checkpoint.root
best_justified_checkpoint_root: string      -- Encoded 32-byte value from store.best_justified_checkpoint.root
```

For example:
```yaml
- checks:
    time: 144
    genesis_time: 0
    head: {slot: 17, root: '0xd2724c86002f7e1f8656ab44a341a409ad80e6e70a5225fd94835566deebb66f'}
    justified_checkpoint_root: '0xcea6ecd3d3188e32ebf611f960eebd45b6c6f477a7cff242fa567a42653bfc7c'
    finalized_checkpoint_root: '0xcea6ecd3d3188e32ebf611f960eebd45b6c6f477a7cff242fa567a42653bfc7c'
    best_justified_checkpoint: '0xcea6ecd3d3188e32ebf611f960eebd45b6c6f477a7cff242fa567a42653bfc7c'
```

*Note*: Each `checks` step may include one or multiple items. Each item has to be checked against the current store.

### `attestation_<32-byte-root>.ssz_snappy`

`<32-byte-root>` is the hash tree root of the given attestation.

Each file is an SSZ-snappy encoded `Attestation`.

### `block_<32-byte-root>.ssz_snappy`

`<32-byte-root>` is the hash tree root of the given block.

Each file is an SSZ-snappy encoded `SignedBeaconBlock`.

## Condition

1. Deserialize `anchor_state.ssz_snappy` and `anchor_block.ssz_snappy` to initialize the local store object by with `get_forkchoice_store(anchor_state, anchor_block)` helper.
2. Iterate sequentially through `steps.yaml`
    - For each execution, look up the corresponding ssz_snappy file. Execute the corresponding helper function on the current store.
        - For the `on_block` execution step: if `len(block.message.body.attestations) > 0`, execute each attestation with `on_attestation(store, attestation)` after executing `on_block(store, block)`.
    - For each `checks` step, the assertions on the current store must be satisfied.
