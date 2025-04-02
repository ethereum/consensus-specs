# EIP-7732 -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Modification in EIP-7732](#modification-in-eip-7732)
  - [Preset](#preset)
  - [Configuration](#configuration)
  - [Containers](#containers)
    - [`BlobSidecar`](#blobsidecar)
    - [Helpers](#helpers)
      - [Modified `verify_blob_sidecar_inclusion_proof`](#modified-verify_blob_sidecar_inclusion_proof)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [`beacon_block`](#beacon_block)
        - [`execution_payload`](#execution_payload)
        - [`payload_attestation_message`](#payload_attestation_message)
        - [`execution_payload_header`](#execution_payload_header)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [BeaconBlocksByRange v2](#beaconblocksbyrange-v2)
      - [BeaconBlocksByRoot v2](#beaconblocksbyroot-v2)
      - [BlobSidecarsByRoot v1](#blobsidecarsbyroot-v1)
      - [ExecutionPayloadEnvelopesByRange v1](#executionpayloadenvelopesbyrange-v1)
      - [ExecutionPayloadEnvelopesByRoot v1](#executionpayloadenvelopesbyroot-v1)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document contains the consensus-layer networking specification for EIP7732.

The specification of these changes continues in the same format as the network specifications of previous upgrades, and assumes them as pre-requisite.

## Modification in EIP-7732

### Preset

*[Modified in EIP-7732]*

| Name                                           | Value        | Description                                                 |
|------------------------------------------------|--------------|-------------------------------------------------------------|
| `KZG_COMMITMENT_INCLUSION_PROOF_DEPTH_EIP7732` | `13` **TBD** | Merkle proof depth for the `blob_kzg_commitments` list item |

### Configuration

*[New in EIP7732]*

| Name                   | Value          | Description                                                       |
|------------------------|----------------|-------------------------------------------------------------------|
| `MAX_REQUEST_PAYLOADS` | `2**7` (= 128) | Maximum number of execution payload envelopes in a single request |

### Containers

#### `BlobSidecar`

The `BlobSidecar` container is modified indirectly because the constant `KZG_COMMITMENT_INCLUSION_PROOF_DEPTH` is modified.

```python
class BlobSidecar(Container):
    index: BlobIndex  # Index of blob in block
    blob: Blob
    kzg_commitment: KZGCommitment
    kzg_proof: KZGProof  # Allows for quick verification of kzg_commitment
    signed_block_header: SignedBeaconBlockHeader
    kzg_commitment_inclusion_proof: Vector[Bytes32, KZG_COMMITMENT_INCLUSION_PROOF_DEPTH_EIP7732]
```

#### Helpers

##### Modified `verify_blob_sidecar_inclusion_proof`

`verify_blob_sidecar_inclusion_proof` is modified in EIP-7732 to account for the fact that the KZG commitments are included in the `ExecutionPayloadEnvelope` and no longer in the beacon block body.

```python
def verify_blob_sidecar_inclusion_proof(blob_sidecar: BlobSidecar) -> bool:
    inner_gindex = get_generalized_index(
        List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK],
        blob_sidecar.index
    )
    outer_gindex = get_generalized_index(
        BeaconBlockBody,
        "signed_execution_payload_header",
        "message",
        "blob_kzg_commitments_root",
    )
    gindex = get_subtree_index(concat_generalized_indices(outer_gindex, inner_gindex))

    return is_valid_merkle_branch(
        leaf=blob_sidecar.kzg_commitment.hash_tree_root(),
        branch=blob_sidecar.kzg_commitment_inclusion_proof,
        depth=KZG_COMMITMENT_INCLUSION_PROOF_DEPTH_EIP7732,
        index=gindex,
        root=blob_sidecar.signed_block_header.message.body_root,
    )
```

### The gossip domain: gossipsub

Some gossip meshes are upgraded in the fork of EIP-7732 to support upgraded types.

#### Topics and messages

Topics follow the same specification as in prior upgrades.

The `beacon_block` topic is updated to support the modified type

| Name           | Message Type                               |
|----------------|--------------------------------------------|
| `beacon_block` | `SignedBeaconBlock` [modified in EIP-7732] |

The new topics along with the type of the `data` field of a gossipsub message are given in this table:

| Name                          | Message Type                                         |
|-------------------------------|------------------------------------------------------|
| `execution_payload_header`    | `SignedExecutionPayloadHeader` [New in EIP-7732] |
| `execution_payload`           | `SignedExecutionPayloadEnvelope` [New in EIP-7732]       |
| `payload_attestation_message` | `PayloadAttestationMessage` [New in EIP-7732]            |

##### Global topics

EIP-7732 introduces new global topics for execution header, execution payload and payload attestation.

###### `beacon_block`

[Modified in EIP-7732]

The *type* of the payload of this topic changes to the (modified) `SignedBeaconBlock` found in [the Beacon Chain changes](./beacon-chain.md).

There are no new validations for this topic. However, all validations with regards to the `ExecutionPayload` are removed:

- _[REJECT]_ The length of KZG commitments is less than or equal to the limitation defined in Consensus Layer -- i.e. validate that `len(signed_beacon_block.message.body.blob_kzg_commitments) <= MAX_BLOBS_PER_BLOCK`
- _[REJECT]_ The block's execution payload timestamp is correct with respect to the slot
       -- i.e. `execution_payload.timestamp == compute_timestamp_at_slot(state, block.slot)`.
- If `execution_payload` verification of block's parent by an execution node is *not* complete:
    - [REJECT] The block's parent (defined by `block.parent_root`) passes all validation (excluding execution node verification of the `block.body.execution_payload`).
- otherwise:
    - [IGNORE] The block's parent (defined by `block.parent_root`) passes all validation (including execution node verification of the `block.body.execution_payload`).
- [REJECT] The block's parent (defined by `block.parent_root`) passes validation.

And instead the following validations are set in place with the alias `header = signed_execution_payload_header.message`:

- If `execution_payload` verification of block's execution payload parent by an execution node **is complete**:
    - [REJECT] The block's execution payload parent (defined by `header.parent_block_hash`) passes all validation.
- [REJECT] The block's parent (defined by `block.parent_root`) passes validation.

###### `execution_payload`

This topic is used to propagate execution payload messages as `SignedExecutionPayloadEnvelope`.

The following validations MUST pass before forwarding the `signed_execution_payload_envelope` on the network, assuming the alias `envelope = signed_execution_payload_envelope.message`, `payload = payload_envelope.payload`:

- _[IGNORE]_ The envelope's block root `envelope.block_root` has been seen (via gossip or non-gossip sources) (a client MAY queue payload for processing once the block is retrieved).
- _[IGNORE]_ The node has not seen another valid `SignedExecutionPayloadEnvelope` for this block root from this builder.

Let `block` be the block with `envelope.beacon_block_root`.
Let `header` alias `block.body.signed_execution_payload_header.message` (notice that this can be obtained from the `state.signed_execution_payload_header`)

- _[REJECT]_ `block` passes validation.
- _[REJECT]_ `envelope.builder_index == header.builder_index`
- if `envelope.payload_withheld == False` then
    - _[REJECT]_ `payload.block_hash == header.block_hash`
- _[REJECT]_ The builder signature, `signed_execution_payload_envelope.signature`, is valid with respect to the builder's public key.

###### `payload_attestation_message`

This topic is used to propagate signed payload attestation message.

The following validations MUST pass before forwarding the `payload_attestation_message` on the network, assuming the alias `data = payload_attestation_message.data`:

- _[IGNORE]_ The message's slot is for the current slot (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance), i.e. `data.slot == current_slot`.
- _[REJECT]_ The message's payload status is a valid status, i.e. `data.payload_status < PAYLOAD_INVALID_STATUS`.
- _[IGNORE]_ The `payload_attestation_message` is the first valid message received from the validator with index `payload_attestation_message.validate_index`.
- _[IGNORE]_ The message's block `data.beacon_block_root` has been seen (via gossip or non-gossip sources) (a client MAY queue attestation for processing once the block is retrieved. Note a client might want to request payload after).
- _[REJECT]_ The message's block `data.beacon_block_root` passes validation.
- _[REJECT]_ The message's validator index is within the payload committee in `get_ptc(state, data.slot)`. The `state` is the head state corresponding to processing the block up to the current slot as determined by the fork choice.
- _[REJECT]_ The message's signature of `payload_attestation_message.signature` is valid with respect to the validator index.

###### `execution_payload_header`

This topic is used to propagate signed bids as `SignedExecutionPayloadHeader`.

The following validations MUST pass before forwarding the `signed_execution_payload_header` on the network, assuming the alias `header = signed_execution_payload_header.message`:

- _[IGNORE]_ this is the first signed bid seen with a valid signature from the given builder for this slot.
- _[IGNORE]_ this bid is the highest value bid seen for the pair of the corresponding slot and the given parent block hash.
- _[REJECT]_ The signed builder bid, `header.builder_index` is a valid, active, and non-slashed builder index in state.
- _[IGNORE]_ The signed builder bid value, `header.value`, is less or equal than the builder's balance in state.  i.e. `MIN_BUILDER_BALANCE + header.value < state.builder_balances[header.builder_index]`.
- _[IGNORE]_ `header.parent_block_hash` is the block hash of a known execution payload in fork choice.
_ _[IGNORE]_ `header.parent_block_root` is the hash tree root of a known beacon block in fork choice.
- _[IGNORE]_ `header.slot` is the current slot or the next slot.
- _[REJECT]_ The builder signature, `signed_execution_payload_header_envelope.signature`, is valid with respect to the `header_envelope.builder_index`.

### The Req/Resp domain

#### Messages

##### BeaconBlocksByRange v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/2/`

<!-- eth2spec: skip -->

| `fork_version`           | Chunk SSZ type                |
|--------------------------|-------------------------------|
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock`   |
| `DENEB_FORK_VERSION`     | `deneb.SignedBeaconBlock`     |
| `EIP7732_FORK_VERSION`   | `eip7732.SignedBeaconBlock`   |

##### BeaconBlocksByRoot v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_root/2/`

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

<!-- eth2spec: skip -->

| `fork_version`           | Chunk SSZ type                |
|--------------------------|-------------------------------|
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock`   |
| `DENEB_FORK_VERSION`     | `deneb.SignedBeaconBlock`     |
| `EIP7732_FORK_VERSION`   | `eip7732.SignedBeaconBlock`   |

##### BlobSidecarsByRoot v1

**Protocol ID:** `/eth2/beacon_chain/req/blob_sidecars_by_root/1/`

<!-- eth2spec: skip -->

| `fork_version`           | Chunk SSZ type                |
|--------------------------|-------------------------------|
| `DENEB_FORK_VERSION`     | `deneb.BlobSidecar`           |
| `EIP7732_FORK_VERSION`   | `eip7732.BlobSidecar`         |

##### ExecutionPayloadEnvelopesByRange v1

**Protocol ID:** `/eth2/beacon_chain/req/execution_payload_envelopes_by_range/1/`

*[New in EIP-7732]*

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

Specifications of req\response methods are equivalent to [BeaconBlocksByRange v2](#beaconblocksbyrange-v2), with the only difference being the response content type.

For each `response_chunk`, a `ForkDigest`-context based on `compute_fork_version(compute_epoch_at_slot(signed_execution_payload_envelop.message.slot))` is used to select the fork namespace of the Response type.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

<!-- eth2spec: skip -->

| `fork_version`         | Chunk SSZ type                           |
|------------------------|------------------------------------------|
| `EIP7732_FORK_VERSION` | `eip7732.SignedExecutionPayloadEnvelope` |

##### ExecutionPayloadEnvelopesByRoot v1

**Protocol ID:** `/eth2/beacon_chain/req/execution_payload_envelopes_by_root/1/`

The `<context-bytes>` field is calculated as `context = compute_fork_digest(fork_version, genesis_validators_root)`:

<!-- eth2spec: skip -->

| `fork_version`         | Chunk SSZ type                           |
|------------------------|------------------------------------------|
| `EIP7732_FORK_VERSION` | `eip7732.SignedExecutionPayloadEnvelope` |

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

Requests execution payload envelopes by `signed_execution_payload_envelope.message.block_root`. The response is a list of `SignedExecutionPayloadEnvelope` whose length is less than or equal to the number of requested execution payload envelopes. It may be less in the case that the responding peer is missing payload envelopes.

No more than `MAX_REQUEST_PAYLOADS` may be requested at a time.

ExecutionPayloadEnvelopesByRoot is primarily used to recover recent execution payload envelopes (e.g. when receiving a payload attestation with revealed status as true but never received a payload).

The request MUST be encoded as an SSZ-field.

The response MUST consist of zero or more `response_chunk`. Each successful `response_chunk` MUST contain a single `SignedExecutionPayloadEnvelope` payload.

Clients MUST support requesting payload envelopes since the latest finalized epoch.

Clients MUST respond with at least one payload envelope, if they have it. Clients MAY limit the number of payload envelopes in the response.
