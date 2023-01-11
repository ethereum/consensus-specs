# Capella -- Networking

This document contains the networking specification for Capella.

The specification of these changes continues in the same format as the network specifications of previous upgrades, and assumes them as pre-requisite.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Modifications in Capella](#modifications-in-capella)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [`beacon_block`](#beacon_block)
        - [`bls_to_execution_change`](#bls_to_execution_change)
    - [Transitioning the gossip](#transitioning-the-gossip)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [BeaconBlocksByRange v2](#beaconblocksbyrange-v2)
      - [BeaconBlocksByRoot v2](#beaconblocksbyroot-v2)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->


# Modifications in Capella

## The gossip domain: gossipsub

A new topic is added to support the gossip of withdrawal credential change messages. And an existing topic is upgraded for updated types in Capella.

### Topics and messages

Topics follow the same specification as in prior upgrades. All existing topics remain stable except the beacon block topic which is updated with the modified type.

The new topics along with the type of the `data` field of a gossipsub message are given in this table:

| Name | Message Type |
| - | - |
| `beacon_block` | `SignedBeaconBlock` (modified) |
| `bls_to_execution_change` | `SignedBLSToExecutionChange` |

Note that the `ForkDigestValue` path segment of the topic separates the old and the new `beacon_block` topics.

#### Global topics

Capella changes the type of the global beacon block topic and adds one global topic to propagate withdrawal credential change messages to all potential proposers of beacon blocks.

##### `beacon_block`

The *type* of the payload of this topic changes to the (modified) `SignedBeaconBlock` found in Capella.
Specifically, this type changes with the addition of `bls_to_execution_changes` to the inner `BeaconBlockBody`.
See Capella [state transition document](./beacon-chain.md#beaconblockbody) for further details.

##### `bls_to_execution_change`

This topic is used to propagate signed bls to execution change messages to be included in future blocks.

The following validations MUST pass before forwarding the `signed_bls_to_execution_change` on the network:

- _[IGNORE]_ The `signed_bls_to_execution_change` is the first valid signed bls to execution change received
  for the validator with index `signed_bls_to_execution_change.message.validator_index`.
- _[REJECT]_ All of the conditions within `process_bls_to_execution_change` pass validation.

### Transitioning the gossip

See gossip transition details found in the [Altair document](../altair/p2p-interface.md#transitioning-the-gossip) for
details on how to handle transitioning gossip topics for Capella.

## The Req/Resp domain

### Messages

#### BeaconBlocksByRange v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/2/`

The Capella fork-digest is introduced to the `context` enum to specify Capella block type.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

[0]: # (eth2spec: skip)

| `fork_version`           | Chunk SSZ type             |
| ------------------------ | -------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock` |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock` |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock` |

#### BeaconBlocksByRoot v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_root/2/`

The Capella fork-digest is introduced to the `context` enum to specify Capella block type.

Per `context = compute_fork_digest(fork_version, genesis_validators_root)`:

[1]: # (eth2spec: skip)

| `fork_version`           | Chunk SSZ type             |
| ------------------------ | -------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock` |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock` |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock` |

