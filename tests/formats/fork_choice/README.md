# Fork choice tests

The aim of the tests for the fork choice rules.

## Test case format

### `meta.yaml`

```yaml
description: string    -- Optional. Description of test case, purely for debugging purposes.
bls_setting: int       -- see general test-format spec.
```

### `anchor_state.ssz_snappy`

A YAML-encoded `BeaconState`, the state to initialize store with `get_forkchoice_store(anchor_state: BeaconState, anchor_block: BeaconBlock)` helper.

### `anchor_block.ssz_snappy`

A YAML-encoded `BeaconBlock`, the block to initialize store with `get_forkchoice_store(anchor_state: BeaconState, anchor_block: BeaconBlock)` helper.

### `steps.yaml`

The steps to execute in sequence. There may be multiple items of the following types:

#### `on_tick` execution step

The parameter that is required for executing `on_tick(store, time)`.

```yaml
{ tick: int }   --  to execute `on_tick(store, time)`
```

After this step, the `store` object may have been updated.

#### `on_attestation` execution step

The parameter that is required for executing `on_attestation(store, attestation)`.

```yaml
{ attestation: string }:  -- the name of the `attestation_<32-byte-root>.ssz_snappy` file. To execute `on_attestation(store, attestation)` with the given attestation.
```
The file is located in the same folder (see below).

After this step, the `store` object may have been updated.

#### `on_block` execution step

The parameter that is required for executing `on_block(store, block)`.

```yaml
{ block: string }:        -- the name of the `block_<32-byte-root>.ssz_snappy` file. To execute `on_block(store, block)` with the given attestation.
```
The file is located in the same folder (see below).

After this step, the `store` object may have been updated.

#### Checks step

The checks to verify the current status of `store` .

```yaml
checks: {<store_field_name>: value}   -- the assertions.
```

`<store_field_name>` is the field member of [`Store`](../../../specs/phase0/fork-choice.md#store) object that maintained by client implementation. Currently, the possible fields included:

```yaml
time: int                                   -- store.time
genesis_time: int                           -- store.genesis_time
justified_checkpoint_root: string           -- store.justified_checkpoint.root
finalized_checkpoint_root: string           -- store.finalized_checkpoint_root.root
best_justified_checkpoint_root: string      -- store.best_justified_checkpoint_root.root
```

For example:
```yaml
- checks: {
    justified_checkpoint_root: '0x347468b606d03f8429afd491f94e32cd3a2295c2536e808c863a9d132a521dc4',
    head: '0x17aa608f5fce87592c6f02ca6ca3c49ca70b5cef5456697709b2e5894e3879c2'
}
```

### `attestation_<32-byte-root>.ssz_snappy`

`<32-byte-root>` is the hash tree root of the given attestation.

Each file is a YAML-encoded `Attestation`.

### `block_<32-byte-root>.ssz_snappy`

`<32-byte-root>` is the hash tree root of the given block.

Each file is a YAML-encoded `SignedBeaconBlock`.

## Condition

1. Deserialize `anchor_state.ssz_snappy` and `anchor_block.ssz_snappy` to initialize the local store object by with `get_forkchoice_store(anchor_state, anchor_block)` helper.
2. Go through `steps.yaml`
    - For each execution, look up the corresponding ssz_snappy file. Execute the corresponding helper function on your store.
    - For each `checks` step, the assertions must be satisfied.
