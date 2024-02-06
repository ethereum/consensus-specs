# EIP-7547 -- Honest Validator

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Helpers](#helpers)
  - [`GetInclusionListResponse`](#getinclusionlistresponse)
- [Protocols](#protocols)
  - [`ExecutionEngine`](#executionengine)
    - [`get_execution_inclusion_list`](#get_execution_inclusion_list)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Inclusion list proposal](#inclusion-list-proposal)
    - [Constructing the inclusion list](#constructing-the-inclusion-list)
    - [Broadcast inclusion list](#broadcast-inclusion-list)
  - [Block and sidecar proposal](#block-and-sidecar-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [ExecutionPayload](#executionpayload)
      - [`inclusion_list_summary`](#inclusion_list_summary)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement EIP-7547.

## Prerequisites

This document is an extension of the [Deneb -- Honest Validator](../../deneb/validator.md) guide.
All behaviors and definitions defined in this document, and documents it extends, carry over unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the updated Beacon Chain doc of [EIP-7547](./beacon-chain.md) are requisite for this document and used throughout.
Please see related Beacon Chain doc before continuing and use them as a reference throughout.

## Helpers

### `GetInclusionListResponse`

```python
class GetInclusionListResponse(Container):
    inclusion_list_summary: InclusionListSummary
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_INCLUSION_LIST]
```

## Protocols

### `ExecutionEngine`

*Note*: `get_execution_inclusion_list` function is added to the `ExecutionEngine` protocol for use as a validator.

The body of this function is implementation dependent.
The Engine API may be used to implement it with an external execution engine.

#### `get_execution_inclusion_list`

Given the `parent_block_hash`, `get_execution_inclusion_list` returns `GetInclusionListResponse` with the most recent version of the inclusion list based on the parent block hash.

```python
def get_execution_inclusion_list(self: ExecutionEngine, parent_block_hash: Root) -> GetInclusionListResponse:
    """
    Return ``GetInclusionListResponse`` object.
    """
    ...
```

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below.

### Inclusion list proposal

EIP7547 introduces forward inclusion list. The detail design is described in this [post](https://ethresear.ch/t/no-free-lunch-a-new-inclusion-list-design/16389).

Proposer must construct and broadcast `SignedInclusionListTransactions` alongside the `SignedBeaconBlock`.
- Proposer for slot `N` submits `SignedBeaconBlock` which now contains their `InclusionListSummary` and broacast it alongside the `SignedInclusionListTransactions`. The slot `N+1` execution payload is checked against the summary.
- `Transactions` is list of transactions that the proposer wants to include in slot `N+1`.
- `Summary` is a list of the addresses sending those transactions and their gas limits.
- Proposer may send many `SignedInclusionListTransactions` each with valid transactions. 

#### Constructing the inclusion list

To obtain an inclusion list, a block proposer building a block on top of a `state` must take the following actions:

1. Retrieve `inclusion_list_response: GetInclusionListResponse` from execution layer by calling `ExecutionEngine.get_execution_inclusion_list(parent_block_hash)`.

2. Call `build_inclusion_list` to build `InclusionList`.

```python
def build_inclusion_list(state: BeaconState, inclusion_list_response: GetInclusionListResponse,
                         block_slot: Slot, privkey: int) -> InclusionList:
    inclusion_list_transactions = inclusion_list_response.inclusion_list_transactions
    signature = get_inclusion_list_transactions_signature(state, inclusion_list_transactions, block_slot, privkey)
    signed_inclusion_list_transactions = SignedInclusionListTransactions(transactions=inclusion_list_transactions, signature=signature)
    return InclusionList(summary=inclusion_list_reponse.summary, transactions=signed_inclusion_list_transactions)
```

In order to get inclusion list transactions signature, the proposer will call `get_inclusion_list_transactions_signature`.

```python
def get_inclusion_list_transactions_signature(state: BeaconState,
                                         inclusion_list_summary: InclusionListSummary,
                                         block_slot: Slot,
                                         privkey: int) -> BLSSignature:
    domain = get_domain(state, DOMAIN_BEACON_PROPOSER, compute_epoch_at_slot(block_slot))
    signing_root = compute_signing_root(inclusion_list_summary, domain)
    return bls.Sign(privkey, signing_root)
```

#### Broadcast inclusion list

Finally, the proposer broadcasts `inclusion_list` along with the `SignedBeaconBlock` on the `beacon_block` pubsub topic.

### Block and sidecar proposal

#### Constructing the `BeaconBlockBody`

##### ExecutionPayload

##### `inclusion_list_summary`

`prepare_execution_payload` is updated from the Deneb specs to provide the `inclusion_list_summary`.

*Note*: In this section, `state` is the state of the slot for the block proposal _without_ the block yet applied.
That is, `state` is the `previous_state` processed through any empty slots up to the assigned slot using `process_slots(previous_state, slot)`.

*Note*: The only change made to `prepare_execution_payload` is to add `inclusion_list_summary`.

```python
def prepare_execution_payload(
        state: BeaconState,
        safe_block_hash: Hash32,
        finalized_block_hash: Hash32,
        suggested_fee_recipient: ExecutionAddress,
        inclusion_list_transactions: List[Transaction, MAX_TRANSACTIONS_PER_INCLUSION_LIST],
        execution_engine: ExecutionEngine) -> Optional[PayloadId]:
    # Verify consistency of the parent hash with respect to the previous execution payload header
    parent_hash = state.latest_execution_payload_header.block_hash

    # Set the forkchoice head and initiate the payload build process
    payload_attributes = PayloadAttributes(
        timestamp=compute_timestamp_at_slot(state, state.slot),
        prev_randao=get_randao_mix(state, get_current_epoch(state)),
        suggested_fee_recipient=suggested_fee_recipient,
        withdrawals=get_expected_withdrawals(state),
        parent_beacon_block_root=hash_tree_root(state.latest_block_header),
        inclusion_list_transactions=inclusion_list_transactions,  # [New in EIP7547]
    )
    return execution_engine.notify_forkchoice_updated(
        head_block_hash=parent_hash,
        safe_block_hash=safe_block_hash,
        finalized_block_hash=finalized_block_hash,
        payload_attributes=payload_attributes,
    )
```
