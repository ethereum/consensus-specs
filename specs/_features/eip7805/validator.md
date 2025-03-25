# EIP-7805 -- Honest Validator

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
  - [Time parameters](#time-parameters)
- [Protocol](#protocol)
  - [`ExecutionEngine`](#executionengine)
- [New inclusion list committee assignment](#new-inclusion-list-committee-assignment)
  - [Lookahead](#lookahead)
- [New proposer duty](#new-proposer-duty)
  - [Block proposal](#block-proposal)
    - [Update execution client with inclusion lists](#update-execution-client-with-inclusion-lists)
- [New inclusion list committee duty](#new-inclusion-list-committee-duty)
    - [Constructing a signed inclusion list](#constructing-a-signed-inclusion-list)
- [Modified attester duty](#modified-attester-duty)
    - [Modified LMD GHOST vote](#modified-lmd-ghost-vote)
- [Modified sync committee duty](#modified-sync-committee-duty)
    - [Modified beacon block root](#modified-beacon-block-root)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement EIP-7805.

## Prerequisites

This document is an extension of the [Electra -- Honest Validator](../../electra/validator.md) guide.
All behaviors and definitions defined in this document, and documents it extends, carry over unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the updated Beacon Chain doc of [EIP-7805](./beacon-chain.md) are requisite for this document and used throughout.
Please see related Beacon Chain doc before continuing and use them as a reference throughout.

## Configuration

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `PROPOSER_INCLUSION_LIST_CUT_OFF` | `SECONDS_PER_SLOT - 1` | seconds | 11 seconds |

## Protocol

### `ExecutionEngine`

*Note*: `engine_getInclusionListV1` and `engine_updateBlockWithInclusionListV1` functions are added to the `ExecutionEngine` protocol for use as a validator.

The body of these function is implementation dependent. The Engine API may be used to implement it with an external execution engine.

## New inclusion list committee assignment

A validator may be a member of the new Inclusion List Committee (ILC) for a given slot. To check for ILC assignments the validator uses the helper `get_inclusion_committee_assignment(state, epoch, validator_index)` where `epoch <= next_epoch`.

Inclusion list committee selection is only stable within the context of the current and next epoch.

```python
def get_inclusion_committee_assignment(
    state: BeaconState, epoch: Epoch, validator_index: ValidatorIndex
) -> Optional[Slot]:
    """
    Returns the slot during the requested epoch in which the validator with index ``validator_index``
    is a member of the ILC. Returns None if no assignment is found.
    """
    next_epoch = Epoch(get_current_epoch(state) + 1)
    assert epoch <= next_epoch

    start_slot = compute_start_slot_at_epoch(epoch)
    for slot in range(start_slot, start_slot + SLOTS_PER_EPOCH):
        if validator_index in get_inclusion_list_committee(state, Slot(slot)):
            return Slot(slot)
    return None
```

### Lookahead

`get_inclusion_committee_assignment` should be called at the start of each epoch to get the assignment for the next epoch (`current_epoch + 1`). A validator should plan for future assignments by noting their assigned ILC slot.

## New proposer duty

### Block proposal

Proposers are still expected to propose `SignedBeaconBlock` at the beginning of any slot during which `is_proposer(state, validator_index)` returns true. The mechanism to prepare this beacon block and related sidecars differs from previous forks as follows:

#### Update execution client with inclusion lists

The proposer should call `engine_updateInclusionListV1` at `PROPOSER_INCLUSION_LIST_CUT_OFF` into the slot with the list of the inclusion lists that gathered up to `PROPOSER_INCLUSION_LIST_CUT_OFF`.

## New inclusion list committee duty

Some validators are selected to submit signed inclusion list. Validators should call `get_inclusion_committee_assignment` at the beginning of an epoch to be prepared to submit their inclusion list during the next epoch.

A validator should create and broadcast the `signed_inclusion_list` to the global `inclusion_list` subnet by `PROPOSER_INCLUSION_LIST_CUT_OFF` seconds into the slot, unless a block for the current slot has been processed and is the head of the chain and broadcast to the network.

#### Constructing a signed inclusion list

The validator creates the `signed_inclusion_list` as follows:
- First, the validator creates the `inclusion_list`.
- Set `inclusion_list.slot` to the assigned slot returned by `get_inclusion_committee_assignment`.
- Set `inclusion_list.validator_index` to the validator's index.
- Set `inclusion_list.inclusion_list_committee_root` to the hash tree root of the committee that the validator is a member of.
- Set `inclusion_list.transactions` using the response from `engine_getInclusionListV1` from the execution layer client.
- Sign the `inclusion_list` using the helper `get_inclusion_list_signature` and obtain the `signature`.
- Set `signed_inclusion_list.message` to `inclusion_list`.
- Set `signed_inclusion_list.signature` to `signature`.

```python
def get_inclusion_list_signature(
    state: BeaconState, inclusion_list: InclusionList, privkey: int
) -> BLSSignature:
    domain = get_domain(
        state,
        DOMAIN_INCLUSION_LIST_COMMITTEE,
        compute_epoch_at_slot(inclusion_list.slot),
    )
    signing_root = compute_signing_root(inclusion_list, domain)
    return bls.Sign(privkey, signing_root)
```

## Modified attester duty

#### Modified LMD GHOST vote

Set `attestation_data.beacon_block_root = get_attester_head(store, head_root)`.

## Modified sync committee duty

#### Modified beacon block root

```python
def get_sync_committee_message(
    state: BeaconState,
    block_root: Root,
    validator_index: ValidatorIndex,
    privkey: int,
    store: Store,
) -> SyncCommitteeMessage:
    epoch = get_current_epoch(state)
    domain = get_domain(state, DOMAIN_SYNC_COMMITTEE, epoch)
    signing_root = compute_signing_root(block_root, domain)
    signature = bls.Sign(privkey, signing_root)

    return SyncCommitteeMessage(
        slot=state.slot,
        beacon_block_root=get_attester_head(store, block_root),
        validator_index=validator_index,
        signature=signature,
    )
```
