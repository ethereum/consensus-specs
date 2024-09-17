# FOCIL -- Honest Validator

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Protocol](#protocol)
  - [`ExecutionEngine`](#executionengine)
- [New inclusion list committee assignment](#new-inclusion-list-committee-assignment)
  - [Lookahead](#lookahead)
- [New proposer duty](#new-proposer-duty)
  - [Inclusion summary aggregates release](#inclusion-summary-aggregates-release)
  - [Block proposal](#block-proposal)
    - [Constructing the new `InclusionSummaryAggregate` field in  `BeaconBlockBody`](#constructing-the-new-inclusionsummaryaggregate-field-in--beaconblockbody)
- [New inclusion list committee duty](#new-inclusion-list-committee-duty)
    - [Constructing a local inclusion list](#constructing-a-local-inclusion-list)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement FOCIL.

## Prerequisites

This document is an extension of the [Electra -- Honest Validator](../../electra/validator.md) guide.
All behaviors and definitions defined in this document, and documents it extends, carry over unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the updated Beacon Chain doc of [FOCIL](./beacon-chain.md) are requisite for this document and used throughout.
Please see related Beacon Chain doc before continuing and use them as a reference throughout.

## Protocol

### `ExecutionEngine`

*Note*: `engine_getInclusionListV1` and `engine_newInclusionListV1` functions are added to the `ExecutionEngine` protocol for use as a validator.

The body of these function is implementation dependent. The Engine API may be used to implement it with an external execution engine. 

## New inclusion list committee assignment

A validator may be a member of the new Inclusion List Committee (ILC) for a given slot.  To check for ILC assignments the validator uses the helper `get_ilc_assignment(state, epoch, validator_index)` where `epoch <= next_epoch`.

ILC selection is only stable within the context of the current and next epoch.

```python
def get_ilc_assignment(
        state: BeaconState,
        epoch: Epoch,
        validator_index: ValidatorIndex) -> Optional[Slot]:
    """
    Returns the slot during the requested epoch in which the validator with index `validator_index`
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

`get_ilc_assignment` should be called at the start of each epoch to get the assignment for the next epoch (`current_epoch + 1`). A validator should plan for future assignments by noting their assigned ILC slot. 

## New proposer duty

### Inclusion summary aggregates release

Proposer has to release `signed_inclusion_summary_aggregates` at `3 * SECONDS_PER_SLOT // 4` seconds into the slot. The proposer will have to:
- Listen to the `inclusion_list` gossip global topic until `3 * SECONDS_PER_SLOT // 4` seconds into the slot.
- Gather all observed local inclusion lists, ensuring they meet the verification criteria specified in the local inclusion list gossip validation and `on_local_inclusion_list` sections. This requires:
  - The `message.parent_hash` must match the local fork choice head view.
  - The `message.slot` must be exactly one slot before the current proposing slot.
  - The `message.summaries` and `message.transactions` must pass `engine_newPayloadV4` validation.
- The proposer aggregates all `local_inclusion_list` data into an `inclusion_summary_aggregates`, focusing only on the `InclusionSummary` field from the `LocalInclusionList`. 
  - To aggregate, the proposer fills the `aggregation_bits` field by using the relative position of the validator indices with respect to the ILC obtained from `get_inclusion_list_committee(state, proposing_slot - 1)`.
- The proposer signs the `inclusion_summary_aggregates` using helper `get_inclusion_summary_aggregates_signatures` and constructs a `signed_inclusion_aggregates_summary`.

```python
def get_inclusion_summary_aggregates_signature(
        state: BeaconState, inclusion_summary_aggregates: InclusionSummaryAggregates, privkey: int) -> BLSSignature:
    domain = get_domain(state, DOMAIN_BEACON_PROPOSER), compute_epoch_at_slot(proposer_slot))
    signing_root = compute_signing_root(inclusion_summary_aggregates, domain)
    return bls.Sign(privkey, signing_root)
```

### Block proposal

Validators are still expected to propose `SignedBeaconBlock` at the beginning of any slot during which `is_proposer(state, validator_index)` returns `true`. The mechanism to prepare this beacon block and related sidecars differs from previous forks as follows:

#### Constructing the new `InclusionSummaryAggregate` field in  `BeaconBlockBody`

Proposer has to include a valid `inclusion_summary_aggregates` into the block body. The proposer will have to
* Proposer uses perviously constructed `InclusionSummaryAggregates` and include it in the beacon block body.

## New inclusion list committee duty

Some validators are selected to submit local inclusion list. Validators should call `get_ilc_assignment` at the beginning of an epoch to be prepared to submit their local inclusion list during the next epoch. 

A validator should create and broadcast the `signed_inclusion_list` to the global `inclusion_list` subnet at the `SECONDS_PER_SLOT * 2 // 2` seconds of `slot`.

#### Constructing a local inclusion list

The validator creates the `signed_local_inclusion_list` as follows:
- First, the validator creates the `local_inclusion_list`.
- Set `local_inclusion_list.slot` to the assigned slot returned by `get_ilc_assignment`.
- Set `local_inclusion_list.validator_index` to the validator's index.
- Set `local_inclusion_list.parent_hash` to the block hash of the fork choice head.
- Set `local_inclusion_list.summaries` and `local_inclusion_list.transactions` using the response from `engine_getInclusionListV1` from the execution layer client.
- Sign the `local_inclusion_list` using the helper `get_inclusion_list_signature` and obtain the `signature`.
- Set `signed_local_inclusion_list.message` to `local_inclusion_list`.
- Set `signed_local_inclusion_list.signature` to `signature`.

```python
def get_inclusion_list_signature(
        state: BeaconState, inclusion_list: LocalInclusionList, privkey: int) -> BLSSignature:
    domain = get_domain(state, DOMAIN_IL_COMMITTEE, compute_epoch_at_slot(inclusion_list.slot))
    signing_root = compute_signing_root(inclusion_list, domain)
    return bls.Sign(privkey, signing_root)
```