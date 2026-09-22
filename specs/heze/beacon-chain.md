# Heze -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
  - [New `InclusionListBits`](#new-inclusionlistbits)
  - [New `InclusionListCommittee`](#new-inclusionlistcommittee)
- [Constants](#constants)
  - [Domains](#domains)
- [Presets](#presets)
  - [Inclusion list committee](#inclusion-list-committee)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`InclusionList`](#inclusionlist)
    - [`SignedInclusionList`](#signedinclusionlist)
  - [Modified containers](#modified-containers)
    - [`ExecutionPayloadBid`](#executionpayloadbid)
    - [`SignedExecutionPayloadBid`](#signedexecutionpayloadbid)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`BeaconState`](#beaconstate)
- [Helpers](#helpers)
  - [Predicates](#predicates)
    - [New `is_valid_inclusion_list_signature`](#new-is_valid_inclusion_list_signature)
  - [Beacon state accessors](#beacon-state-accessors)
    - [New `get_inclusion_list_committee`](#new-get_inclusion_list_committee)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Epoch processing](#epoch-processing)
    - [Modified `process_epoch`](#modified-process_epoch)
  - [Block processing](#block-processing)
    - [Modified `process_block`](#modified-process_block)
    - [Operations](#operations)
      - [Modified `process_operations`](#modified-process_operations)

<!-- mdformat-toc end -->

## Introduction

Heze is a consensus-layer upgrade containing a number of features. Including:

- [EIP-7805](https://github.com/ethereum/EIPs/blob/9a345f96c2295a678b0ce33e94d41276ddb3fdef/EIPS/eip-7805.md):
  Fork-choice enforced Inclusion Lists (FOCIL)
- [EIP-8015](https://github.com/ethereum/EIPs/blob/0ebff04bf89b696d51ebf2ff9d029940ef3ed693/EIPS/eip-8015.md):
  Remove `deposit` and `eth1data` fields

*Note*: These EIPs are in draft and may change or be removed. Each link above
points to the specific version targeted by this specification, which may differ
from the latest published version of the EIPs.

## Types

### New `InclusionListBits`

```python
class InclusionListBits(BitVector):
    """
    A bitfield over the inclusion list committee, one bit per member in
    committee order.
    """

    LENGTH = INCLUSION_LIST_COMMITTEE_SIZE
```

### New `InclusionListCommittee`

```python
class InclusionListCommittee(Vector[ValidatorIndex]):
    """
    The inclusion list committee of a slot.
    """

    LENGTH = INCLUSION_LIST_COMMITTEE_SIZE
```

## Constants

### Domains

| Name                              | Value                      |
| --------------------------------- | -------------------------- |
| `DOMAIN_INCLUSION_LIST_COMMITTEE` | `DomainType('0x10000000')` |

## Presets

### Inclusion list committee

| Name                            | Value                 |
| ------------------------------- | --------------------- |
| `INCLUSION_LIST_COMMITTEE_SIZE` | `Uint64(2**4)` (= 16) |

## Containers

### New containers

#### `InclusionList`

```python
class InclusionList(Container):
    slot: Slot
    validator_index: ValidatorIndex
    dependent_root: Root
    transactions: Transactions
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
class ExecutionPayloadBid(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=13)

    parent_block_hash: Hash32
    parent_block_root: Root
    block_hash: Hash32
    prev_randao: Bytes32
    fee_recipient: ExecutionAddress
    gas_limit: Uint64
    builder_index: BuilderIndex
    slot: Slot
    value: Gwei
    execution_payment: Gwei
    blob_kzg_commitments: BlobKZGCommitments
    execution_requests_root: Root
    # [New in Heze:EIP7805]
    inclusion_list_bits: InclusionListBits
```

#### `SignedExecutionPayloadBid`

```python
class SignedExecutionPayloadBid(Container):
    # [Modified in Heze:EIP7805]
    message: ExecutionPayloadBid
    signature: BLSSignature
```

#### `BeaconBlockBody`

```python
class BeaconBlockBody(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=13, gaps=(1, 6))

    randao_reveal: BLSSignature
    # [Modified in Heze:EIP8015]
    # Removed `eth1_data`
    graffiti: Bytes32
    proposer_slashings: ProposerSlashings
    attester_slashings: AttesterSlashings
    attestations: Attestations
    # [Modified in Heze:EIP8015]
    # Removed `deposits`
    voluntary_exits: VoluntaryExits
    sync_aggregate: SyncAggregate
    bls_to_execution_changes: BLSToExecutionChanges
    # [Modified in Heze:EIP7805]
    signed_execution_payload_bid: SignedExecutionPayloadBid
    payload_attestations: PayloadAttestations
    parent_execution_requests: ExecutionRequests
```

#### `BeaconState`

```python
class BeaconState(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=46, gaps=(8, 9, 10, 28))

    genesis_time: Uint64
    genesis_validators_root: Root
    slot: Slot
    fork: Fork
    latest_block_header: BeaconBlockHeader
    block_roots: BlockRoots
    state_roots: StateRoots
    historical_roots: HistoricalRoots
    # [Modified in Heze:EIP8015]
    # Removed `eth1_data`
    # [Modified in Heze:EIP8015]
    # Removed `eth1_data_votes`
    # [Modified in Heze:EIP8015]
    # Removed `eth1_deposit_index`
    validators: Validators
    balances: Balances
    randao_mixes: RandaoMixes
    slashings: Slashings
    previous_epoch_participation: EpochParticipation
    current_epoch_participation: EpochParticipation
    justification_bits: JustificationBits
    previous_justified_checkpoint: Checkpoint
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    inactivity_scores: InactivityScores
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    latest_block_hash: Hash32
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
    historical_summaries: HistoricalSummaries
    # [Modified in Heze:EIP8015]
    # Removed `deposit_requests_start_index`
    deposit_balance_to_consume: Gwei
    exit_balance_to_consume: Gwei
    earliest_exit_epoch: Epoch
    consolidation_balance_to_consume: Gwei
    earliest_consolidation_epoch: Epoch
    pending_deposits: PendingDeposits
    pending_partial_withdrawals: PendingPartialWithdrawals
    pending_consolidations: PendingConsolidations
    proposer_lookahead: ProposerLookahead
    builders: Builders
    next_withdrawal_builder_index: BuilderIndex
    execution_payload_availability: ExecutionPayloadAvailability
    builder_pending_payments: BuilderPendingPayments
    builder_pending_withdrawals: BuilderPendingWithdrawals
    # [Modified in Heze:EIP7805]
    latest_execution_payload_bid: ExecutionPayloadBid
    payload_expected_withdrawals: Withdrawals
    ptc_window: PayloadTimelinessCommitteeWindow
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
def get_inclusion_list_committee(state: BeaconState, slot: Slot) -> InclusionListCommittee:
    """
    Get the inclusion list committee for the given ``slot``.
    """
    epoch = compute_epoch_at_slot(slot)
    indices: list[ValidatorIndex] = []
    # Concatenate all committees for this slot in order
    committees_per_slot = get_committee_count_per_slot(state, epoch)
    for i in range(committees_per_slot):
        committee = get_beacon_committee(state, slot, CommitteeIndex(i))
        indices.extend(committee)
    return InclusionListCommittee(
        data=[indices[i % len(indices)] for i in range(INCLUSION_LIST_COMMITTEE_SIZE)]
    )
```

## Beacon chain state transition function

### Epoch processing

#### Modified `process_epoch`

*Note*: `process_epoch` removes call to `process_eth1_data_reset`.

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_inactivity_updates(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)
    process_slashings(state)
    # [Modified in Heze:EIP8015]
    # Removed `process_eth1_data_reset`
    process_pending_deposits(state)
    process_pending_consolidations(state)
    process_builder_pending_payments(state)
    process_effective_balance_updates(state)
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_summaries_update(state)
    process_participation_flag_updates(state)
    process_sync_committee_updates(state)
    process_proposer_lookahead(state)
    process_ptc_window(state)
```

### Block processing

#### Modified `process_block`

*Note*: `process_block` removes call to `process_eth1_data`.

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    parent_slot = state.latest_block_header.slot

    process_parent_execution_payload(state, block)
    process_block_header(state, block)
    process_withdrawals(state)
    process_execution_payload_bid(state, block.body.signed_execution_payload_bid)
    process_randao(state, block.body)
    # [Modified in Heze:EIP8015]
    # Removed `process_eth1_data`
    process_operations(state, block.body, parent_slot)
    process_sync_aggregate(state, block.body.sync_aggregate)
```

#### Operations

##### Modified `process_operations`

*Note*: `process_operations` removes the check that `body.deposits` is empty.

```python
def process_operations(state: BeaconState, body: BeaconBlockBody, parent_slot: Slot) -> None:
    def for_ops(operations: Sequence[Any], fn: Callable[..., None], *args: Any) -> None:
        for operation in operations:
            fn(state, operation, *args)

    assert len(body.proposer_slashings) <= MAX_PROPOSER_SLASHINGS
    assert len(body.attester_slashings) <= MAX_ATTESTER_SLASHINGS_ELECTRA
    assert len(body.attestations) <= MAX_ATTESTATIONS_ELECTRA
    assert len(body.voluntary_exits) <= MAX_VOLUNTARY_EXITS
    assert len(body.bls_to_execution_changes) <= MAX_BLS_TO_EXECUTION_CHANGES
    assert len(body.payload_attestations) <= MAX_PAYLOAD_ATTESTATIONS

    for_ops(body.proposer_slashings, process_proposer_slashing)
    for_ops(body.attester_slashings, process_attester_slashing)
    for_ops(body.attestations, process_attestation, parent_slot)
    for_ops(body.voluntary_exits, process_voluntary_exit)
    for_ops(body.bls_to_execution_changes, process_bls_to_execution_change)
    for_ops(body.payload_attestations, process_payload_attestation)
```
