# Ethereum 2.0 The Merge

**Warning:** This document is based on [Phase 0](../phase0/validator.md) and considered to be rebased to [Altair](../altair/validator.md) once the latter is shipped.

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block proposal](#block-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [Eth1 data](#eth1-data)
        - [`get_eth1_data`](#get_eth1_data)
      - [Application Payload](#application-payload)
        - [`produce_application_payload`](#produce_application_payload)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement executable beacon chain proposal.

## Prerequisites

This document is an extension of the [Phase 0 -- Validator](../phase0/validator.md). All behaviors and definitions defined in the Phase 0 doc carry over unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the updated Beacon Chain doc of [The Merge](./beacon-chain.md) are requisite for this document and used throughout. Please see related Beacon Chain doc before continuing and use them as a reference throughout.

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below. Namely, the modification of `Eth1Data` and the addition of `ApplicationPayload`.

### Block proposal

#### Constructing the `BeaconBlockBody`

##### Eth1 data

The `block.body.eth1_data` field is for block proposers to publish recent Eth1 data. This recent data contains deposit root (as calculated by the `get_deposit_root()` method of the deposit contract) and deposit count after processing of the parent block. The fork choice verifies Eth1 data of a block, then `state.eth1_data` updates immediately allowing new deposits to be processed. Each deposit in `block.body.deposits` must verify against `state.eth1_data.deposit_root`.

###### `get_eth1_data`

Let `get_eth1_data(state: BeaconState) -> Eth1Data` be the function that returns the `Eth1Data` obtained from the beacon state.

*Note*: This is mostly a function of the state of the beacon chain deposit contract. It can be read from the application state and/or logs. The `block_hash` value of `Eth1Data` must be set to `state.application_block_hash`.

Set `block.body.eth1_data = get_eth1_data(state)`.


##### Application Payload

###### `produce_application_payload`

Let `produce_application_payload(parent_hash: Bytes32, beacon_chain_data: BeaconChainData) -> ApplicationPayload` be the function that produces new instance of application payload.
The body of this function is implementation dependant.

* Let `randao_reveal` be `block.body.randao_reveal` of the block that is being produced
* Set `block.body.application_payload = get_application_payload(state, randao_reveal)` where:

```python
def get_application_payload(state: BeaconState, randao_reveal: BLSSignature) -> ApplicationPayload:   
    application_parent_hash = state.application_block_hash
    beacon_chain_data = BeaconChainData(
        slot=state.slot,
        randao_mix=compute_randao_mix(state, randao_reveal),
        timestamp=compute_time_at_slot(state.genesis_time, state.slot),
        recent_block_roots=get_evm_beacon_block_roots(state) 
    )
    
    return produce_application_payload(application_parent_hash, beacon_chain_data)
```
