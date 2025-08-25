# Gloas -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modification in Gloas](#modification-in-gloas)
  - [Preset](#preset)
  - [Configuration](#configuration)
  - [Containers](#containers)
    - [Modified `DataColumnSidecar`](#modified-datacolumnsidecar)
    - [Helpers](#helpers)
      - [Modified `verify_data_column_sidecar_inclusion_proof`](#modified-verify_data_column_sidecar_inclusion_proof)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [`beacon_aggregate_and_proof`](#beacon_aggregate_and_proof)
        - [`beacon_block`](#beacon_block)
        - [`execution_payload`](#execution_payload)
        - [`payload_attestation_message`](#payload_attestation_message)
        - [`execution_payload_header`](#execution_payload_header)
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

This document contains the consensus-layer networking specification for
GloasGloasGloasGloasGloasGloasGloasGloas.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

## Modification in Gloas

### Preset

*[Modified in Gloas:EIP7732]*

| Name                                          | Value | Description                                                 |
| --------------------------------------------- | ----- | ----------------------------------------------------------- |
| `KZG_COMMITMENTS_INCLUSION_PROOF_DEPTH_GLOAS` | `9`   | Merkle proof depth for the `blob_kzg_commitments` list item |

### Configuration

*[New in Gloas:EIP7732]*

| Name                   | Value          | Description                                                       |
| ---------------------- | -------------- | ----------------------------------------------------------------- |
| `MAX_REQUEST_PAYLOADS` | `2**7` (= 128) | Maximum number of execution payload envelopes in a single request |

### Containers

#### Modified `DataColumnSidecar`

*Note*: The `DataColumnSidecar` container is modified indirectly because the
constant `KZG_COMMITMENTS_INCLUSION_PROOF_DEPTH` is modified.

```python
class DataColumnSidecar(Container):
    index: ColumnIndex
    column: List[Cell, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    kzg_proofs: List[KZGProof, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    signed_block_header: SignedBeaconBlockHeader
    # [Modified in Gloas:EIP7732]
    kzg_commitments_inclusion_proof: Vector[Bytes32, KZG_COMMITMENTS_INCLUSION_PROOF_DEPTH_GLOAS]
```

#### Helpers

##### Modified `verify_data_column_sidecar_inclusion_proof`

`verify_data_column_sidecar_inclusion_proof` is modified in Gloas to account for
the fact that the KZG commitments are included in the `ExecutionPayloadEnvelope`
and no longer in the beacon block body.

```python
def verify_data_column_sidecar_inclusion_proof(sidecar: DataColumnSidecar) -> bool:
    """
    Verify if the given KZG commitments included in the given beacon block.
    """
    return is_valid_merkle_branch(
        leaf=hash_tree_root(sidecar.kzg_commitments),
        branch=sidecar.kzg_commitments_inclusion_proof,
        # [Modified in Gloas:EIP7732]
        depth=KZG_COMMITMENTS_INCLUSION_PROOF_DEPTH_GLOAS,
        # [Modified in Gloas:EIP7732]
        index=get_subtree_index(
            get_generalized_index(
                BeaconBlockBody,
                "signed_execution_payload_header",
                "message",
                "blob_kzg_commitments_root",
            )
        ),
        root=sidecar.signed_block_header.message.body_root,
    )
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
| `execution_payload_header`    | `SignedExecutionPayloadHeader`   |
| `execution_payload`           | `SignedExecutionPayloadEnvelope` |
| `payload_attestation_message` | `PayloadAttestationMessage`      |

##### Global topics

Gloas introduces new global topics for execution header, execution payload and
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
- [REJECT] The block's parent (defined by `block.parent_root`) passes
  validation.

And instead the following validations are set in place with the alias
`header = signed_execution_payload_header.message`:

- If `execution_payload` verification of block's execution payload parent by an
  execution node **is complete**:
  - [REJECT] The block's execution payload parent (defined by
    `header.parent_block_hash`) passes all validation.
- [REJECT] The block's parent (defined by `block.parent_root`) passes
  validation.

###### `execution_payload`

This topic is used to propagate execution payload messages as
`SignedExecutionPayloadEnvelope`.

The following validations MUST pass before forwarding the
`signed_execution_payload_envelope` on the network, assuming the alias
`envelope = signed_execution_payload_envelope.message`,
`payload = payload_envelope.payload`:

- _[IGNORE]_ The envelope's block root `envelope.block_root` has been seen (via
  gossip or non-gossip sources) (a client MAY queue payload for processing once
  the block is retrieved).
- _[IGNORE]_ The node has not seen another valid
  `SignedExecutionPayloadEnvelope` for this block root from this builder.

Let `block` be the block with `envelope.beacon_block_root`. Let `header` alias
`block.body.signed_execution_payload_header.message` (notice that this can be
obtained from the `state.signed_execution_payload_header`)

- _[REJECT]_ `block` passes validation.
- _[REJECT]_ `block.slot` equals `envelope.slot`.
- _[REJECT]_ `envelope.builder_index == header.builder_index`
- _[REJECT]_ `payload.block_hash == header.block_hash`
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

###### `execution_payload_header`

This topic is used to propagate signed bids as `SignedExecutionPayloadHeader`.

The following validations MUST pass before forwarding the
`signed_execution_payload_header` on the network, assuming the alias
`header = signed_execution_payload_header.message`:

- _[REJECT]_ `header.builder_index` is a valid, active, and non-slashed builder
  index.
- _[REJECT]_ the builder's withdrawal credentials' prefix is
  `BUILDER_WITHDRAWAL_PREFIX` -- i.e.
  `is_builder_withdrawal_credential(state.validators[header.builder_index].withdrawal_credentials)`
  returns `True`.
- _[IGNORE]_ this is the first signed bid seen with a valid signature from the
  given builder for this slot.
- _[IGNORE]_ this bid is the highest value bid seen for the corresponding slot
  and the given parent block hash.
- _[IGNORE]_ `header.value` is less or equal than the builder's excess balance
  -- i.e.
  `MIN_ACTIVATION_BALANCE + header.value <= state.balances[header.builder_index]`.
- _[IGNORE]_ `header.parent_block_hash` is the block hash of a known execution
  payload in fork choice.
- _[IGNORE]_ `header.parent_block_root` is the hash tree root of a known beacon
  block in fork choice.
- _[IGNORE]_ `header.slot` is the current slot or the next slot.
- _[REJECT]_ `signed_execution_payload_header.signature` is valid with respect
  to the `header.builder_index`.

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

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

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

For each `response_chunk`, a `ForkDigest`-context based on
`compute_fork_version(compute_epoch_at_slot(signed_execution_payload_envelop.message.slot))`
is used to select the fork namespace of the Response type.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

<!-- eth2spec: skip -->

| `fork_version`       | Chunk SSZ type                         |
| -------------------- | -------------------------------------- |
| `GLOAS_FORK_VERSION` | `gloas.SignedExecutionPayloadEnvelope` |

##### ExecutionPayloadEnvelopesByRoot v1

**Protocol ID:** `/eth2/beacon_chain/req/execution_payload_envelopes_by_root/1/`

The `<context-bytes>` field is calculated as
`context = compute_fork_digest(fork_version, genesis_validators_root)`:

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
