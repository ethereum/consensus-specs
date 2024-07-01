# Electra -- Networking

This document contains the consensus-layer networking specification for Electra.

The specification of these changes continues in the same format as the network specifications of previous upgrades, and assumes them as pre-requisite.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Modifications in Electra](#modifications-in-electra)
  - [MetaData](#metadata)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
    - [Global topics](#global-topics)
      - [`beacon_aggregate_and_proof`](#beacon_aggregate_and_proof)
      - [`beacon_attestation_{subnet_id}`](#beacon_attestation_subnet_id)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [GetMetaData v3](#getmetadata-v3)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Modifications in Electra

### MetaData

The `MetaData` stored locally by clients is updated with an additional field to communicate the custody subnet count.

```
(
  seq_number: uint64
  attnets: Bitvector[ATTESTATION_SUBNET_COUNT]
  syncnets: Bitvector[SYNC_COMMITTEE_SUBNET_COUNT]
  custody_subnet_count: uint64
)
```

Where

- `seq_number`, `attnets`, and `syncnets` have the same meaning defined in the Altair document.
- `custody_subnet_count` represents the node's custody subnet count. Clients MAY reject ENRs with a value less than `CUSTODY_REQUIREMENT`.

### The gossip domain: gossipsub

Some gossip meshes are upgraded in the fork of Electra to support upgraded types.

#### Topics and messages

Topics follow the same specification as in prior upgrades.

The `beacon_block` topic is modified to also support Electra blocks.

The `beacon_aggregate_and_proof` and `beacon_attestation_{subnet_id}` topics are modified to support the gossip of the new attestation type.

The specification around the creation, validation, and dissemination of messages has not changed from the Capella document unless explicitly noted here.

The derivation of the `message-id` remains stable.

#### Global topics

##### `beacon_aggregate_and_proof`

The following convenience variables are re-defined
- `index = get_committee_indices(aggregate.committee_bits)[0]`

The following validations are added:
* [REJECT] `len(committee_indices) == 1`, where `committee_indices = get_committee_indices(aggregate)`.
* [REJECT] `aggregate.data.index == 0`

##### `beacon_attestation_{subnet_id}`

The following convenience variables are re-defined
- `index = get_committee_indices(attestation.committee_bits)[0]`

The following validations are added:
* [REJECT] `len(committee_indices) == 1`, where `committee_indices = get_committee_indices(attestation)`.
* [REJECT] `attestation.data.index == 0`

### The Req/Resp domain

#### Messages

##### GetMetaData v3

**Protocol ID:** `/eth2/beacon_chain/req/metadata/3/`

No Request Content.

Response Content:

```
(
  MetaData
)
```

Requests the MetaData of a peer, using the new `MetaData` definition given above that is extended from Altair. Other conditions for the `GetMetaData` protocol are unchanged from the Altair p2p networking document.
