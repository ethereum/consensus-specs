# FOCIL -- The Beacon Chain

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Preset](#preset)
  - [Domain types](#domain-types)
  - [Inclusion List Committee](#inclusion-list-committee)
  - [Execution](#execution)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`InclusionList`](#inclusionlist)
    - [`SignedInclusionList`](#signedinclusionlist)
  - [Predicates](#predicates)
    - [New `is_valid_inclusion_list_signature`](#new-is_valid_inclusion_list_signature)
  - [Beacon State accessors](#beacon-state-accessors)
    - [`get_inclusion_list_committee`](#get_inclusion_list_committee)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Execution engine](#execution-engine)
    - [Request data](#request-data)
      - [Modified `NewPayloadRequest`](#modified-newpayloadrequest)
    - [Engine APIs](#engine-apis)
      - [Modified `notify_new_payload`](#modified-notify_new_payload)
      - [Modified `verify_and_notify_new_payload`](#modified-verify_and_notify_new_payload)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the beacon chain specification to add a fork-choice enforced, committee-based inclusion list (FOCIL) mechanism to allow forced transaction inclusion. Refers to the following posts:
- [Fork-Choice enforced Inclusion Lists (FOCIL): A simple committee-based inclusion list proposal](https://ethresear.ch/t/fork-choice-enforced-inclusion-lists-focil-a-simple-committee-based-inclusion-list-proposal/19870/1)
- [FOCIL CL & EL workflow](https://ethresear.ch/t/focil-cl-el-workflow/20526)
*Note:* This specification is built upon [Electra](../../electra/beacon_chain.md) and is under active development.

## Preset

### Domain types

| Name | Value |
| - | - |
| `DOMAIN_IL_COMMITTEE`       | `DomainType('0x0C000000')`  # (New in FOCIL)|

### Inclusion List Committee

| Name | Value | 
| - | - | 
| `IL_COMMITTEE_SIZE` | `uint64(2**4)` (=16)  # (New in FOCIL) |

### Execution

| Name | Value |
| - | - |
| `MAX_TRANSACTIONS_PER_INCLUSION_LIST` |  `uint64(1)` # (New in FOCIL) TODO: Placeholder | 

## Containers

### New containers

#### `InclusionList`

```python
class InclusionList(Container):
    slot: Slot
    validator_index: ValidatorIndex
    inclusion_list_committee_root: Root
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_INCLUSION_LIST]
```

#### `SignedInclusionList`

```python
class SignedInclusionList(Container):
    message: InclusionList
    signature: BLSSignature
```

### Predicates

#### New `is_valid_inclusion_list_signature`

```python
def is_valid_inclusion_list_signature(
        state: BeaconState, 
        signed_inclusion_list: SignedInclusionList) -> bool:
    """
    Check if ``signed_inclusion_list`` has a valid signature
    """
    message = signed_inclusion_list.message
    index = message.validator_index
    pubkey = state.validators[index].pubkey
    domain = get_domain(state, DOMAIN_IL_COMMITTEE, compute_epoch_at_slot(message.slot))
    signing_root = compute_signing_root(message, domain)
    return bls.FastAggregateVerify(pubkey, signing_root, signed_inclusion_list.signature)
```

### Beacon State accessors

#### `get_inclusion_list_committee`

```python
def get_inclusion_list_committee(state: BeaconState, slot: Slot) -> Vector[ValidatorIndex, IL_COMMITTEE_SIZE]:
    epoch = compute_epoch_at_slot(slot)
    seed = get_seed(state, epoch, DOMAIN_IL_COMMITTEE)
    indices = get_active_validator_indices(state, epoch)
    start = (slot % SLOTS_PER_EPOCH) * IL_COMMITTEE_SIZE
    end = start + IL_COMMITTEE_SIZE
    return [indices[compute_shuffled_index(uint64(i), uint64(len(indices)), seed)] for i in range(start, end)]
```

## Beacon chain state transition function

### Execution engine

#### Request data

##### Modified `NewPayloadRequest`

```python
@dataclass
class NewPayloadRequest(object):
    execution_payload: ExecutionPayload
    versioned_hashes: Sequence[VersionedHash]
    parent_beacon_block_root: Root
    execution_requests: ExecutionRequests 
    il_transactions: List[Transaction, MAX_TRANSACTIONS_PER_INCLUSION_LIST]  # [New in FOCIL]
```

#### Engine APIs

##### Modified `notify_new_payload`

*Note*: The function `notify_new_payload` is modified to include the additional `il_transactions` parameter in FOCIL.

```python
def notify_new_payload(self: ExecutionEngine,
                       execution_payload: ExecutionPayload,
                       execution_requests: ExecutionRequests,
                       parent_beacon_block_root: Root,
                       il_transactions: List[Transaction, MAX_TRANSACTIONS_PER_INCLUSION_LIST] ) -> bool:
    """
    Return ``True`` if and only if ``execution_payload`` and ``execution_requests`` 
    are valid with respect to ``self.execution_state``.
    """
    ...
```

##### Modified `verify_and_notify_new_payload`

*Note*: The function `verify_and_notify_new_payload` is modified to pass the additional parameter `il_transactions`
when calling `notify_new_payload` in FOCIL.

```python
def verify_and_notify_new_payload(self: ExecutionEngine,
                                  new_payload_request: NewPayloadRequest) -> bool:
    """
    Return ``True`` if and only if ``new_payload_request`` is valid with respect to ``self.execution_state``.
    """
    execution_payload = new_payload_request.execution_payload
    execution_requests = new_payload_request.execution_requests
    parent_beacon_block_root = new_payload_request.parent_beacon_block_root
    il_transactions = new_payload_request.il_transactions # [New in FOCIL]

    if not self.is_valid_block_hash(execution_payload, parent_beacon_block_root):
        return False

    if not self.is_valid_versioned_hashes(new_payload_request):
        return False

    # [Modified in FOCIL]
    if not self.notify_new_payload(
            execution_payload, 
            execution_requests, 
            parent_beacon_block_root,
            il_transactions):
        return False

    return True
```