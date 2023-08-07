# ePBS -- The Beacon Chain

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the beacon chain specification of the enshrined proposer builder separation feature. 

*Note:* This specification is built upon [Deneb](../../deneb/beacon-chain.md) and is under active development.

This feature adds new staked consensus participants called *Builders* and new honest validators duties called *payload timeliness attestations*. The slot is divided in **four** intervals as opposed to the current three. Honest validators gather *signed bids* from builders and submit their consensus blocks (a `SignedBlindedBeaconBlock`) at the beginning of the slot. At the start of the second interval, honest validators submit attestations just as they do previous to this feature). At the  start of the third interval, aggregators aggregate these attestations (exactly as before this feature) and the honest builder reveals the full payload. At the start of the fourth interval, some honest validators selected to be members of the new **Payload Timeliness Committee** attest to the presence of the builder's payload.

At any given slot, the status of the blockchain's head may be either 
- A *full* block from a previous slot (eg. the current slot's proposer did not submit its block). 
- An *empty* block from the current slot (eg. the proposer submitted a timely block, but the builder did not reveal the payload on time). 
- A full block for the current slot (both the proposer and the builder revealed on time). 

For a further introduction please refer to this [ethresear.ch article](https://ethresear.ch/t/payload-timeliness-committee-ptc-an-epbs-design/16054)

## Preset

### Misc

| Name | Value | 
| - | - | 
| `PTC_SIZE` | `uint64(2**9)` (=512) |

### Domain types

| Name | Value |
| - | - |
| `DOMAIN_BEACON_BUILDER`     | `DomainType('0x0B000000')` |

### State list lengths

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `BUILDER_REGISTRY_LIMIT` | `uint64(2**20)` (=1,048,576) | builders | 

### Gwei values

| Name | Value | 
| - | - | 
| `BUILDER_MIN_BALANCE` | `Gwei(2**10 * 10**9)` = (1,024,000,000,000) | 

### Incentivization weights

| Name | Value | 
| - | - | 
| `PTC_PENALTY_WEIGHT` | `uint64(2)` | 

### Execution
| Name | Value | 
| - | - | 
| MAX_TRANSACTIONS_PER_INCLUSION_LIST | `2**4` (=16) | 

## Containers

### New Containers

#### `Builder`

``` python
class Builder(Container):
    pubkey: BLSPubkey
    withdrawal_address: ExecutionAddress  # Commitment to pubkey for withdrawals
    effective_balance: Gwei  # Balance at stake
    exit_epoch: Epoch
    withdrawable_epoch: Epoch  # When builder can withdraw funds
```

#### `SignedExecutionPayloadHeader`

```python
class SignedExecutionPayloadHeader(Container):
    message: ExecutionPayloadHeader
    signature: BLSSignature
```

#### `ExecutionPayloadEnvelope`

```python
class ExecutionPayloadEnvelope(Container):
    payload: ExecutionPayload
    state_root: Root
```

#### `SignedExecutionPayloadEnvelope`

```python
class SignedExecutionPayloadEnvelope(Container):
    message: ExecutionPayloadEnvelope
    signature: BLSSignature
```

### Modified Containers

#### `ExecutionPayload`

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
    builder_index: uint64 # [New in ePBS]
```

#### `ExecutionPayloadHeader`

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
    builder_index: uint64 # [New in ePBS]
```

#### `BeaconBlockBody`

```python
class BeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data  # Eth1 data vote
    graffiti: Bytes32  # Arbitrary data
    # Operations
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS]
    attestations: List[Attestation, MAX_ATTESTATIONS]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    execution_payload_header: SignedExecutionPayloadHeader  # [Modified in ePBS]
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]
    tx_inclusion_list: List[Transaction, MAX_TRANSACTIONS_PER_INCLUSION_LIST]
```


#### `BeaconState`
*Note*: the beacon state is modified to store a signed latest execution payload header and it adds a registry of builders, their balances and two transaction inclusion lists.

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
    historical_roots: List[Root, HISTORICAL_ROOTS_LIMIT]  # Frozen in Capella, replaced by historical_summaries
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
    # PBS
    builders: List[Builder, BUILDER_REGISTRY_LIMIT] # [New in ePBS]
    builder_balances: List[Gwei, BUILDER_REGISTRY_LIMIT] # [New in ePBS]
    previous_tx_inclusion_list: List[Transaction, MAX_TRANSACTIONS_PER_INCLUSION_LIST] # [New in ePBS]
    current_tx_inclusion_list: List[Transaction, MAX_TRANSACTIONS_PER_INCLUSION_LIST] # [New in ePBS]
    current_signed_execution_payload_header: SignedExecutionPayloadHeader # [New in ePBS]
```

## Beacon chain state transition function

*Note*: state transition is fundamentally modified in ePBS. The full state transition is broken in two parts, first importing a signed block and then importing an execution payload. 

The post-state corresponding to a pre-state `state` and a signed block `signed_block` is defined as `state_transition(state, signed_block)`. State transitions that trigger an unhandled exception (e.g. a failed `assert` or an out-of-range list access) are considered invalid. State transitions that cause a `uint64` overflow or underflow are also considered invalid. 

The post-state corresponding to a pre-state `state` and a signed execution payload `signed_execution_payload` is defined as `process_execution_payload(state, signed_execution_payload)`. State transitions that trigger an unhandled exception (e.g. a failed `assert` or an out-of-range list access) are considered invalid. State transitions that cause a `uint64` overflow or underflow are also considered invalid. 

### Block processing

*Note*: the function `process_block` is modified to only process the consensus block. The full state-transition process is broken into separate functions, one to process a `BeaconBlock` and another to process a `SignedExecutionPayload`.  

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_execution_payload_header(state, block.body.execution_payload_header) # [Modified in ePBS]
    # Removed process_withdrawal in ePBS is processed during payload processing [Modified in ePBS]
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)  # [Modified in ePBS]
    process_sync_aggregate(state, block.body.sync_aggregate)
    process_tx_inclusion_list(state, block) # [New in ePBS]
```

#### New `update_tx_inclusion_lists`

```python
def update_tx_inclusion_lists(state: BeaconState, payload: ExecutionPayload) -> None:
    old_transactions = payload.transactions[:len(state.previous_tx_inclusion_list)]
    assert state.previous_tx_inclusion_list == old_transactions

    new_transactions = payload.transactions[len(state.previous_tx_inclusion_list):]
    state.previous_tx_inclusion_list = [tx for tx in state.current_tx_inclusion_list if x not in new_transactions]

    #TODO: check validity of the IL for the next block, requires engine changes
```
#### New `verify_execution_payload_header_signature`

```python
def verify_execution_payload_header_signature(state: BeaconState, signed_header: SignedExecutionPayloadHeader) -> bool:
    builder = state.builders[signed_header.message.builder_index]
    signing_root = compute_signing_root(signed_header.message, get_domain(state, DOMAIN_BEACON_BUILDER))
    return bls.Verify(builder.pubkey, signing_root, signed_header.signature)
```

#### New `verify_execution_payload_signature`

```python
def verify_execution_envelope_signature(state: BeaconState, signed_envelope: SignedExecutionPayloadEnvelope) -> bool:
    builder = state.builders[signed_envelope.message.payload.builder_index]
    signing_root = compute_signing_root(signed_envelope.message, get_domain(state, DOMAIN_BEACON_BUILDER))
    return bls.Verify(builder.pubkey, signing_root, signed_envelope.signature)
```

#### New `process_execution_payload_header`

```python
def process_execution_payload_header(state: BeaconState, signed_header: SignedExecutionPayloadHeader) -> None:
    assert verify_execution_payload_header_signature(state, signed_header)
    header = signed_header.message
    # Verify consistency of the parent hash with respect to the previous execution payload header
    assert header.parent_hash == state.latest_execution_payload_header.block_hash
    # Verify prev_randao
    assert header.prev_randao == get_randao_mix(state, get_current_epoch(state))
    # Verify timestamp
    assert header.timestamp == compute_timestamp_at_slot(state, state.slot)
    # Cache execution payload header
    state.current_signed_execution_payload_header = signed_header
```

#### Modified `process_execution_payload`
*Note*: `process_execution_payload` is now an independent check in state transition. It is called when importing a signed execution payload proposed by the builder of the current slot.

TODO: Deal with the case when the payload becomes invalid because of the forward inclusion list.

```python
def process_execution_payload(state: BeaconState, signed_envelope: SignedExecutionPayloadEnvelope, execution_engine: ExecutionEngine) -> None:
    # Verify signature [New in ePBS]
    assert verify_execution_envelope_signature(state, signed_envelope)
    payload = signed_envelope.message.payload
    # Verify consistency with the committed header
    hash = hash_tree_root(payload)
    previous_hash = hash_tree_root(state.current_signed_execution_payload_header.message)
    assert hash == previous_hash
    # Verify and update the proposers inclusion lists
    update_tx_inclusion_lists(state, payload)
    # Verify the execution payload is valid
    assert execution_engine.verify_and_notify_new_payload(NewPayloadRequest(execution_payload=payload))
    # Process Withdrawals in the payload
    process_withdrawals(state, payload)
    # Cache the execution payload header
    state.latest_execution_payload_header = state.current_signed_execution_payload_header.message 
    # Verify the state root
    assert signed_envelope.message.state_root == hash_tree_root(state)
```

#### New `process_tx_inclusion_list`

```python
def process_tx_inclusion_list(state: BeaconState, block: BeaconBlock) -> None:
    # TODO: cap gas usage, comunicate with the engine. 
    state.previous_tx_inclusion_list = state.current_tx_inclusion_list
    state.current_tx_inclusion_list = block.body.tx_inclusion_list
```

