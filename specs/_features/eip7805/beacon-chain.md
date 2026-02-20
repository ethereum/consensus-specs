# EIP-7805 -- The Beacon Chain

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Domains](#domains)
- [Preset](#preset)
  - [Inclusion list committee](#inclusion-list-committee)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`InclusionList`](#inclusionlist)
    - [`SignedInclusionList`](#signedinclusionlist)
  - [Modified containers](#modified-containers)
    - [`ExecutionPayloadBid`](#executionpayloadbid)
    - [`SignedExecutionPayloadBid`](#signedexecutionpayloadbid)
    - [`BeaconState`](#beaconstate)
- [Helpers](#helpers)
  - [Predicates](#predicates)
    - [New `is_valid_inclusion_list_signature`](#new-is_valid_inclusion_list_signature)
  - [Beacon state accessors](#beacon-state-accessors)
    - [New `get_inclusion_list_committee`](#new-get_inclusion_list_committee)

<!-- mdformat-toc end -->

## Introduction

These are the beacon-chain specifications to add EIP-7805 / fork-choice
enforced, committee-based inclusion list (FOCIL) mechanism to allow forced
transaction inclusion.

*Note*: This specification is built upon [Gloas](../../gloas/beacon-chain.md).

## Constants

### Domains

| Name                              | Value                      |
| --------------------------------- | -------------------------- |
| `DOMAIN_INCLUSION_LIST_COMMITTEE` | `DomainType('0x0E000000')` |

## Preset

### Inclusion list committee

| Name                            | Value                |
| ------------------------------- | -------------------- |
| `INCLUSION_LIST_COMMITTEE_SIZE` | `uint64(2**4)` (=16) |

## Containers

### New containers

#### `InclusionList`

```python
class InclusionList(Container):
    slot: Slot
    validator_index: ValidatorIndex
    inclusion_list_committee_root: Root
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]
```

#### `SignedInclusionList`

```python
class SignedInclusionList(Container):
    message: InclusionList
    signature: BLSSignature
```

### Modified containers

#### `ExecutionPayloadBid`

```python
class ExecutionPayloadBid(Container):
    parent_block_hash: Hash32
    parent_block_root: Root
    block_hash: Hash32
    prev_randao: Bytes32
    fee_recipient: ExecutionAddress
    gas_limit: uint64
    builder_index: BuilderIndex
    slot: Slot
    value: Gwei
    execution_payment: Gwei
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    # [New in EIP7805]
    inclusion_list_bits: Bitvector[INCLUSION_LIST_COMMITTEE_SIZE]
```

#### `SignedExecutionPayloadBid`

```python
class SignedExecutionPayloadBid(Container):
    # [Modified in EIP7805]
    message: ExecutionPayloadBid
    signature: BLSSignature
```

#### `BeaconState`

```python
class BeaconState(Container):
    genesis_time: uint64
    genesis_validators_root: Root
    slot: Slot
    fork: Fork
    latest_block_header: BeaconBlockHeader
    block_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    state_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    historical_roots: List[Root, HISTORICAL_ROOTS_LIMIT]
    eth1_data: Eth1Data
    eth1_data_votes: List[Eth1Data, EPOCHS_PER_ETH1_VOTING_PERIOD * SLOTS_PER_EPOCH]
    eth1_deposit_index: uint64
    validators: List[Validator, VALIDATOR_REGISTRY_LIMIT]
    balances: List[Gwei, VALIDATOR_REGISTRY_LIMIT]
    randao_mixes: Vector[Bytes32, EPOCHS_PER_HISTORICAL_VECTOR]
    slashings: Vector[Gwei, EPOCHS_PER_SLASHINGS_VECTOR]
    previous_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    current_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    justification_bits: Bitvector[JUSTIFICATION_BITS_LENGTH]
    previous_justified_checkpoint: Checkpoint
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    inactivity_scores: List[uint64, VALIDATOR_REGISTRY_LIMIT]
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    # [Modified in EIP7805]
    latest_execution_payload_bid: ExecutionPayloadBid
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
    historical_summaries: List[HistoricalSummary, HISTORICAL_ROOTS_LIMIT]
    deposit_requests_start_index: uint64
    deposit_balance_to_consume: Gwei
    exit_balance_to_consume: Gwei
    earliest_exit_epoch: Epoch
    consolidation_balance_to_consume: Gwei
    earliest_consolidation_epoch: Epoch
    pending_deposits: List[PendingDeposit, PENDING_DEPOSITS_LIMIT]
    pending_partial_withdrawals: List[PendingPartialWithdrawal, PENDING_PARTIAL_WITHDRAWALS_LIMIT]
    pending_consolidations: List[PendingConsolidation, PENDING_CONSOLIDATIONS_LIMIT]
    proposer_lookahead: Vector[ValidatorIndex, (MIN_SEED_LOOKAHEAD + 1) * SLOTS_PER_EPOCH]
    builders: List[Builder, BUILDER_REGISTRY_LIMIT]
    next_withdrawal_builder_index: BuilderIndex
    execution_payload_availability: Bitvector[SLOTS_PER_HISTORICAL_ROOT]
    builder_pending_payments: Vector[BuilderPendingPayment, 2 * SLOTS_PER_EPOCH]
    builder_pending_withdrawals: List[BuilderPendingWithdrawal, BUILDER_PENDING_WITHDRAWALS_LIMIT]
    latest_block_hash: Hash32
    payload_expected_withdrawals: List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD]
```

## Helpers

### Predicates

#### New `is_valid_inclusion_list_signature`

```python
def is_valid_inclusion_list_signature(
    state: BeaconState, signed_inclusion_list: SignedInclusionList
) -> bool:
    """
    Check if ``signed_inclusion_list`` has a valid signature.
    """
    message = signed_inclusion_list.message
    index = message.validator_index
    pubkey = state.validators[index].pubkey
    domain = get_domain(state, DOMAIN_INCLUSION_LIST_COMMITTEE, compute_epoch_at_slot(message.slot))
    signing_root = compute_signing_root(message, domain)
    return bls.Verify(pubkey, signing_root, signed_inclusion_list.signature)
```

### Beacon state accessors

#### New `get_inclusion_list_committee`

```python
def get_inclusion_list_committee(
    state: BeaconState, slot: Slot
) -> Vector[ValidatorIndex, INCLUSION_LIST_COMMITTEE_SIZE]:
    """
    Get the inclusion list committee for the given ``slot``.
    """
    epoch = compute_epoch_at_slot(slot)
    indices: List[ValidatorIndex] = []
    # Concatenate all committees for this slot in order
    committees_per_slot = get_committee_count_per_slot(state, epoch)
    for i in range(committees_per_slot):
        committee = get_beacon_committee(state, slot, CommitteeIndex(i))
        indices.extend(committee)
    return Vector[ValidatorIndex, INCLUSION_LIST_COMMITTEE_SIZE](
        [indices[i % len(indices)] for i in range(INCLUSION_LIST_COMMITTEE_SIZE)]
    )
```
