# Ethereum 2.0 The Merge

**Warning:** This document is currently based on [Phase 0](../phase0/validator.md) but will be rebased to [Altair](../altair/validator.md) once the latter is shipped.

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
      - [Application Payload](#application-payload)
        - [`get_pow_chain_head`](#get_pow_chain_head)
        - [`produce_application_payload`](#produce_application_payload)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- /TOC -->

## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement executable beacon chain proposal.

## Prerequisites

This document is an extension of the [Phase 0 -- Validator](../phase0/validator.md). All behaviors and definitions defined in the Phase 0 doc carry over unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the updated Beacon Chain doc of [The Merge](./beacon-chain.md) are requisite for this document and used throughout. Please see related Beacon Chain doc before continuing and use them as a reference throughout.

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below. Namely, the transition block handling and the addition of `ApplicationPayload`.

### Block proposal

#### Constructing the `BeaconBlockBody`

##### Application Payload

###### `get_pow_chain_head`

Let `get_pow_chain_head() -> PowBlock` be the function that returns the head of the PoW chain. The body of the function is implementation specific.

###### `produce_application_payload`

Let `produce_application_payload(parent_hash: Bytes32) -> ApplicationPayload` be the function that produces new instance of application payload.
The body of this function is implementation dependent.

- Set `block.body.application_payload = get_application_payload(state)` where:

```python
def get_application_payload(state: BeaconState) -> ApplicationPayload:
    if not is_transition_completed(state):
        pow_block = get_pow_chain_head()
        if pow_block.total_difficulty < TRANSITION_TOTAL_DIFFICULTY:
            # Pre-merge, empty payload
            return ApplicationPayload()
        else:
            # Signify merge via last PoW block_hash and an otherwise empty payload
            return ApplicationPayload(block_hash=pow_block.block_hash)

    # Post-merge, normal payload
    application_parent_hash = state.application_block_hash
    return produce_application_payload(state.application_block_hash)
```
