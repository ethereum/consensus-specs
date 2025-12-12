# Electra -- Networking

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modifications in Electra](#modifications-in-electra)
  - [Helper functions](#helper-functions)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)
  - [Configuration](#configuration)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [`beacon_block`](#beacon_block)
        - [`beacon_aggregate_and_proof`](#beacon_aggregate_and_proof)
        - [`blob_sidecar_{subnet_id}`](#blob_sidecar_subnet_id)
      - [Attestation subnets](#attestation-subnets)
        - [`beacon_attestation_{subnet_id}`](#beacon_attestation_subnet_id)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [BeaconBlocksByRange v2](#beaconblocksbyrange-v2)
      - [BeaconBlocksByRoot v2](#beaconblocksbyroot-v2)
      - [BlobSidecarsByRange v1](#blobsidecarsbyrange-v1)
      - [BlobSidecarsByRoot v1](#blobsidecarsbyroot-v1)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specification for Electra.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

## Modifications in Electra

### Helper functions

#### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
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

*[New in Electra:EIP7691]*

| Name                                | Value                                                    | Description                                                       |
| ----------------------------------- | -------------------------------------------------------- | ----------------------------------------------------------------- |
| `MAX_REQUEST_BLOB_SIDECARS_ELECTRA` | `MAX_REQUEST_BLOCKS_DENEB * MAX_BLOBS_PER_BLOCK_ELECTRA` | Maximum number of blob sidecars in a single request               |
| `BLOB_SIDECAR_SUBNET_COUNT_ELECTRA` | `9`                                                      | The number of blob sidecar subnets used in the gossipsub protocol |

### The gossip domain: gossipsub

Some gossip meshes are upgraded in the fork of Electra to support upgraded
types.

#### Topics and messages

Topics follow the same specification as in prior upgrades.

The `beacon_block` topic is modified to also support Electra blocks.

The `beacon_aggregate_and_proof` and `beacon_attestation_{subnet_id}` topics are
modified to support the gossip of the new attestation type.

The `attester_slashing` topic is modified to support the gossip of the new
`AttesterSlashing` type.

The specification around the creation, validation, and dissemination of messages
has not changed from the Capella document unless explicitly noted here.

The derivation of the `message-id` remains stable.

##### Global topics

###### `beacon_block`

*Updated validation*

- _[REJECT]_ The length of KZG commitments is less than or equal to the
  limitation defined in Consensus Layer -- i.e. validate that
  `len(signed_beacon_block.message.body.blob_kzg_commitments) <= MAX_BLOBS_PER_BLOCK_ELECTRA`

###### `beacon_aggregate_and_proof`

Assuming the alias `aggregate = signed_aggregate_and_proof.message.aggregate`:

The following convenience variables are re-defined:

- `index = get_committee_indices(aggregate.committee_bits)[0]`

The following validations are added:

- [REJECT] `len(committee_indices) == 1`, where
  `committee_indices = get_committee_indices(aggregate.committee_bits)`.
- [REJECT] `aggregate.data.index == 0`

###### `blob_sidecar_{subnet_id}`

*[Modified in Electra:EIP7691]*

The existing validations all apply as given from previous forks, with the
following exceptions:

- Uses of `MAX_BLOBS_PER_BLOCK` in existing validations are replaced with
  `MAX_BLOBS_PER_BLOCK_ELECTRA`.

##### Attestation subnets

###### `beacon_attestation_{subnet_id}`

The topic is updated to propagate `SingleAttestation` objects.

The following convenience variables are re-defined:

- `index = attestation.committee_index`

The following validations are added:

- _[REJECT]_ `attestation.data.index == 0`
- _[REJECT]_ The attester is a member of the committee -- i.e.
  `attestation.attester_index in get_beacon_committee(state, attestation.data.slot, index)`.

The following validations are removed:

- _[REJECT]_ The attestation is unaggregated -- that is, it has exactly one
  participating validator (`len([bit for bit in aggregation_bits if bit]) == 1`,
  i.e. exactly 1 bit is set).
- _[REJECT]_ The number of aggregation bits matches the committee size -- i.e.
  `len(aggregation_bits) == len(get_beacon_committee(state, attestation.data.slot, index))`.

### The Req/Resp domain

#### Messages

##### BeaconBlocksByRange v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/2/`

The Electra fork-digest is introduced to the `context` enum to specify Electra
beacon block type.

<!-- eth2spec: skip -->

| `fork_version`           | Chunk SSZ type                |
| ------------------------ | ----------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock`   |
| `DENEB_FORK_VERSION`     | `deneb.SignedBeaconBlock`     |
| `ELECTRA_FORK_VERSION`   | `electra.SignedBeaconBlock`   |

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

##### BlobSidecarsByRange v1

**Protocol ID:** `/eth2/beacon_chain/req/blob_sidecars_by_range/1/`

*[Modified in Electra:EIP7691]*

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
  List[BlobSidecar, MAX_REQUEST_BLOB_SIDECARS_ELECTRA]
)
```

*Updated validation*

Clients MUST respond with at least the blob sidecars of the first blob-carrying
block that exists in the range, if they have it, and no more than
`MAX_REQUEST_BLOB_SIDECARS_ELECTRA` sidecars.

##### BlobSidecarsByRoot v1

**Protocol ID:** `/eth2/beacon_chain/req/blob_sidecars_by_root/1/`

*[Modified in Electra:EIP7691]*

Request Content:

```
(
  List[BlobIdentifier, MAX_REQUEST_BLOB_SIDECARS_ELECTRA]
)
```

Response Content:

```
(
  List[BlobSidecar, MAX_REQUEST_BLOB_SIDECARS_ELECTRA]
)
```

*Updated validation*

No more than `MAX_REQUEST_BLOB_SIDECARS_ELECTRA` may be requested at a time.
