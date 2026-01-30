# Gloas -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modification in Gloas](#modification-in-gloas)
  - [Configuration](#configuration)
  - [Containers](#containers)
    - [Modified `DataColumnSidecar`](#modified-datacolumnsidecar)
    - [New `ProposerPreferences`](#new-proposerpreferences)
    - [New `SignedProposerPreferences`](#new-signedproposerpreferences)
  - [Helpers](#helpers)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)
    - [Modified `verify_data_column_sidecar_kzg_proofs`](#modified-verify_data_column_sidecar_kzg_proofs)
    - [Modified `verify_data_column_sidecar`](#modified-verify_data_column_sidecar)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [`beacon_aggregate_and_proof`](#beacon_aggregate_and_proof)
        - [`beacon_block`](#beacon_block)
        - [`execution_payload`](#execution_payload)
        - [`payload_attestation_message`](#payload_attestation_message)
        - [`execution_payload_bid`](#execution_payload_bid)
        - [`proposer_preferences`](#proposer_preferences)
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

This document contains the consensus-layer networking specifications for Gloas.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

## Modification in Gloas

### Configuration

| Name                   | Value          | Description                                                       |
| ---------------------- | -------------- | ----------------------------------------------------------------- |
| `MAX_REQUEST_PAYLOADS` | `2**7` (= 128) | Maximum number of execution payload envelopes in a single request |

### Containers

#### Modified `DataColumnSidecar`

*Note*: The `signed_block_header`, `kzg_commitments`, and
`kzg_commitments_inclusion_proof` fields have been removed from
`DataColumnSidecar` in Gloas as header and inclusion proof verifications are no
longer required in Gloas. The KZG commitments are now located at
`block.body.signed_execution_payload_bid.message.blob_kzg_commitments` where
`block` is the `BeaconBlock` associated with `beacon_block_root`.

```python
class DataColumnSidecar(Container):
    index: ColumnIndex
    column: List[Cell, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    # [Modified in Gloas:EIP7732]
    # Removed `kzg_commitments`
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

#### New `ProposerPreferences`

*[New in Gloas:EIP7732]*

```python
class ProposerPreferences(Container):
    proposal_slot: Slot
    validator_index: ValidatorIndex
    fee_recipient: ExecutionAddress
    gas_limit: uint64
```

#### New `SignedProposerPreferences`

*[New in Gloas:EIP7732]*

```python
class SignedProposerPreferences(Container):
    message: ProposerPreferences
    signature: BLSSignature
```

### Helpers

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

#### Modified `verify_data_column_sidecar_kzg_proofs`

```python
def verify_data_column_sidecar_kzg_proofs(
    sidecar: DataColumnSidecar,
    # [New in Gloas:EIP7732]
    kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK],
) -> bool:
    """
    Verify if the KZG proofs are correct.
    """
    # The column index also represents the cell index
    cell_indices = [CellIndex(sidecar.index)] * len(sidecar.column)

    # Batch verify that the cells match the corresponding commitments and proofs
    return verify_cell_kzg_proof_batch(
        # [Modified in Gloas:EIP7732]
        commitments_bytes=kzg_commitments,
        cell_indices=cell_indices,
        cells=sidecar.column,
        proofs_bytes=sidecar.kzg_proofs,
    )
```

#### Modified `verify_data_column_sidecar`

```python
def verify_data_column_sidecar(
    sidecar: DataColumnSidecar,
    # [New in Gloas:EIP7732]
    kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK],
) -> bool:
    """
    Verify if the data column sidecar is valid.
    """
    # The sidecar index must be within the valid range
    if sidecar.index >= NUMBER_OF_COLUMNS:
        return False

    # [Modified in Gloas:EIP7732]
    # A sidecar for zero blobs is invalid
    if len(sidecar.column) == 0:
        return False

    # [Modified in Gloas:EIP7732]
    # The column length must be equal to the number of commitments/proofs
    if len(sidecar.column) != len(kzg_commitments) or len(sidecar.column) != len(
        sidecar.kzg_proofs
    ):
        return False

    return True
```

### The gossip domain: gossipsub

Some gossip meshes are upgraded in Gloas to support upgraded types.

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
| `proposer_preferences`        | `SignedProposerPreferences`      |

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
`SignedBeaconBlock` found in [the beacon-chain changes](./beacon-chain.md).

There are no new validations for this topic. However, all validations with
regards to the `ExecutionPayload` are removed:

- _[REJECT]_ The length of KZG commitments is less than or equal to the
  limitation defined in the consensus layer -- i.e. validate that
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

- _[REJECT]_ The length of KZG commitments is less than or equal to the
  limitation defined in the consensus layer -- i.e. validate that
  `len(bid.blob_kzg_commitments) <= get_blob_parameters(get_current_epoch(state)).max_blobs_per_block`
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
  `payload_attestation_message.validator_index`.
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

- _[IGNORE]_ `bid.slot` is the current slot or the next slot.
- _[IGNORE]_ the `SignedProposerPreferences` where `preferences.proposal_slot`
  is equal to `bid.slot` has been seen.
- _[REJECT]_ `bid.builder_index` is a valid/active builder index -- i.e.
  `is_active_builder(state, bid.builder_index)` returns `True`.
- _[REJECT]_ `bid.execution_payment` is zero.
- _[REJECT]_ `bid.fee_recipient` matches the `fee_recipient` from the proposer's
  `SignedProposerPreferences` associated with `bid.slot`.
- _[REJECT]_ `bid.gas_limit` matches the `gas_limit` from the proposer's
  `SignedProposerPreferences` associated with `bid.slot`.
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
- _[REJECT]_ `signed_execution_payload_bid.signature` is valid with respect to
  the `bid.builder_index`.

*Note*: Implementations SHOULD include DoS prevention measures to mitigate spam
from malicious builders submitting numerous bids with minimal value increments.
Possible strategies include: (1) only forwarding bids that exceed the current
highest bid by a minimum threshold, or (2) forwarding only the highest observed
bid at regular time intervals.

###### `proposer_preferences`

*[New in Gloas:EIP7732]*

This topic is used to propagate signed proposer preferences as
`SignedProposerPreferences`. These messages allow validators to communicate
their preferred `fee_recipient` and `gas_limit` to builders.

The following validations MUST pass before forwarding the
`signed_proposer_preferences` on the network, assuming the alias
`preferences = signed_proposer_preferences.message`:

- _[IGNORE]_ `preferences.proposal_slot` is in the next epoch -- i.e.
  `compute_epoch_at_slot(preferences.proposal_slot) == get_current_epoch(state) + 1`.
- _[REJECT]_ `preferences.validator_index` is present at the correct slot in the
  next epoch's portion of `state.proposer_lookahead` -- i.e.
  `is_valid_proposal_slot(state, preferences)` returns `True`.
- _[IGNORE]_ The `signed_proposer_preferences` is the first valid message
  received from the validator with index `preferences.validator_index`.
- _[REJECT]_ `signed_proposer_preferences.signature` is valid with respect to
  the validator's public key.

```python
def is_valid_proposal_slot(state: BeaconState, preferences: ProposerPreferences) -> bool:
    """
    Check if the validator is the proposer for the given slot in the next epoch.
    """
    index = SLOTS_PER_EPOCH + preferences.proposal_slot % SLOTS_PER_EPOCH
    return state.proposer_lookahead[index] == preferences.validator_index
```

##### Blob subnets

###### `data_column_sidecar_{subnet_id}`

*[Modified in Gloas:EIP7732]*

The following validations MUST pass before forwarding the
`sidecar: DataColumnSidecar` on the network, assuming the alias
`bid = block.body.signed_execution_payload_bid.message` where `block` is the
`BeaconBlock` associated with `sidecar.beacon_block_root`:

- _[IGNORE]_ The sidecar's `beacon_block_root` has been seen via a valid signed
  execution payload bid. A client MAY queue the sidecar for processing once the
  block is retrieved.
- _[REJECT]_ The sidecars's `slot` matches the slot of the block with root
  `beacon_block_root`.
- _[REJECT]_ The sidecar is valid as verified by
  `verify_data_column_sidecar(sidecar, bid.blob_kzg_commitments)`.
- _[REJECT]_ The sidecar is for the correct subnet -- i.e.
  `compute_subnet_for_data_column_sidecar(sidecar.index) == subnet_id`.
- _[REJECT]_ The sidecar's column data is valid as verified by
  `verify_data_column_sidecar_kzg_proofs(sidecar, bid.blob_kzg_commitments)`.
- _[IGNORE]_ The sidecar is the first sidecar for the tuple
  `(sidecar.beacon_block_root, sidecar.index)` with valid kzg proof.

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
