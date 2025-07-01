# Fork choice tests

The aim of the fork choice tests is to provide test coverage of the various
components of the fork choice.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Test case format](#test-case-format)
  - [`meta.yaml`](#metayaml)
  - [`anchor_state.ssz_snappy`](#anchor_statessz_snappy)
  - [`anchor_block.ssz_snappy`](#anchor_blockssz_snappy)
  - [`steps.yaml`](#stepsyaml)
    - [`on_tick` execution step](#on_tick-execution-step)
    - [`on_attestation` execution step](#on_attestation-execution-step)
    - [`on_block` execution step](#on_block-execution-step)
    - [`on_merge_block` execution step](#on_merge_block-execution-step)
    - [`on_attester_slashing` execution step](#on_attester_slashing-execution-step)
    - [`on_payload_info` execution step](#on_payload_info-execution-step)
    - [Checks step](#checks-step)
  - [`attestation_<32-byte-root>.ssz_snappy`](#attestation_32-byte-rootssz_snappy)
  - [`block_<32-byte-root>.ssz_snappy`](#block_32-byte-rootssz_snappy)
- [Condition](#condition)

<!-- mdformat-toc end -->

## Test case format

### `meta.yaml`

```yaml
description: string    -- Optional. Description of test case, purely for debugging purposes.
bls_setting: int       -- see general test-format spec.
```

### `anchor_state.ssz_snappy`

An SSZ-snappy encoded `BeaconState`, the state to initialize store with
`get_forkchoice_store(anchor_state: BeaconState, anchor_block: BeaconBlock)`
helper.

### `anchor_block.ssz_snappy`

An SSZ-snappy encoded `BeaconBlock`, the block to initialize store with
`get_forkchoice_store(anchor_state: BeaconState, anchor_block: BeaconBlock)`
helper.

### `steps.yaml`

The steps to execute in sequence. There may be multiple items of the following
types:

#### `on_tick` execution step

The parameter that is required for executing `on_tick(store, time)`.

```yaml
{
    tick: int       -- to execute `on_tick(store, time)`.
    valid: bool     -- optional, default to `true`.
                       If it's `false`, this execution step is expected to be invalid.
}
```

After this step, the `store` object may have been updated.

#### `on_attestation` execution step

The parameter that is required for executing
`on_attestation(store, attestation)`.

```yaml
{
    attestation: string  -- the name of the `attestation_<32-byte-root>.ssz_snappy` file.
                            To execute `on_attestation(store, attestation)` with the given attestation.
    valid: bool          -- optional, default to `true`.
                            If it's `false`, this execution step is expected to be invalid.
}
```

The file is located in the same folder (see below).

After this step, the `store` object may have been updated.

#### `on_block` execution step

The parameter that is required for executing `on_block(store, block)`.

```yaml
{
    block: string           -- the name of the `block_<32-byte-root>.ssz_snappy` file.
                              To execute `on_block(store, block)` with the given attestation.
    blobs: string           -- optional, the name of the `blobs_<32-byte-root>.ssz_snappy` file.
                               The blobs file content is a `List[Blob, MAX_BLOB_COMMITMENTS_PER_BLOCK]` SSZ object.
    proofs: array of byte48 hex string -- optional, the proofs of blob commitments.
    columns: string        -- optional, array of the names of the `column_<32-byte-root>.ssz_snappy` files.
    valid: bool             -- optional, default to `true`.
                               If it's `false`, this execution step is expected to be invalid.
}
```

The file is located in the same folder (see below).

`blobs` and `proofs` are new fields from Deneb EIP-4844. These fields indicate
the expected values from `retrieve_blobs_and_proofs()` helper inside
`is_data_available()` helper. If these two fields are not provided,
`retrieve_blobs_and_proofs()` returns empty lists.

`columns` is a new field in Fulu EIP-7594. This field indicate the expected values from `retrieve_column_sidecars` helper inside `is_data_available()` helper. If this field is an empty array, `retrieve_column_sidecars` should throw an exception (not enough data sampled). If this field is not provided, `retrieve_column_sidecars` returns an empty list.

Post-Deneb and pre-Fulu, `columns` should not be present. Post-Fulu `blobs` and `proofs` should not be present.

After this step, the `store` object may have been updated.

#### `on_merge_block` execution step

Adds `PowBlock` data which is required for executing `on_block(store, block)`.

```yaml
{
    pow_block: string  -- the name of the `pow_block_<32-byte-root>.ssz_snappy` file.
                          To be used in `get_pow_block` lookup
}
```

The file is located in the same folder (see below). PowBlocks should be used as
return values for `get_pow_block(hash: Hash32) -> PowBlock` function if hashes
match.

#### `on_attester_slashing` execution step

The parameter that is required for executing
`on_attester_slashing(store, attester_slashing)`.

```yaml
{
    attester_slashing: string  -- the name of the `attester_slashing_<32-byte-root>.ssz_snappy` file.
                            To execute `on_attester_slashing(store, attester_slashing)` with the given attester slashing.
    valid: bool          -- optional, default to `true`.
                            If it's `false`, this execution step is expected to be invalid.
}
```

The file is located in the same folder (see below).

After this step, the `store` object may have been updated.

#### `on_payload_info` execution step

Optional step for optimistic sync tests.

```yaml
{
    block_hash: string,             -- Encoded 32-byte value of payload's block hash.
    payload_status: {
        status: string,             -- Enum, "VALID" | "INVALID" | "SYNCING" | "ACCEPTED" | "INVALID_BLOCK_HASH".
        latest_valid_hash: string,    -- Encoded 32-byte value of the latest valid block hash, may be `null`.
        validation_error: string,    -- Message providing additional details on the validation error, may be `null`.
    }
}
```

This step sets the
[`payloadStatus`](https://github.com/ethereum/execution-apis/blob/main/src/engine/paris.md#payloadstatusv1)
value that Execution Layer client mock returns in responses to the following
Engine API calls:

- [`engine_newPayloadV1(payload)`](https://github.com/ethereum/execution-apis/blob/main/src/engine/paris.md#engine_newpayloadv1)
  if `payload.blockHash == payload_info.block_hash`
- [`engine_forkchoiceUpdatedV1(forkchoiceState, ...)`](https://github.com/ethereum/execution-apis/blob/main/src/engine/paris.md#engine_forkchoiceupdatedv1)
  if `forkchoiceState.headBlockHash == payload_info.block_hash`

*Note*: Status of a payload must be *initialized* via `on_payload_info` before
the corresponding `on_block` execution step.

*Note*: Status of the same payload may be updated for several times throughout
the test.

#### Checks step

The checks to verify the current status of `store`.

```yaml
checks: {<store_attribute>: value}  -- the assertions.
```

`<store_attribute>` is the field member or property of
[`Store`](../../../specs/phase0/fork-choice.md#store) object that maintained by
client implementation. The fields include:

```yaml
head: {
    slot: int,
    root: string,             -- Encoded 32-byte value from get_head(store)
}
time: int                     -- store.time
genesis_time: int             -- store.genesis_time
justified_checkpoint: {
    epoch: int,               -- Integer value from store.justified_checkpoint.epoch
    root: string,             -- Encoded 32-byte value from store.justified_checkpoint.root
}
finalized_checkpoint: {
    epoch: int,               -- Integer value from store.finalized_checkpoint.epoch
    root: string,             -- Encoded 32-byte value from store.finalized_checkpoint.root
}
proposer_boost_root: string   -- Encoded 32-byte value from store.proposer_boost_root
viable_for_head_roots_and_weights: [{
    root: string,             -- Encoded 32-byte value of filtered_block_tree leaf blocks
    weight: int               -- Integer value from get_weight(store, viable_block_root)
}]
```

Additionally, these fields if `get_proposer_head` and
`should_override_forkchoice_update` features are implemented:

```yaml
get_proposer_head: string             -- Encoded 32-byte value from get_proposer_head(store)
should_override_forkchoice_update: {  -- [New in Bellatrix]
    validator_is_connected: bool,     -- The mocking result of `validator_is_connected(proposer_index)` in this call
    result: bool,                     -- The result of `should_override_forkchoice_update(store, head_root)`, where head_root is the result value from get_head(store)
}
```

For example:

```yaml
- checks:
    time: 192
    head: {slot: 32, root: '0xdaa1d49d57594ced0c35688a6da133abb086d191a2ebdfd736fad95299325aeb'}
    justified_checkpoint: {epoch: 3, root: '0xc25faab4acab38d3560864ca01e4d5cc4dc2cd473da053fbc03c2669143a2de4'}
    finalized_checkpoint: {epoch: 2, root: '0x40d32d6283ec11c53317a46808bc88f55657d93b95a1af920403187accf48f4f'}
    proposer_boost_root: '0xdaa1d49d57594ced0c35688a6da133abb086d191a2ebdfd736fad95299325aeb'
    get_proposer_head: '0xdaa1d49d57594ced0c35688a6da133abb086d191a2ebdfd736fad95299325aeb'
    should_override_forkchoice_update: {validator_is_connected: false, result: false}
    viable_for_head_roots_and_weights: [
      {root: '0x533290b6f44d31c925acd08dfc8448624979d48c40b877d4e6714648866c9ddb', weight: 192000000000},
      {root: '0x5cfb9d9099cdf1d8ab68ce96cdae9f0fa6eef16914a01070580dfdc1d2d59ec3', weight: 544000000000}
    ]
```

*Note*: Each `checks` step may include one or multiple items. Each item has to
be checked against the current store.

### `attestation_<32-byte-root>.ssz_snappy`

`<32-byte-root>` is the hash tree root of the given attestation.

Each file is an SSZ-snappy encoded `Attestation`.

### `block_<32-byte-root>.ssz_snappy`

`<32-byte-root>` is the hash tree root of the given block.

Each file is an SSZ-snappy encoded `SignedBeaconBlock`.

## Condition

1. Deserialize `anchor_state.ssz_snappy` and `anchor_block.ssz_snappy` to
   initialize the local store object by with
   `get_forkchoice_store(anchor_state, anchor_block)` helper.
2. Iterate sequentially through `steps.yaml`
   - For each execution, look up the corresponding ssz_snappy file. Execute the
     corresponding helper function on the current store.
     - For the `on_block` execution step: if
       `len(block.message.body.attestations) > 0`, execute each attestation with
       `on_attestation(store, attestation)` after executing
       `on_block(store, block)`.
   - For each `checks` step, the assertions on the current store must be
     satisfied.
