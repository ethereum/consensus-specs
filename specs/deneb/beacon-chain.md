# Deneb -- The Beacon Chain

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Constants](#constants)
  - [Blob](#blob)
- [Preset](#preset)
  - [Execution](#execution)
- [Configuration](#configuration)
  - [Execution](#execution-1)
  - [Validator cycle](#validator-cycle)
- [Containers](#containers)
  - [Modified containers](#modified-containers)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`ExecutionPayload`](#executionpayload)
    - [`ExecutionPayloadHeader`](#executionpayloadheader)
    - [`BeaconState`](#beaconstate)
- [Helper functions](#helper-functions)
  - [Misc](#misc)
    - [`kzg_commitment_to_versioned_hash`](#kzg_commitment_to_versioned_hash)
  - [Beacon state accessors](#beacon-state-accessors)
    - [Modified `get_attestation_participation_flag_indices`](#modified-get_attestation_participation_flag_indices)
    - [New `get_validator_activation_churn_limit`](#new-get_validator_activation_churn_limit)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Execution engine](#execution-engine)
    - [Request data](#request-data)
      - [Modified `NewPayloadRequest`](#modified-newpayloadrequest)
    - [Engine APIs](#engine-apis)
      - [`is_valid_block_hash`](#is_valid_block_hash)
      - [`is_valid_versioned_hashes`](#is_valid_versioned_hashes)
      - [Modified `notify_new_payload`](#modified-notify_new_payload)
      - [Modified `verify_and_notify_new_payload`](#modified-verify_and_notify_new_payload)
  - [Block processing](#block-processing)
    - [Modified `process_attestation`](#modified-process_attestation)
    - [Execution payload](#execution-payload)
      - [Modified `process_execution_payload`](#modified-process_execution_payload)
    - [Modified `process_voluntary_exit`](#modified-process_voluntary_exit)
  - [Epoch processing](#epoch-processing)
    - [Registry updates](#registry-updates)

<!-- mdformat-toc end -->

## Introduction

Deneb is a consensus-layer upgrade containing a number of features. Including:

- [EIP-4788](https://eips.ethereum.org/EIPS/eip-4788): Beacon block root in the
  EVM
- [EIP-4844](https://eips.ethereum.org/EIPS/eip-4844): Shard Blob Transactions
  scale data-availability of Ethereum in a simple, forwards-compatible manner
- [EIP-7044](https://eips.ethereum.org/EIPS/eip-7044): Perpetually Valid Signed
  Voluntary Exits
- [EIP-7045](https://eips.ethereum.org/EIPS/eip-7045): Increase Max Attestation
  Inclusion Slot
- [EIP-7514](https://eips.ethereum.org/EIPS/eip-7514): Add Max Epoch Churn Limit

## Custom types

| Name            | SSZ equivalent | Description              |
| --------------- | -------------- | ------------------------ |
| `VersionedHash` | `Bytes32`      | *[New in Deneb:EIP4844]* |
| `BlobIndex`     | `uint64`       | *[New in Deneb:EIP4844]* |

## Constants

### Blob

| Name                         | Value            |
| ---------------------------- | ---------------- |
| `VERSIONED_HASH_VERSION_KZG` | `Bytes1('0x01')` |

## Preset

### Execution

| Name                             | Value                    | Description                                                                                                              |
| -------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| `MAX_BLOB_COMMITMENTS_PER_BLOCK` | `uint64(2**12)` (= 4096) | *[New in Deneb:EIP4844]* hardfork independent fixed theoretical limit same as `TARGET_BLOB_GAS_PER_BLOCK` (see EIP 4844) |

## Configuration

### Execution

| Name                  | Value       | Description                                                                                                    |
| --------------------- | ----------- | -------------------------------------------------------------------------------------------------------------- |
| `MAX_BLOBS_PER_BLOCK` | `uint64(6)` | *[New in Deneb:EIP4844]* maximum number of blobs in a single block limited by `MAX_BLOB_COMMITMENTS_PER_BLOCK` |

*Note*: The blob transactions are packed into the execution payload by the
EL/builder with their corresponding blobs being independently transmitted and
are limited by `MAX_BLOB_GAS_PER_BLOCK // GAS_PER_BLOB`. However the CL limit is
independently defined by `MAX_BLOBS_PER_BLOCK`.

### Validator cycle

| Name                                   | Value                |
| -------------------------------------- | -------------------- |
| `MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT` | `uint64(2**3)` (= 8) |

## Containers

### Modified containers

#### `BeaconBlockBody`

*Note*: `BeaconBlock` and `SignedBeaconBlock` types are updated indirectly.

```python
class BeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data
    graffiti: Bytes32
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS]
    attestations: List[Attestation, MAX_ATTESTATIONS]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    # [Modified in Deneb:EIP4844]
    execution_payload: ExecutionPayload
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]
    # [New in Deneb:EIP4844]
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
```

#### `ExecutionPayload`

```python
class ExecutionPayload(Container):
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
    block_hash: Hash32
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]
    withdrawals: List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD]
    # [New in Deneb:EIP4844]
    blob_gas_used: uint64
    # [New in Deneb:EIP4844]
    excess_blob_gas: uint64
```

#### `ExecutionPayloadHeader`

```python
class ExecutionPayloadHeader(Container):
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
    block_hash: Hash32
    transactions_root: Root
    withdrawals_root: Root
    # [New in Deneb:EIP4844]
    blob_gas_used: uint64
    # [New in Deneb:EIP4844]
    excess_blob_gas: uint64
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
    # [Modified in Deneb:EIP4844]
    latest_execution_payload_header: ExecutionPayloadHeader
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
    historical_summaries: List[HistoricalSummary, HISTORICAL_ROOTS_LIMIT]
```

## Helper functions

### Misc

#### `kzg_commitment_to_versioned_hash`

```python
def kzg_commitment_to_versioned_hash(kzg_commitment: KZGCommitment) -> VersionedHash:
    return VERSIONED_HASH_VERSION_KZG + hash(kzg_commitment)[1:]
```

### Beacon state accessors

#### Modified `get_attestation_participation_flag_indices`

*Note*: The function `get_attestation_participation_flag_indices` is modified to
set the `TIMELY_TARGET_FLAG` for any correct target attestation, regardless of
`inclusion_delay` as a baseline reward for any speed of inclusion of an
attestation that contributes to justification of the contained chain for
EIP-7045.

```python
def get_attestation_participation_flag_indices(
    state: BeaconState, data: AttestationData, inclusion_delay: uint64
) -> Sequence[int]:
    """
    Return the flag indices that are satisfied by an attestation.
    """
    # Matching source
    if data.target.epoch == get_current_epoch(state):
        justified_checkpoint = state.current_justified_checkpoint
    else:
        justified_checkpoint = state.previous_justified_checkpoint
    is_matching_source = data.source == justified_checkpoint

    # Matching target
    target_root = get_block_root(state, data.target.epoch)
    target_root_matches = data.target.root == target_root
    is_matching_target = is_matching_source and target_root_matches

    # Matching head
    head_root = get_block_root_at_slot(state, data.slot)
    head_root_matches = data.beacon_block_root == head_root
    is_matching_head = is_matching_target and head_root_matches

    assert is_matching_source

    participation_flag_indices = []
    if is_matching_source and inclusion_delay <= integer_squareroot(SLOTS_PER_EPOCH):
        participation_flag_indices.append(TIMELY_SOURCE_FLAG_INDEX)
    # [Modified in Deneb:EIP7045]
    if is_matching_target:
        participation_flag_indices.append(TIMELY_TARGET_FLAG_INDEX)
    if is_matching_head and inclusion_delay == MIN_ATTESTATION_INCLUSION_DELAY:
        participation_flag_indices.append(TIMELY_HEAD_FLAG_INDEX)

    return participation_flag_indices
```

#### New `get_validator_activation_churn_limit`

```python
def get_validator_activation_churn_limit(state: BeaconState) -> uint64:
    """
    Return the validator activation churn limit for the current epoch.
    """
    return min(MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT, get_validator_churn_limit(state))
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
```

#### Engine APIs

##### `is_valid_block_hash`

*Note*: The function `is_valid_block_hash` is modified to include the additional
`parent_beacon_block_root` parameter for EIP-4788.

```python
def is_valid_block_hash(
    self: ExecutionEngine, execution_payload: ExecutionPayload, parent_beacon_block_root: Root
) -> bool:
    """
    Return ``True`` if and only if ``execution_payload.block_hash`` is computed correctly.
    """
    ...
```

##### `is_valid_versioned_hashes`

```python
def is_valid_versioned_hashes(
    self: ExecutionEngine, new_payload_request: NewPayloadRequest
) -> bool:
    """
    Return ``True`` if and only if the version hashes computed by the blob transactions of
    ``new_payload_request.execution_payload`` matches ``new_payload_request.versioned_hashes``.
    """
    ...
```

##### Modified `notify_new_payload`

*Note*: The function `notify_new_payload` is modified to include the additional
`parent_beacon_block_root` parameter for EIP-4788.

```python
def notify_new_payload(
    self: ExecutionEngine, execution_payload: ExecutionPayload, parent_beacon_block_root: Root
) -> bool:
    """
    Return ``True`` if and only if ``execution_payload`` is valid with respect to ``self.execution_state``.
    """
    ...
```

##### Modified `verify_and_notify_new_payload`

```python
def verify_and_notify_new_payload(
    self: ExecutionEngine, new_payload_request: NewPayloadRequest
) -> bool:
    """
    Return ``True`` if and only if ``new_payload_request`` is valid with respect to ``self.execution_state``.
    """
    execution_payload = new_payload_request.execution_payload
    # [New in Deneb:EIP4788]
    parent_beacon_block_root = new_payload_request.parent_beacon_block_root

    if b"" in execution_payload.transactions:
        return False

    # [Modified in Deneb:EIP4788]
    if not self.is_valid_block_hash(execution_payload, parent_beacon_block_root):
        return False

    # [New in Deneb:EIP4844]
    if not self.is_valid_versioned_hashes(new_payload_request):
        return False

    # [Modified in Deneb:EIP4788]
    if not self.notify_new_payload(execution_payload, parent_beacon_block_root):
        return False

    return True
```

### Block processing

#### Modified `process_attestation`

*Note*: The function `process_attestation` is modified to expand valid slots for
inclusion to those in both `target.epoch` epoch and `target.epoch + 1` epoch for
EIP-7045. Additionally, it utilizes an updated version of
`get_attestation_participation_flag_indices` to ensure rewards are available for
the extended attestation inclusion range for EIP-7045.

```python
def process_attestation(state: BeaconState, attestation: Attestation) -> None:
    data = attestation.data
    assert data.target.epoch in (get_previous_epoch(state), get_current_epoch(state))
    assert data.target.epoch == compute_epoch_at_slot(data.slot)
    # [Modified in Deneb:EIP7045]
    assert data.slot + MIN_ATTESTATION_INCLUSION_DELAY <= state.slot
    assert data.index < get_committee_count_per_slot(state, data.target.epoch)

    committee = get_beacon_committee(state, data.slot, data.index)
    assert len(attestation.aggregation_bits) == len(committee)

    # Participation flag indices
    participation_flag_indices = get_attestation_participation_flag_indices(
        state, data, state.slot - data.slot
    )

    # Verify signature
    assert is_valid_indexed_attestation(state, get_indexed_attestation(state, attestation))

    # Update epoch participation flags
    if data.target.epoch == get_current_epoch(state):
        epoch_participation = state.current_epoch_participation
    else:
        epoch_participation = state.previous_epoch_participation

    proposer_reward_numerator = 0
    for index in get_attesting_indices(state, attestation):
        for flag_index, weight in enumerate(PARTICIPATION_FLAG_WEIGHTS):
            if flag_index in participation_flag_indices and not has_flag(
                epoch_participation[index], flag_index
            ):
                epoch_participation[index] = add_flag(epoch_participation[index], flag_index)
                proposer_reward_numerator += get_base_reward(state, index) * weight

    # Reward proposer
    proposer_reward_denominator = (
        (WEIGHT_DENOMINATOR - PROPOSER_WEIGHT) * WEIGHT_DENOMINATOR // PROPOSER_WEIGHT
    )
    proposer_reward = Gwei(proposer_reward_numerator // proposer_reward_denominator)
    increase_balance(state, get_beacon_proposer_index(state), proposer_reward)
```

#### Execution payload

##### Modified `process_execution_payload`

*Note*: The function `process_execution_payload` is modified to pass
`versioned_hashes` into `execution_engine.verify_and_notify_new_payload` and to
assign the new fields in `ExecutionPayloadHeader` for EIP-4844. It is also
modified to pass in the parent beacon block root to support EIP-4788.

```python
def process_execution_payload(
    state: BeaconState, body: BeaconBlockBody, execution_engine: ExecutionEngine
) -> None:
    payload = body.execution_payload

    # Verify consistency of the parent hash with respect to the previous execution payload header
    assert payload.parent_hash == state.latest_execution_payload_header.block_hash
    # Verify prev_randao
    assert payload.prev_randao == get_randao_mix(state, get_current_epoch(state))
    # Verify timestamp
    assert payload.timestamp == compute_time_at_slot(state, state.slot)
    # [New in Deneb:EIP4844]
    # Verify commitments are under limit
    assert len(body.blob_kzg_commitments) <= MAX_BLOBS_PER_BLOCK

    # [New in Deneb:EIP4844]
    # Compute list of versioned hashes
    versioned_hashes = [
        kzg_commitment_to_versioned_hash(commitment) for commitment in body.blob_kzg_commitments
    ]

    # Verify the execution payload is valid
    assert execution_engine.verify_and_notify_new_payload(
        NewPayloadRequest(
            execution_payload=payload,
            # [New in Deneb:EIP4844]
            versioned_hashes=versioned_hashes,
            # [New in Deneb:EIP4788]
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
        # [New in Deneb:EIP4844]
        blob_gas_used=payload.blob_gas_used,
        # [New in Deneb:EIP4844]
        excess_blob_gas=payload.excess_blob_gas,
    )
```

#### Modified `process_voluntary_exit`

*Note*: The function `process_voluntary_exit` is modified to use the fixed fork
version -- `CAPELLA_FORK_VERSION` -- for EIP-7044.

```python
def process_voluntary_exit(state: BeaconState, signed_voluntary_exit: SignedVoluntaryExit) -> None:
    voluntary_exit = signed_voluntary_exit.message
    validator = state.validators[voluntary_exit.validator_index]
    # Verify the validator is active
    assert is_active_validator(validator, get_current_epoch(state))
    # Verify exit has not been initiated
    assert validator.exit_epoch == FAR_FUTURE_EPOCH
    # Exits must specify an epoch when they become valid; they are not valid before then
    assert get_current_epoch(state) >= voluntary_exit.epoch
    # Verify the validator has been active long enough
    assert get_current_epoch(state) >= validator.activation_epoch + SHARD_COMMITTEE_PERIOD
    # Verify signature
    # [Modified in Deneb:EIP7044]
    domain = compute_domain(
        DOMAIN_VOLUNTARY_EXIT, CAPELLA_FORK_VERSION, state.genesis_validators_root
    )
    signing_root = compute_signing_root(voluntary_exit, domain)
    assert bls.Verify(validator.pubkey, signing_root, signed_voluntary_exit.signature)
    # Initiate exit
    initiate_validator_exit(state, voluntary_exit.validator_index)
```

### Epoch processing

#### Registry updates

*Note*: The function `process_registry_updates` is modified to utilize
`get_validator_activation_churn_limit()` to rate limit the activation queue for
EIP-7514.

```python
def process_registry_updates(state: BeaconState) -> None:
    # Process activation eligibility and ejections
    for index, validator in enumerate(state.validators):
        if is_eligible_for_activation_queue(validator):
            validator.activation_eligibility_epoch = get_current_epoch(state) + 1

        if (
            is_active_validator(validator, get_current_epoch(state))
            and validator.effective_balance <= EJECTION_BALANCE
        ):
            initiate_validator_exit(state, ValidatorIndex(index))

    # Queue validators eligible for activation and not yet dequeued for activation
    activation_queue = sorted(
        [
            index
            for index, validator in enumerate(state.validators)
            if is_eligible_for_activation(state, validator)
        ],
        # Order by the sequence of activation_eligibility_epoch setting and then index
        key=lambda index: (state.validators[index].activation_eligibility_epoch, index),
    )
    # Dequeued validators for activation up to activation churn limit
    # [Modified in Deneb:EIP7514]
    for index in activation_queue[: get_validator_activation_churn_limit(state)]:
        validator = state.validators[index]
        validator.activation_epoch = compute_activation_exit_epoch(get_current_epoch(state))
```
