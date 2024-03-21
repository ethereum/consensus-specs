# EIP-7547 -- The Beacon Chain

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Domain types](#domain-types)
- [Preset](#preset)
  - [Execution](#execution)
- [Containers](#containers)
  - [New Containers](#new-containers)
    - [`InclusionListSummaryEntry`](#inclusionlistsummaryentry)
    - [`InclusionListSummary`](#inclusionlistsummary)
    - [`SignedInclusionListSummary`](#signedinclusionlistsummary)
    - [`InclusionList`](#inclusionlist)
  - [Extended containers](#extended-containers)
    - [`ExecutionPayload`](#executionpayload)
    - [`ExecutionPayloadHeader`](#executionpayloadheader)
    - [`BeaconState`](#beaconstate)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Execution engine](#execution-engine)
    - [Engine APIs](#engine-apis)
      - [New `verify_and_notify_new_inclusion_list`](#new-verify_and_notify_new_inclusion_list)
  - [Block processing](#block-processing)
    - [Execution payload](#execution-payload)
      - [Modified `process_execution_payload`](#modified-process_execution_payload)
      - [New `verify_inclusion_list_summary_signature`](#new-verify_inclusion_list_summary_signature)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the beacon chain specification to add an inclusion list mechanism to allow forced transaction inclusion. Refers to [EIP-7547](https://eips.ethereum.org/EIPS/eip-7547).

*Note:* This specification is built upon [Deneb](../../deneb/beacon_chain.md) and is under active development.

## Constants

### Domain types

| Name | Value |
| - | - |
| `DOMAIN_INCLUSION_LIST_SUMMARY`     | `DomainType('0x0B000000')` |

## Preset

### Execution

| Name | Value |
| - | - |
| `MAX_TRANSACTIONS_PER_INCLUSION_LIST` |  `uint64(16384) = 2**14` |

## Containers

### New Containers

#### `InclusionListSummaryEntry`

```python
class InclusionListSummaryEntry(Container):
    address: ExecutionAddress
    nonce: uint64
```

#### `InclusionListSummary`

```python
class InclusionListSummary(Container):
    slot: Slot
    proposer_index: ValidatorIndex
    parent_hash: Hash32
    summary: List[InclusionListSummaryEntry, MAX_TRANSACTIONS_PER_INCLUSION_LIST]
```

#### `SignedInclusionListSummary`

```python
class SignedInclusionListSummary(Container):
    message: InclusionListSummary
    signature: BLSSignature
```

#### `InclusionList`

```python
class InclusionList(Container):
    signed_summary: SignedInclusionListSummary
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_INCLUSION_LIST]
```

### Extended containers

#### `ExecutionPayload`

Adding `parent_inclusion_list_summary`.

```python
class ExecutionPayload(Container):
    # Execution block header fields
    parent_hash: Hash32
    fee_recipient: ExecutionAddress  # 'beneficiary' in the yellow paper
    state_root: Bytes32
    receipts_root: Bytes32
    logs_bloom: ByteVector[BYTES_PER_LOGS_BLOOM]
    prev_randao: Bytes32  # 'difficulty' in the yellow paper
    block_number: uint64  # 'number' in the yellow paper
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    extra_data: ByteList[MAX_EXTRA_DATA_BYTES]
    base_fee_per_gas: uint256
    # Extra payload fields
    block_hash: Hash32  # Hash of execution block
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]
    withdrawals: List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD]
    blob_gas_used: uint64
    excess_blob_gas: uint64
    parent_inclusion_list_summary: SignedInclusionListSummary  # [New in EIP7547]
```

#### `ExecutionPayloadHeader`

Adding `parent_inclusion_list_summary_root`.

```python
class ExecutionPayloadHeader(Container):
    # Execution block header fields
    parent_hash: Hash32
    fee_recipient: ExecutionAddress
    state_root: Bytes32
    receipts_root: Bytes32
    logs_bloom: ByteVector[BYTES_PER_LOGS_BLOOM]
    prev_randao: Bytes32
    block_number: uint64
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    extra_data: ByteList[MAX_EXTRA_DATA_BYTES]
    base_fee_per_gas: uint256
    # Extra payload fields
    block_hash: Hash32  # Hash of execution block
    transactions_root: Root
    withdrawals_root: Root
    blob_gas_used: uint64
    excess_blob_gas: uint64 
    parent_inclusion_list_summary_root: Root  # [New in EIP7547]
```

#### `BeaconState`

Add `parent_proposer_index`.

```python
class BeaconState(Container):
    # Versioning
    genesis_time: uint64
    genesis_validators_root: Root
    slot: Slot
    fork: Fork
    # History
    latest_block_header: BeaconBlockHeader
    block_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    state_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    historical_roots: List[Root, HISTORICAL_ROOTS_LIMIT]
    # Eth1
    eth1_data: Eth1Data
    eth1_data_votes: List[Eth1Data, EPOCHS_PER_ETH1_VOTING_PERIOD * SLOTS_PER_EPOCH]
    eth1_deposit_index: uint64
    # Registry
    validators: List[Validator, VALIDATOR_REGISTRY_LIMIT]
    balances: List[Gwei, VALIDATOR_REGISTRY_LIMIT]
    # Randomness
    randao_mixes: Vector[Bytes32, EPOCHS_PER_HISTORICAL_VECTOR]
    # Slashings
    slashings: Vector[Gwei, EPOCHS_PER_SLASHINGS_VECTOR]  # Per-epoch sums of slashed effective balances
    # Participation
    previous_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    current_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    # Finality
    justification_bits: Bitvector[JUSTIFICATION_BITS_LENGTH]  # Bit set for every recent justified epoch
    previous_justified_checkpoint: Checkpoint
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    # Inactivity
    inactivity_scores: List[uint64, VALIDATOR_REGISTRY_LIMIT]
    # Sync
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    # Execution
    latest_execution_payload_header: ExecutionPayloadHeader
    # Withdrawals
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
    # Deep history valid from Capella onwards
    historical_summaries: List[HistoricalSummary, HISTORICAL_ROOTS_LIMIT]
    # Needed for inclusion list validation
    parent_proposer_index: ValidatorIndex  # [New in EIP7547]
```

## Beacon chain state transition function

### Execution engine

#### Engine APIs

##### New `verify_and_notify_new_inclusion_list`

```python
def verify_and_notify_new_inclusion_list(self: ExecutionEngine,
                              inclusion_list: InclusionList) -> bool:
    """
    Return ``True`` if and only if the transactions in the inclusion list can be successfully executed
    starting from the execution state corresponding to the `parent_hash` in the inclusion list 
    summary.
    """
    ...
```

### Block processing

#### Execution payload

##### Modified `process_execution_payload`

Assert validity of inclusion list summary with `verify_inclusion_list_summary_signature`.

```python
def process_execution_payload(state: BeaconState, body: BeaconBlockBody, execution_engine: ExecutionEngine) -> None:
    payload = body.execution_payload

    # Verify consistency of the parent hash with respect to the previous execution payload header
    assert payload.parent_hash == state.latest_execution_payload_header.block_hash
    # Verify prev_randao
    assert payload.prev_randao == get_randao_mix(state, get_current_epoch(state))
    # Verify timestamp
    assert payload.timestamp == compute_timestamp_at_slot(state, state.slot)
    # [New in EIP7547] Verify parent proposer signature on inclusion list summary
    assert verify_inclusion_list_summary_signature(state, payload.parent_inclusion_list_summary)

    # Verify commitments are under limit
    assert len(body.blob_kzg_commitments) <= MAX_BLOBS_PER_BLOCK

    # Verify the execution payload is valid
    versioned_hashes = [kzg_commitment_to_versioned_hash(commitment) for commitment in body.blob_kzg_commitments]
    assert execution_engine.verify_and_notify_new_payload(
        NewPayloadRequest(
            execution_payload=payload,
            versioned_hashes=versioned_hashes,
            parent_beacon_block_root=state.latest_block_header.parent_root,
        )
    )

    # Cache execution payload header
    state.latest_execution_payload_header = ExecutionPayloadHeader(
        parent_hash=payload.parent_hash,
        fee_recipient=payload.fee_recipient,
        state_root=payload.state_root,
        receipts_root=payload.receipts_root,
        logs_bloom=payload.logs_bloom,
        prev_randao=payload.prev_randao,
        block_number=payload.block_number,
        gas_limit=payload.gas_limit,
        gas_used=payload.gas_used,
        timestamp=payload.timestamp,
        extra_data=payload.extra_data,
        base_fee_per_gas=payload.base_fee_per_gas,
        block_hash=payload.block_hash,
        transactions_root=hash_tree_root(payload.transactions),
        withdrawals_root=hash_tree_root(payload.withdrawals),
        blob_gas_used=payload.blob_gas_used,
        excess_blob_gas=payload.excess_blob_gas,
        parent_inclusion_list_summary_root=hash_tree_root(payload.parent_inclusion_list_summary)  # [New in EIP7547]
    )
```

##### New `verify_inclusion_list_summary_signature`

```python
def verify_inclusion_list_summary_signature(state: BeaconState,
                                            inclusion_list_summary: SignedInclusionListSummary) -> bool:
    signing_root = compute_signing_root(
        inclusion_list_summary.message,
        get_domain(state, DOMAIN_INCLUSION_LIST_SUMMARY),
    )
    proposer = state.validators[state.proposer_index]
    return bls.Verify(il_proposer.pubkey, signing_root, inclusion_list_summary.signature)
```