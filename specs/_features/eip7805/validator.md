# EIP-7805 -- Honest Validator

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
  - [Time parameters](#time-parameters)
- [Helpers](#helpers)
  - [New `GetInclusionListResponse`](#new-getinclusionlistresponse)
- [Protocols](#protocols)
  - [`ExecutionEngine`](#executionengine)
    - [New `get_inclusion_list`](#new-get_inclusion_list)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Validator assignments](#validator-assignments)
    - [Inclusion list committee](#inclusion-list-committee)
    - [Lookahead](#lookahead)
  - [Block and sidecar proposal](#block-and-sidecar-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [ExecutionPayload](#executionpayload)
  - [Inclusion list proposal](#inclusion-list-proposal)
    - [Constructing the `SignedInclusionList`](#constructing-the-signedinclusionlist)
  - [Attesting](#attesting)
    - [Attestation data](#attestation-data)
      - [Modified LMD GHOST vote](#modified-lmd-ghost-vote)
  - [Sync committee](#sync-committee)
    - [`get_sync_committee_message`](#get_sync_committee_message)
      - [Modified `beacon_block_root`](#modified-beacon_block_root)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
validator" to implement EIP-7805.

## Prerequisites

This document is an extension of the
[Electra -- Honest Validator](../../electra/validator.md) guide. All behaviors
and definitions defined in this document, and documents it extends, carry over
unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the
updated Beacon Chain doc of [EIP-7805](./beacon-chain.md) are requisite for this
document and used throughout. Please see related Beacon Chain doc before
continuing and use them as a reference throughout.

## Configuration

### Time parameters

| Name                                 | Value                       |  Unit   |  Duration  |
| ------------------------------------ | --------------------------- | :-----: | :--------: |
| `INCLUSION_LIST_SUBMISSION_DEADLINE` | `SECONDS_PER_SLOT * 2 // 3` | seconds | 8 seconds  |
| `PROPOSER_INCLUSION_LIST_CUTOFF`     | `SECONDS_PER_SLOT - 1`      | seconds | 11 seconds |

## Helpers

### New `GetInclusionListResponse`

```python
@dataclass
class GetInclusionListResponse(object):
    inclusion_list_transactions: Sequence[Transaction]
```

## Protocols

### `ExecutionEngine`

*Note*: `get_inclusion_list` function is added to the `ExecutionEngine` protocol
for use as an inclusion list committee member.

The body of this function is implementation dependent. The Engine API may be
used to implement it with an external execution engine.

#### New `get_inclusion_list`

`get_inclusion_list` returns `GetInclusionListResponse` with the most recent
inclusion list transactions that has been built based on the latest view of the
public mempool.

```python
def get_inclusion_list(self: ExecutionEngine) -> GetInclusionListResponse:
    """
    Return ``GetInclusionListResponse`` object.
    """
    ...
```

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below.

### Validator assignments

#### Inclusion list committee

A validator may be a member of the new inclusion list committee for a given
slot. To determine inclusion list committee assignments, the validator can run
the following function:
`get_inclusion_committee_assignment(state, epoch, validator_index)` where
`epoch <= next_epoch`.

Inclusion list committee selection is only stable within the context of the
current and next epoch.

```python
def get_inclusion_committee_assignment(
    state: BeaconState, epoch: Epoch, validator_index: ValidatorIndex
) -> Optional[Slot]:
    """
    Returns the slot during the requested epoch in which the validator with index ``validator_index``
    is a member of the inclusion list committee. Returns None if no assignment is found.
    """
    next_epoch = Epoch(get_current_epoch(state) + 1)
    assert epoch <= next_epoch

    start_slot = compute_start_slot_at_epoch(epoch)
    for slot in range(start_slot, start_slot + SLOTS_PER_EPOCH):
        if validator_index in get_inclusion_list_committee(state, Slot(slot)):
            return Slot(slot)
    return None
```

#### Lookahead

`get_inclusion_committee_assignment` should be called at the start of each epoch
to get the assignment for the next epoch (`current_epoch + 1`). A validator
should plan for future assignments by noting their assigned inclusion list
committee slot.

### Block and sidecar proposal

#### Constructing the `BeaconBlockBody`

##### ExecutionPayload

`prepare_execution_payload` is updated from the Electra specs.

*Note*: In this section, `state` is the state of the slot for the block proposal
_without_ the block yet applied. That is, `state` is the `previous_state`
processed through any empty slots up to the assigned slot using
`process_slots(previous_state, slot)`.

*Note*: The only change to `prepare_execution_payload` is to call
`get_inclusion_list_store` and `get_inclusion_list_transactions` to set the new
`inclusion_list_transactions` field of `PayloadAttributes`.

*Note*: A proposer should produce an execution payload that satisfies the
inclusion list constraints with respect to the inclusion lists gathered up to
`PROPOSER_INCLUSION_LIST_CUTOFF` into the slot.

```python
def prepare_execution_payload(
    state: BeaconState,
    safe_block_hash: Hash32,
    finalized_block_hash: Hash32,
    suggested_fee_recipient: ExecutionAddress,
    execution_engine: ExecutionEngine,
) -> Optional[PayloadId]:
    # Verify consistency of the parent hash with respect to the previous execution payload header
    parent_hash = state.latest_execution_payload_header.block_hash

    # Set the forkchoice head and initiate the payload build process
    withdrawals, _ = get_expected_withdrawals(state)

    # [New in EIP7805]
    # Get the inclusion list store
    inclusion_list_store = get_inclusion_list_store()

    payload_attributes = PayloadAttributes(
        timestamp=compute_time_at_slot(state, state.slot),
        prev_randao=get_randao_mix(state, get_current_epoch(state)),
        suggested_fee_recipient=suggested_fee_recipient,
        withdrawals=withdrawals,
        parent_beacon_block_root=hash_tree_root(state.latest_block_header),
        # [New in EIP7805]
        inclusion_list_transactions=get_inclusion_list_transactions(
            inclusion_list_store, state, Slot(state.slot - 1)
        ),
    )
    return execution_engine.notify_forkchoice_updated(
        head_block_hash=parent_hash,
        safe_block_hash=safe_block_hash,
        finalized_block_hash=finalized_block_hash,
        payload_attributes=payload_attributes,
    )
```

### Inclusion list proposal

A validator is expected to propose a
[`SignedInclusionList`](./beacon-chain.md#signedinclusionlist) at the beginning
of any `slot` for which
`get_inclusion_committee_assignment(state, epoch, validator_index)` returns.

If a validator is in the current inclusion list committee, the validator should
create and broadcast the `signed_inclusion_list` to the global `inclusion_list`
subnet by `INCLUSION_LIST_SUBMISSION_DEADLINE` seconds into the slot after
processing the block for the current slot and confirming it as the head. If no
block is received by `INCLUSION_LIST_SUBMISSION_DEADLINE - 1` seconds into the
slot, the validator should run `get_head` to determine the local head and
construct and broadcast the inclusion list based on this local head by
`INCLUSION_LIST_SUBMISSION_DEADLINE` seconds into the slot.

#### Constructing the `SignedInclusionList`

The validator creates the `signed_inclusion_list` as follows:

- First, the validator creates the `inclusion_list`.
- Set `inclusion_list.slot` to the assigned slot returned by
  `get_inclusion_committee_assignment`.
- Set `inclusion_list.validator_index` to the validator's index.
- Set `inclusion_list.inclusion_list_committee_root` to the hash tree root of
  the committee that the validator is a member of.
- Set `inclusion_list.transactions` using the response from `ExecutionEngine`
  via `get_inclusion_list`.
- Sign the `inclusion_list` using the helper `get_inclusion_list_signature` and
  obtain the `signature`.
- Set `signed_inclusion_list.message` to `inclusion_list`.
- Set `signed_inclusion_list.signature` to `signature`.

```python
def get_inclusion_list_signature(
    state: BeaconState, inclusion_list: InclusionList, privkey: int
) -> BLSSignature:
    domain = get_domain(
        state, DOMAIN_INCLUSION_LIST_COMMITTEE, compute_epoch_at_slot(inclusion_list.slot)
    )
    signing_root = compute_signing_root(inclusion_list, domain)
    return bls.Sign(privkey, signing_root)
```

### Attesting

#### Attestation data

*Note*: The only change to `attestation_data` is to call
`get_attester_head(store, head_root)` to set the `beacon_block_root` field of
`attestation_data`.

##### Modified LMD GHOST vote

Set `attestation_data.beacon_block_root = get_attester_head(store, head_root)`.

### Sync committee

*Note*: The only change to `get_sync_committee_message` is to call
`get_attester_head(store, head_root)` to set the `beacon_block_root` parameter
of `get_sync_committee_message`.

#### `get_sync_committee_message`

##### Modified `beacon_block_root`

The `beacon_block_root` parameter MUST be set to return value of
[`get_attester_head(store: Store, head_root: Root)`](./fork-choice.md#new-get_attester_head)
function.
