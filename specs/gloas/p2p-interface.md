# Gloas -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modification in Gloas](#modification-in-gloas)
  - [Helper functions](#helper-functions)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)
  - [Configuration](#configuration)
  - [Containers](#containers)
    - [Modified `DataColumnSidecar`](#modified-datacolumnsidecar)
  - [Helpers](#helpers)
    - [Modified `verify_data_column_sidecar`](#modified-verify_data_column_sidecar)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [`beacon_aggregate_and_proof`](#beacon_aggregate_and_proof)
        - [`beacon_block`](#beacon_block)
        - [`execution_payload`](#execution_payload)
        - [`payload_attestation_message`](#payload_attestation_message)
        - [`execution_payload_bid`](#execution_payload_bid)
      - [Blob subnets](#blob-subnets)
        - [`data_column_sidecar_{subnet_id}`](#data_column_sidecar_subnet_id)
      - [Attestation subnets](#attestation-subnets)
        - [`beacon_attestation_{subnet_id}`](#beacon_attestation_subnet_id)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [BeaconBlocksByRange v2](#beaconblocksbyrange-v2)
      - [BeaconBlocksByRoot v2](#beaconblocksbyroot-v2)
      - [ExecutionPayloadEnvelopesByRange v1](#executionpayloadenvelopesbyrange-v1)
      - [ExecutionPayloadEnvelopesByRoot v1](#executionpayloadenvelopesbyroot-v1)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specification for Gloas.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

## Modification in Gloas

### Helper functions

#### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= GLOAS_FORK_EPOCH:
        return GLOAS_FORK_VERSION
    if epoch >= FULU_FORK_EPOCH:
        return FULU_FORK_VERSION
    if epoch >= ELECTRA_FORK_EPOCH:
        return ELECTRA_FORK_VERSION
    if epoch >= DENEB_FORK_EPOCH:
        return DENEB_FORK_VERSION
    if epoch >= CAPELLA_FORK_EPOCH:
        return CAPELLA_FORK_VERSION
    if epoch >= BELLATRIX_FORK_EPOCH:
        return BELLATRIX_FORK_VERSION
    if epoch >= ALTAIR_FORK_EPOCH:
        return ALTAIR_FORK_VERSION
    return GENESIS_FORK_VERSION
```

### Configuration

*[New in Gloas:EIP7732]*

| Name                   | Value          | Description                                                       |
| ---------------------- | -------------- | ----------------------------------------------------------------- |
| `MAX_REQUEST_PAYLOADS` | `2**7` (= 128) | Maximum number of execution payload envelopes in a single request |

### Containers

#### Modified `DataColumnSidecar`

*Note*: The `signed_block_header` and `kzg_commitments_inclusion_proof` fields
have been removed from `DataColumnSidecar` in Gloas as header and inclusion
proof verifications are no longer required in ePBS. Instead, sidecars are
validated by checking that the hash of `kzg_commitments` matches what's
committed in the builder's bid for the corresponding `beacon_block_root`.

```python
class DataColumnSidecar(Container):
    index: ColumnIndex
    column: List[Cell, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    kzg_proofs: List[KZGProof, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    # [Modified in Gloas:EIP7732]
    # Removed `signed_block_header`
    # [Modified in Gloas:EIP7732]
    # Removed `kzg_commitments_inclusion_proof`
    # [New in Gloas:EIP7732]
    slot: Slot
    # [New in Gloas:EIP7732]
    beacon_block_root: Root
```

### Helpers

##### Modified `verify_data_column_sidecar`

```python
def verify_data_column_sidecar(sidecar: DataColumnSidecar) -> bool:
    """
    Verify if the data column sidecar is valid.
    """
    # The sidecar index must be within the valid range
    if sidecar.index >= NUMBER_OF_COLUMNS:
        return False

    # A sidecar for zero blobs is invalid
    if len(sidecar.kzg_commitments) == 0:
        return False

    # [Modified in Gloas:EIP7732]
    # Check that the sidecar respects the blob limit
    epoch = compute_epoch_at_slot(sidecar.slot)
    if len(sidecar.kzg_commitments) > get_blob_parameters(epoch).max_blobs_per_block:
        return False

    # The column length must be equal to the number of commitments/proofs
    if len(sidecar.column) != len(sidecar.kzg_commitments) or len(sidecar.column) != len(
        sidecar.kzg_proofs
    ):
        return False

    return True
```

### The gossip domain: gossipsub

Some gossip meshes are upgraded in the fork of Gloas to support upgraded types.

#### Topics and messages

Topics follow the same specification as in prior upgrades.

The `beacon_block` topic is updated to support the modified type

| Name           | Message Type        |
| -------------- | ------------------- |
| `beacon_block` | `SignedBeaconBlock` |

The new topics along with the type of the `data` field of a gossipsub message
are given in this table:

| Name                          | Message Type                     |
| ----------------------------- | -------------------------------- |
| `execution_payload_bid`       | `SignedExecutionPayloadBid`      |
| `execution_payload`           | `SignedExecutionPayloadEnvelope` |
| `payload_attestation_message` | `PayloadAttestationMessage`      |

##### Global topics

Gloas introduces new global topics for execution bid, execution payload and
payload attestation.

###### `beacon_aggregate_and_proof`

Let `block` be the beacon block corresponding to
`aggregate.data.beacon_block_root`.

The following validations are added:

- _[REJECT]_ `aggregate.data.index < 2`.
- _[REJECT]_ `aggregate.data.index == 0` if `block.slot == aggregate.data.slot`.

The following validations are removed:

- _[REJECT]_ `aggregate.data.index == 0`.

###### `beacon_block`

*[Modified in Gloas:EIP7732]*

The *type* of the payload of this topic changes to the (modified)
`SignedBeaconBlock` found in [the Beacon Chain changes](./beacon-chain.md).

There are no new validations for this topic. However, all validations with
regards to the `ExecutionPayload` are removed:

- _[REJECT]_ The length of KZG commitments is less than or equal to the
  limitation defined in Consensus Layer -- i.e. validate that
  `len(signed_beacon_block.message.body.blob_kzg_commitments) <= get_blob_parameters(get_current_epoch(state)).max_blobs_per_block`
- _[REJECT]_ The block's execution payload timestamp is correct with respect to
  the slot -- i.e.
  `execution_payload.timestamp == compute_time_at_slot(state, block.slot)`.
- If `execution_payload` verification of block's parent by an execution node is
  *not* complete:
  - [REJECT] The block's parent (defined by `block.parent_root`) passes all
    validation (excluding execution node verification of the
    `block.body.execution_payload`).
- otherwise:
  - [IGNORE] The block's parent (defined by `block.parent_root`) passes all
    validation (including execution node verification of the
    `block.body.execution_payload`).

And instead the following validations are set in place with the alias
`bid = signed_execution_payload_bid.message`:

- If `execution_payload` verification of block's execution payload parent by an
  execution node **is complete**:
  - [REJECT] The block's execution payload parent (defined by
    `bid.parent_block_hash`) passes all validation.
- [REJECT] The bid's parent (defined by `bid.parent_block_root`) equals the
  block's parent (defined by `block.parent_root`).

###### `execution_payload`

This topic is used to propagate execution payload messages as
`SignedExecutionPayloadEnvelope`.

The following validations MUST pass before forwarding the
`signed_execution_payload_envelope` on the network, assuming the alias
`envelope = signed_execution_payload_envelope.message`,
`payload = envelope.payload`:

- _[IGNORE]_ The envelope's block root `envelope.block_root` has been seen (via
  gossip or non-gossip sources) (a client MAY queue payload for processing once
  the block is retrieved).
- _[IGNORE]_ The node has not seen another valid
  `SignedExecutionPayloadEnvelope` for this block root from this builder.
- _[IGNORE]_ The envelope is from a slot greater than or equal to the latest
  finalized slot -- i.e. validate that
  `envelope.slot >= compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)`

Let `block` be the block with `envelope.beacon_block_root`. Let `bid` alias
`block.body.signed_execution_payload_bid.message` (notice that this can be
obtained from the `state.latest_execution_payload_bid`)

- _[REJECT]_ `block` passes validation.
- _[REJECT]_ `block.slot` equals `envelope.slot`.
- _[REJECT]_ `envelope.builder_index == bid.builder_index`
- _[REJECT]_ `payload.block_hash == bid.block_hash`
- _[REJECT]_ `signed_execution_payload_envelope.signature` is valid with respect
  to the builder's public key.

###### `payload_attestation_message`

This topic is used to propagate signed payload attestation message.

The following validations MUST pass before forwarding the
`payload_attestation_message` on the network, assuming the alias
`data = payload_attestation_message.data`:

- _[IGNORE]_ The message's slot is for the current slot (with a
  `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance), i.e. `data.slot == current_slot`.
- _[IGNORE]_ The `payload_attestation_message` is the first valid message
  received from the validator with index
  `payload_attestation_message.validate_index`.
- _[IGNORE]_ The message's block `data.beacon_block_root` has been seen (via
  gossip or non-gossip sources) (a client MAY queue attestation for processing
  once the block is retrieved. Note a client might want to request payload
  after).
- _[REJECT]_ The message's block `data.beacon_block_root` passes validation.
- _[REJECT]_ The message's validator index is within the payload committee in
  `get_ptc(state, data.slot)`. The `state` is the head state corresponding to
  processing the block up to the current slot as determined by the fork choice.
- _[REJECT]_ `payload_attestation_message.signature` is valid with respect to
  the validator's public key.

###### `execution_payload_bid`

This topic is used to propagate signed bids as `SignedExecutionPayloadBid`.

The following validations MUST pass before forwarding the
`signed_execution_payload_bid` on the network, assuming the alias
`bid = signed_execution_payload_bid.message`:

- _[REJECT]_ `bid.builder_index` is a valid/active builder index -- i.e.
  `is_active_builder(state, bid.builder_index)` returns `True`.
- _[REJECT]_ `bid.execution_payment` is zero.
- _[IGNORE]_ this is the first signed bid seen with a valid signature from the
  given builder for this slot.
- _[IGNORE]_ this bid is the highest value bid seen for the corresponding slot
  and the given parent block hash.
- _[IGNORE]_ `bid.value` is less or equal than the builder's excess balance --
  i.e. `can_builder_cover_bid(state, builder_index, amount)` returns `True`.
- _[IGNORE]_ `bid.parent_block_hash` is the block hash of a known execution
  payload in fork choice.
- _[IGNORE]_ `bid.parent_block_root` is the hash tree root of a known beacon
  block in fork choice.
- _[IGNORE]_ `bid.slot` is the current slot or the next slot.
- _[REJECT]_ `signed_execution_payload_bid.signature` is valid with respect to
  the `bid.builder_index`.

##### Blob subnets

###### `data_column_sidecar_{subnet_id}`

*[Modified in Gloas:EIP7732]*

This topic is used to propagate column sidecars, where each column maps to some
`subnet_id`.

The *type* of the payload of this topic is `DataColumnSidecar`.

The following validations MUST pass before forwarding the
`sidecar: DataColumnSidecar` on the network:

**Modified from Fulu:**

- _[IGNORE]_ The sidecar is the first sidecar for the tuple
  `(sidecar.beacon_block_root, sidecar.index)` with valid kzg proof.

**Added in Gloas:**

- _[IGNORE]_ The sidecar's `beacon_block_root` has been seen via a valid signed
  execution payload bid. A client MAY queue the sidecar for processing once the
  block is retrieved.
- _[REJECT]_ The sidecars's `slot` matches the slot of the block with root
  `beacon_block_root`.
- _[REJECT]_ The hash of the sidecar's `kzg_commitments` matches the
  `blob_kzg_commitments_root` in the corresponding builder's bid for
  `sidecar.beacon_block_root`.

**Removed from Fulu:**

- _[IGNORE]_ The sidecar is not from a future slot (with a
  `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) -- i.e. validate that
  `block_header.slot <= current_slot` (a client MAY queue future sidecars for
  processing at the appropriate slot).
- _[IGNORE]_ The sidecar is from a slot greater than the latest finalized slot
  -- i.e. validate that
  `block_header.slot > compute_start_slot_at_epoch(state.finalized_checkpoint.epoch)`
- _[REJECT]_ The proposer signature of `sidecar.signed_block_header`, is valid
  with respect to the `block_header.proposer_index` pubkey.
- _[IGNORE]_ The sidecar's block's parent (defined by
  `block_header.parent_root`) has been seen (via gossip or non-gossip sources)
  (a client MAY queue sidecars for processing once the parent block is
  retrieved).
- _[REJECT]_ The sidecar's block's parent (defined by
  `block_header.parent_root`) passes validation.
- _[REJECT]_ The sidecar is from a higher slot than the sidecar's block's parent
  (defined by `block_header.parent_root`).
- _[REJECT]_ The current finalized_checkpoint is an ancestor of the sidecar's
  block -- i.e.
  `get_checkpoint_block(store, block_header.parent_root, store.finalized_checkpoint.epoch) == store.finalized_checkpoint.root`.
- _[REJECT]_ The sidecar's `kzg_commitments` field inclusion proof is valid as
  verified by `verify_data_column_sidecar_inclusion_proof(sidecar)`.
- _[REJECT]_ The sidecar is proposed by the expected `proposer_index` for the
  block's slot in the context of the current shuffling (defined by
  `block_header.parent_root`/`block_header.slot`). If the `proposer_index`
  cannot immediately be verified against the expected shuffling, the sidecar MAY
  be queued for later processing while proposers for the block's branch are
  calculated -- in such a case _do not_ `REJECT`, instead `IGNORE` this message.

##### Attestation subnets

###### `beacon_attestation_{subnet_id}`

Let `block` be the beacon block corresponding to
`attestation.data.beacon_block_root`.

The following validations are added:

- _[REJECT]_ `attestation.data.index < 2`.
- _[REJECT]_ `attestation.data.index == 0` if
  `block.slot == attestation.data.slot`.

The following validations are removed:

- _[REJECT]_ `attestation.data.index == 0`.

### The Req/Resp domain

#### Messages

##### BeaconBlocksByRange v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/2/`

<!-- eth2spec: skip -->

| `fork_version`           | Chunk SSZ type                |
| ------------------------ | ----------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock`   |
| `DENEB_FORK_VERSION`     | `deneb.SignedBeaconBlock`     |
| `ELECTRA_FORK_VERSION`   | `electra.SignedBeaconBlock`   |
| `FULU_FORK_VERSION`      | `fulu.SignedBeaconBlock`      |
| `GLOAS_FORK_VERSION`     | `gloas.SignedBeaconBlock`     |

##### BeaconBlocksByRoot v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_root/2/`

<!-- eth2spec: skip -->

| `fork_version`           | Chunk SSZ type                |
| ------------------------ | ----------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock`   |
| `DENEB_FORK_VERSION`     | `deneb.SignedBeaconBlock`     |
| `ELECTRA_FORK_VERSION`   | `electra.SignedBeaconBlock`   |
| `FULU_FORK_VERSION`      | `fulu.SignedBeaconBlock`      |
| `GLOAS_FORK_VERSION`     | `gloas.SignedBeaconBlock`     |

##### ExecutionPayloadEnvelopesByRange v1

**Protocol ID:**
`/eth2/beacon_chain/req/execution_payload_envelopes_by_range/1/`

*[New in Gloas:EIP7732]*

Request Content:

```
(
  start_slot: Slot
  count: uint64
)
```

Response Content:

```
(
  List[SignedExecutionPayloadEnvelope, MAX_REQUEST_BLOCKS_DENEB]
)
```

Specifications of req\\response methods are equivalent to
[BeaconBlocksByRange v2](#beaconblocksbyrange-v2), with the only difference
being the response content type.

For each successful `response_chunk`, the `ForkDigest` context epoch is
determined by `compute_epoch_at_slot(beacon_block.slot)` based on the
`beacon_block` referred to by
`signed_execution_payload_envelope.message.beacon_block_root`.

Per `fork_version = compute_fork_version(epoch)`:

<!-- eth2spec: skip -->

| `fork_version`       | Chunk SSZ type                         |
| -------------------- | -------------------------------------- |
| `GLOAS_FORK_VERSION` | `gloas.SignedExecutionPayloadEnvelope` |

##### ExecutionPayloadEnvelopesByRoot v1

**Protocol ID:** `/eth2/beacon_chain/req/execution_payload_envelopes_by_root/1/`

For each successful `response_chunk`, the `ForkDigest` context epoch is
determined by `compute_epoch_at_slot(beacon_block.slot)` based on the
`beacon_block` referred to by
`signed_execution_payload_envelope.message.beacon_block_root`.

Per `fork_version = compute_fork_version(epoch)`:

<!-- eth2spec: skip -->

| `fork_version`       | Chunk SSZ type                         |
| -------------------- | -------------------------------------- |
| `GLOAS_FORK_VERSION` | `gloas.SignedExecutionPayloadEnvelope` |

Request Content:

```
(
  List[Root, MAX_REQUEST_PAYLOADS]
)
```

Response Content:

```
(
  List[SignedExecutionPayloadEnvelope, MAX_REQUEST_PAYLOADS]
)
```

Requests execution payload envelopes by
`signed_execution_payload_envelope.message.block_root`. The response is a list
of `SignedExecutionPayloadEnvelope` whose length is less than or equal to the
number of requested execution payload envelopes. It may be less in the case that
the responding peer is missing payload envelopes.

No more than `MAX_REQUEST_PAYLOADS` may be requested at a time.

ExecutionPayloadEnvelopesByRoot is primarily used to recover recent execution
payload envelopes (e.g. when receiving a payload attestation with revealed
status as true but never received a payload).

The request MUST be encoded as an SSZ-field.

The response MUST consist of zero or more `response_chunk`. Each successful
`response_chunk` MUST contain a single `SignedExecutionPayloadEnvelope` payload.

Clients MUST support requesting payload envelopes since the latest finalized
epoch.

Clients MUST respond with at least one payload envelope, if they have it.
Clients MAY limit the number of payload envelopes in the response.
