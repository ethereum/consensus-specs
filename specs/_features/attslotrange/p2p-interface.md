# AttSlotRange -- Networking

This document contains the consensus-layer networking specification for AttSlotRange.

The specification of these changes continues in the same format as the network specifications of previous upgrades, and assumes them as pre-requisite.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Modifications in AttSlotRange](#modifications-in-attslotrange)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [`beacon_aggregate_and_proof`](#beacon_aggregate_and_proof)
    - [Attestation subnets](#attestation-subnets)
      - [`beacon_attestation_{subnet_id}](#beacon_attestation_subnet_id)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Modifications in AttSlotRange

### The gossip domain: gossipsub

#### Topics and messages

Topics follow the same specification as in prior upgrades.

The `beacon_aggregate_and_proof` and `beacon_attestation_{subnet_id}` topics are modified to support the gossip of attestations created in epoch `N` to be gossiped through the entire range of slots in epoch `N+1` rather than only through one epoch of slots.

Otherwise, the specification around the creation, validation, and dissemination of messages has not changed from the Deneb document unless explicitly noted here.

The derivation of the `message-id` remains stable.

##### Global topics

Deneb introduces new global topics for blob sidecars.

###### `beacon_aggregate_and_proof`

The following validation is removed:
* _[IGNORE]_ `aggregate.data.slot` is within the last `ATTESTATION_PROPAGATION_SLOT_RANGE` slots (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) --
  i.e. `aggregate.data.slot + ATTESTATION_PROPAGATION_SLOT_RANGE >= current_slot >= aggregate.data.slot`
  (a client MAY queue future aggregates for processing at the appropriate slot).

The following validations are added in its place:
* _[IGNORE]_ `aggregate.data.slot` is equal to or earlier than the `current_slot` (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) --
  i.e. `aggregate.data.slot <= current_slot`
  (a client MAY queue future aggregates for processing at the appropriate slot).
* _[IGNORE]_ the epoch of `aggregate.data.slot` is either the current or previous epoch
  (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) --
  i.e. `compute_epoch_at_slot(aggregate.data.slot) in (get_previous_epoch(state), get_current_epoch(state))`

#### Attestation subnets

##### `beacon_attestation_{subnet_id}

The following validation is removed:
* _[IGNORE]_ `attestation.data.slot` is within the last `ATTESTATION_PROPAGATION_SLOT_RANGE` slots (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) --
  i.e. `attestation.data.slot + ATTESTATION_PROPAGATION_SLOT_RANGE >= current_slot >= attestation.data.slot`
  (a client MAY queue future attestations for processing at the appropriate slot).

The following validations are added in its place:
* _[IGNORE]_ `attestation.data.slot` is equal to or earlier than the `current_slot` (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) --
  i.e. `attestation.data.slot <= current_slot`
  (a client MAY queue future attestation for processing at the appropriate slot).
* _[IGNORE]_ the epoch of `attestation.data.slot` is either the current or previous epoch
  (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) --
  i.e. `compute_epoch_at_slot(attestation.data.slot) in (get_previous_epoch(state), get_current_epoch(state))`
