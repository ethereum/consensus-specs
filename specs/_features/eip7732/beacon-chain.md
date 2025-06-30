# EIP-7732 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Payload status](#payload-status)
- [Preset](#preset)
  - [Misc](#misc)
  - [Domain types](#domain-types)
  - [Max operations per block](#max-operations-per-block)
  - [Withdrawal prefixes](#withdrawal-prefixes)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`PayloadAttestationData`](#payloadattestationdata)
    - [`PayloadAttestation`](#payloadattestation)
    - [`PayloadAttestationMessage`](#payloadattestationmessage)
    - [`IndexedPayloadAttestation`](#indexedpayloadattestation)
    - [`SignedExecutionPayloadHeader`](#signedexecutionpayloadheader)
    - [`ExecutionPayloadEnvelope`](#executionpayloadenvelope)
    - [`SignedExecutionPayloadEnvelope`](#signedexecutionpayloadenvelope)
  - [Modified containers](#modified-containers)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`ExecutionPayloadHeader`](#executionpayloadheader)
    - [`BeaconState`](#beaconstate)
- [Helper functions](#helper-functions)
  - [Math](#math)
    - [`bit_floor`](#bit_floor)
  - [Misc](#misc-1)
    - [`remove_flag`](#remove_flag)
  - [Predicates](#predicates)
    - [Modified `is_compounding_withdrawal_credential`](#modified-is_compounding_withdrawal_credential)
    - [New `is_builder_withdrawal_credential`](#new-is_builder_withdrawal_credential)
    - [New `is_builder`](#new-is_builder)
    - [`is_valid_indexed_payload_attestation`](#is_valid_indexed_payload_attestation)
    - [`is_parent_block_full`](#is_parent_block_full)
  - [Beacon State accessors](#beacon-state-accessors)
    - [`get_ptc`](#get_ptc)
    - [Modified `get_attesting_indices`](#modified-get_attesting_indices)
    - [`get_payload_attesting_indices`](#get_payload_attesting_indices)
    - [`get_indexed_payload_attestation`](#get_indexed_payload_attestation)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Withdrawals](#withdrawals)
      - [Modified `process_withdrawals`](#modified-process_withdrawals)
    - [Execution payload header](#execution-payload-header)
      - [New `verify_execution_payload_header_signature`](#new-verify_execution_payload_header_signature)
      - [New `process_execution_payload_header`](#new-process_execution_payload_header)
    - [Operations](#operations)
      - [Modified `process_operations`](#modified-process_operations)
      - [Payload Attestations](#payload-attestations)
        - [`process_payload_attestation`](#process_payload_attestation)
    - [Modified `is_merge_transition_complete`](#modified-is_merge_transition_complete)
    - [Modified `validate_merge_block`](#modified-validate_merge_block)
  - [Execution payload processing](#execution-payload-processing)
    - [New `verify_execution_payload_envelope_signature`](#new-verify_execution_payload_envelope_signature)
    - [New `process_execution_payload`](#new-process_execution_payload)
- [Testing](#testing)
  - [Modified `is_merge_transition_complete`](#modified-is_merge_transition_complete-1)

<!-- mdformat-toc end -->

## Introduction

This is the beacon chain specification of the enshrined proposer builder
separation feature.

*Note*: This specification is built upon
[Electra](../../electra/beacon-chain.md) and is under active development.

This feature adds new staked consensus participants called *Builders* and new
honest validators duties called *payload timeliness attestations*. The slot is
divided in **four** intervals. Honest validators gather *signed bids* (a
`SignedExecutionPayloadHeader`) from builders and submit their consensus blocks
(a `SignedBeaconBlock`) including these bids at the beginning of the slot. At
the start of the second interval, honest validators submit attestations just as
they do previous to this feature). At the start of the third interval,
aggregators aggregate these attestations and the builder broadcasts either a
full payload or a message indicating that they are withholding the payload (a
`SignedExecutionPayloadEnvelope`). At the start of the fourth interval, some
validators selected to be members of the new **Payload Timeliness Committee**
(PTC) attest to the presence and timeliness of the builder's payload.

At any given slot, the status of the blockchain's head may be either

- A block from a previous slot (e.g. the current slot's proposer did not submit
  its block).
- An *empty* block from the current slot (e.g. the proposer submitted a timely
  block, but the builder did not reveal the payload on time).
- A full block for the current slot (both the proposer and the builder revealed
  on time).

## Constants

### Payload status

| Name                     | Value      |
| ------------------------ | ---------- |
| `PAYLOAD_ABSENT`         | `uint8(0)` |
| `PAYLOAD_PRESENT`        | `uint8(1)` |
| `PAYLOAD_WITHHELD`       | `uint8(2)` |
| `PAYLOAD_INVALID_STATUS` | `uint8(3)` |

## Preset

### Misc

| Name       | Value                                     |
| ---------- | ----------------------------------------- |
| `PTC_SIZE` | `uint64(2**9)` (=512) # (New in EIP-7732) |

### Domain types

| Name                    | Value                                          |
| ----------------------- | ---------------------------------------------- |
| `DOMAIN_BEACON_BUILDER` | `DomainType('0x1B000000')` # (New in EIP-7732) |
| `DOMAIN_PTC_ATTESTER`   | `DomainType('0x0C000000')` # (New in EIP-7732) |

### Max operations per block

| Name                       | Value                            |
| -------------------------- | -------------------------------- |
| `MAX_PAYLOAD_ATTESTATIONS` | `2**2` (= 4) # (New in EIP-7732) |

### Withdrawal prefixes

| Name                        | Value            | Description                                                   |
| --------------------------- | ---------------- | ------------------------------------------------------------- |
| `BUILDER_WITHDRAWAL_PREFIX` | `Bytes1('0x03')` | *[New in EIP7732]* Withdrawal credential prefix for a builder |

## Containers

### New containers

#### `PayloadAttestationData`

```python
class PayloadAttestationData(Container):
    beacon_block_root: Root
    slot: Slot
    payload_status: uint8
```

#### `PayloadAttestation`

```python
class PayloadAttestation(Container):
    aggregation_bits: Bitvector[PTC_SIZE]
    data: PayloadAttestationData
    signature: BLSSignature
```

#### `PayloadAttestationMessage`

```python
class PayloadAttestationMessage(Container):
    validator_index: ValidatorIndex
    data: PayloadAttestationData
    signature: BLSSignature
```

#### `IndexedPayloadAttestation`

```python
class IndexedPayloadAttestation(Container):
    attesting_indices: List[ValidatorIndex, PTC_SIZE]
    data: PayloadAttestationData
    signature: BLSSignature
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
    execution_requests: ExecutionRequests
    builder_index: ValidatorIndex
    beacon_block_root: Root
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    payload_withheld: boolean
    state_root: Root
```

#### `SignedExecutionPayloadEnvelope`

```python
class SignedExecutionPayloadEnvelope(Container):
    message: ExecutionPayloadEnvelope
    signature: BLSSignature
```

### Modified containers

#### `BeaconBlockBody`

*Note*: The Beacon Block body is modified to contain a
`Signed ExecutionPayloadHeader`. The containers `BeaconBlock` and
`SignedBeaconBlock` are modified indirectly. The field `execution_requests` is
removed from the beacon block body and moved into the signed execution payload
envelope.

*Note*: `execution_payload`, `blob_kzg_commitments`, and `execution_requests`
have been removed.

```python
class BeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data
    graffiti: Bytes32
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS_ELECTRA]
    attestations: List[Attestation, MAX_ATTESTATIONS_ELECTRA]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]
    # [New in EIP-7732]
    signed_execution_payload_header: SignedExecutionPayloadHeader
    # [New in EIP-7732]
    payload_attestations: List[PayloadAttestation, MAX_PAYLOAD_ATTESTATIONS]
```

#### `ExecutionPayloadHeader`

*Note*: The `ExecutionPayloadHeader` is modified to only contain the block hash
of the committed `ExecutionPayload` in addition to the builder's payment
information, gas limit and KZG commitments root to verify the inclusion proofs.

```python
class ExecutionPayloadHeader(Container):
    parent_block_hash: Hash32
    parent_block_root: Root
    block_hash: Hash32
    gas_limit: uint64
    builder_index: ValidatorIndex
    slot: Slot
    value: Gwei
    blob_kzg_commitments_root: Root
```

#### `BeaconState`

*Note*: The `BeaconState` is modified to track the last withdrawals honored in
the CL. The `latest_execution_payload_header` is modified semantically to refer
not to a past committed `ExecutionPayload` but instead it corresponds to the
state's slot builder's bid. Another addition is to track the last committed
block hash and the last slot that was full, that is in which there were both
consensus and execution blocks included.

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
    latest_execution_payload_header: ExecutionPayloadHeader
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
    # [New in EIP-7732]
    latest_block_hash: Hash32
    # [New in EIP-7732]
    latest_full_slot: Slot
    # [New in EIP-7732]
    latest_withdrawals_root: Root
```

## Helper functions

### Math

#### `bit_floor`

```python
def bit_floor(n: uint64) -> uint64:
    """
    if ``n`` is not zero, returns the largest power of `2` that is not greater than `n`.
    """
    if n == 0:
        return 0
    return uint64(1) << (n.bit_length() - 1)
```

### Misc

#### `remove_flag`

```python
def remove_flag(flags: ParticipationFlags, flag_index: int) -> ParticipationFlags:
    flag = ParticipationFlags(2**flag_index)
    return flags & ~flag
```

### Predicates

#### Modified `is_compounding_withdrawal_credential`

```python
def is_compounding_withdrawal_credential(withdrawal_credentials: Bytes32) -> bool:
    prefix = withdrawal_credentials[:1]
    return prefix == COMPOUNDING_WITHDRAWAL_PREFIX or prefix == BUILDER_WITHDRAWAL_PREFIX
```

#### New `is_builder_withdrawal_credential`

```python
def is_builder_withdrawal_credential(withdrawal_credentials: Bytes32) -> bool:
    return withdrawal_credentials[:1] == BUILDER_WITHDRAWAL_PREFIX
```

#### New `is_builder`

```python
def is_builder(validator: Validator) -> bool:
    """
    Check if ``validator`` has an 0x03 prefixed "builder" withdrawal credential.
    """
    return is_builder_withdrawal_credential(validator.withdrawal_credentials)
```

#### `is_valid_indexed_payload_attestation`

```python
def is_valid_indexed_payload_attestation(
    state: BeaconState, indexed_payload_attestation: IndexedPayloadAttestation
) -> bool:
    """
    Check if ``indexed_payload_attestation`` is not empty, has sorted and unique indices and has
    a valid aggregate signature.
    """
    # Verify the data is valid
    if indexed_payload_attestation.data.payload_status >= PAYLOAD_INVALID_STATUS:
        return False

    # Verify indices are sorted and unique
    indices = indexed_payload_attestation.attesting_indices
    if len(indices) == 0 or not indices == sorted(set(indices)):
        return False

    # Verify aggregate signature
    pubkeys = [state.validators[i].pubkey for i in indices]
    domain = get_domain(state, DOMAIN_PTC_ATTESTER, None)
    signing_root = compute_signing_root(indexed_payload_attestation.data, domain)
    return bls.FastAggregateVerify(pubkeys, signing_root, indexed_payload_attestation.signature)
```

#### `is_parent_block_full`

This function returns true if the last committed payload header was fulfilled
with a payload, this can only happen when both beacon block and payload were
present. This function must be called on a beacon state before processing the
execution payload header in the block.

```python
def is_parent_block_full(state: BeaconState) -> bool:
    return state.latest_execution_payload_header.block_hash == state.latest_block_hash
```

### Beacon State accessors

#### `get_ptc`

```python
def get_ptc(state: BeaconState, slot: Slot) -> Vector[ValidatorIndex, PTC_SIZE]:
    """
    Get the payload timeliness committee for the given ``slot``
    """
    epoch = compute_epoch_at_slot(slot)
    committees_per_slot = bit_floor(min(get_committee_count_per_slot(state, epoch), PTC_SIZE))
    members_per_committee = PTC_SIZE // committees_per_slot

    validator_indices: List[ValidatorIndex] = []
    for idx in range(committees_per_slot):
        beacon_committee = get_beacon_committee(state, slot, CommitteeIndex(idx))
        validator_indices += beacon_committee[:members_per_committee]
    return validator_indices
```

#### Modified `get_attesting_indices`

`get_attesting_indices` is modified to ignore PTC votes

```python
def get_attesting_indices(state: BeaconState, attestation: Attestation) -> Set[ValidatorIndex]:
    """
    Return the set of attesting indices corresponding to ``aggregation_bits`` and ``committee_bits``.
    """
    output: Set[ValidatorIndex] = set()
    committee_indices = get_committee_indices(attestation.committee_bits)
    committee_offset = 0
    for index in committee_indices:
        committee = get_beacon_committee(state, attestation.data.slot, index)
        committee_attesters = set(
            index
            for i, index in enumerate(committee)
            if attestation.aggregation_bits[committee_offset + i]
        )
        output = output.union(committee_attesters)
        committee_offset += len(committee)

    if compute_epoch_at_slot(attestation.data.slot) < EIP7732_FORK_EPOCH:
        return output
    ptc = get_ptc(state, attestation.data.slot)
    return set(i for i in output if i not in ptc)
```

#### `get_payload_attesting_indices`

```python
def get_payload_attesting_indices(
    state: BeaconState, slot: Slot, payload_attestation: PayloadAttestation
) -> Set[ValidatorIndex]:
    """
    Return the set of attesting indices corresponding to ``payload_attestation``.
    """
    ptc = get_ptc(state, slot)
    return set(index for i, index in enumerate(ptc) if payload_attestation.aggregation_bits[i])
```

#### `get_indexed_payload_attestation`

```python
def get_indexed_payload_attestation(
    state: BeaconState, slot: Slot, payload_attestation: PayloadAttestation
) -> IndexedPayloadAttestation:
    """
    Return the indexed payload attestation corresponding to ``payload_attestation``.
    """
    attesting_indices = get_payload_attesting_indices(state, slot, payload_attestation)

    return IndexedPayloadAttestation(
        attesting_indices=sorted(attesting_indices),
        data=payload_attestation.data,
        signature=payload_attestation.signature,
    )
```

## Beacon chain state transition function

*Note*: state transition is fundamentally modified in EIP-7732. The full state
transition is broken in two parts, first importing a signed block and then
importing an execution payload.

The post-state corresponding to a pre-state `state` and a signed beacon block
`signed_block` is defined as `state_transition(state, signed_block)`. State
transitions that trigger an unhandled exception (e.g. a failed `assert` or an
out-of-range list access) are considered invalid. State transitions that cause a
`uint64` overflow or underflow are also considered invalid.

The post-state corresponding to a pre-state `state` and a signed execution
payload envelope `signed_envelope` is defined as
`process_execution_payload(state, signed_envelope)`. State transitions that
trigger an unhandled exception (e.g. a failed `assert` or an out-of-range list
access) are considered invalid. State transitions that cause an `uint64`
overflow or underflow are also considered invalid.

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_withdrawals(state)  # [Modified in EIP-7732]
    # Removed `process_execution_payload` in EIP-7732
    process_execution_payload_header(state, block)  # [New in EIP-7732]
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)  # [Modified in EIP-7732]
    process_sync_aggregate(state, block.body.sync_aggregate)
```

#### Withdrawals

##### Modified `process_withdrawals`

*Note*: This is modified to take only the `state` as parameter. Withdrawals are
deterministic given the beacon state, any execution payload that has the
corresponding block as parent beacon block is required to honor these
withdrawals in the execution layer. This function must be called before
`process_execution_payload_header` as this latter function affects validator
balances.

```python
def process_withdrawals(state: BeaconState) -> None:
    # return early if the parent block was empty
    if not is_parent_block_full(state):
        return

    withdrawals, partial_withdrawals_count = get_expected_withdrawals(state)
    withdrawals_list = List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD](withdrawals)
    state.latest_withdrawals_root = hash_tree_root(withdrawals_list)
    for withdrawal in withdrawals:
        decrease_balance(state, withdrawal.validator_index, withdrawal.amount)

    # Update pending partial withdrawals
    state.pending_partial_withdrawals = state.pending_partial_withdrawals[
        partial_withdrawals_count:
    ]

    # Update the next withdrawal index if this block contained withdrawals
    if len(withdrawals) != 0:
        latest_withdrawal = withdrawals[-1]
        state.next_withdrawal_index = WithdrawalIndex(latest_withdrawal.index + 1)

    # Update the next validator index to start the next withdrawal sweep
    if len(withdrawals) == MAX_WITHDRAWALS_PER_PAYLOAD:
        # Next sweep starts after the latest withdrawal's validator index
        next_validator_index = ValidatorIndex(
            (withdrawals[-1].validator_index + 1) % len(state.validators)
        )
        state.next_withdrawal_validator_index = next_validator_index
    else:
        # Advance sweep by the max length of the sweep if there was not a full set of withdrawals
        next_index = state.next_withdrawal_validator_index + MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP
        next_validator_index = ValidatorIndex(next_index % len(state.validators))
        state.next_withdrawal_validator_index = next_validator_index
```

#### Execution payload header

##### New `verify_execution_payload_header_signature`

```python
def verify_execution_payload_header_signature(
    state: BeaconState, signed_header: SignedExecutionPayloadHeader
) -> bool:
    # Check the signature
    builder = state.validators[signed_header.message.builder_index]
    signing_root = compute_signing_root(
        signed_header.message, get_domain(state, DOMAIN_BEACON_BUILDER)
    )
    return bls.Verify(builder.pubkey, signing_root, signed_header.signature)
```

##### New `process_execution_payload_header`

```python
def process_execution_payload_header(state: BeaconState, block: BeaconBlock) -> None:
    # Verify the header signature
    signed_header = block.body.signed_execution_payload_header
    assert verify_execution_payload_header_signature(state, signed_header)

    # Check that the builder is active non-slashed has funds to cover the bid
    header = signed_header.message
    builder_index = header.builder_index
    builder = state.validators[builder_index]
    assert is_active_validator(builder, get_current_epoch(state))
    assert not builder.slashed
    amount = header.value
    assert state.balances[builder_index] >= amount

    # Check that the builder is registered as a builder unless self-building with zero value
    if not is_builder(builder):
        assert builder_index == block.proposer_index
        assert amount == 0

    # Verify that the bid is for the current slot
    assert header.slot == block.slot
    # Verify that the bid is for the right parent block
    assert header.parent_block_hash == state.latest_block_hash
    assert header.parent_block_root == block.parent_root

    # Transfer the funds from the builder to the proposer
    decrease_balance(state, builder_index, amount)
    increase_balance(state, block.proposer_index, amount)

    # Cache the signed execution payload header
    state.latest_execution_payload_header = header
```

#### Operations

##### Modified `process_operations`

*Note*: `process_operations` is modified to process PTC attestations

```python
def process_operations(state: BeaconState, body: BeaconBlockBody) -> None:
    # Verify that outstanding deposits are processed up to the maximum number of deposits
    assert len(body.deposits) == min(
        MAX_DEPOSITS, state.eth1_data.deposit_count - state.eth1_deposit_index
    )

    def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
        for operation in operations:
            fn(state, operation)

    for_ops(body.proposer_slashings, process_proposer_slashing)
    for_ops(body.attester_slashings, process_attester_slashing)
    for_ops(body.attestations, process_attestation)
    for_ops(body.deposits, process_deposit)
    for_ops(body.voluntary_exits, process_voluntary_exit)
    for_ops(body.bls_to_execution_changes, process_bls_to_execution_change)
    # Removed `process_deposit_request` in EIP-7732
    # Removed `process_withdrawal_request` in EIP-7732
    # Removed `process_consolidation_request` in EIP-7732
    for_ops(body.payload_attestations, process_payload_attestation)  # [New in EIP-7732]
```

##### Payload Attestations

###### `process_payload_attestation`

```python
def process_payload_attestation(
    state: BeaconState, payload_attestation: PayloadAttestation
) -> None:
    # Check that the attestation is for the parent beacon block
    data = payload_attestation.data
    assert data.beacon_block_root == state.latest_block_header.parent_root
    # Check that the attestation is for the previous slot
    assert data.slot + 1 == state.slot

    # Verify signature
    indexed_payload_attestation = get_indexed_payload_attestation(
        state, data.slot, payload_attestation
    )
    assert is_valid_indexed_payload_attestation(state, indexed_payload_attestation)

    if state.slot % SLOTS_PER_EPOCH == 0:
        epoch_participation = state.previous_epoch_participation
    else:
        epoch_participation = state.current_epoch_participation

    # Return early if the attestation is for the wrong payload status
    payload_was_present = data.slot == state.latest_full_slot
    voted_present = data.payload_status == PAYLOAD_PRESENT
    proposer_reward_denominator = (
        (WEIGHT_DENOMINATOR - PROPOSER_WEIGHT) * WEIGHT_DENOMINATOR // PROPOSER_WEIGHT
    )
    proposer_index = get_beacon_proposer_index(state)
    if voted_present != payload_was_present:
        # Unset the flags in case they were set by an equivocating ptc attestation
        proposer_penalty_numerator = 0
        for index in indexed_payload_attestation.attesting_indices:
            for flag_index, weight in enumerate(PARTICIPATION_FLAG_WEIGHTS):
                if has_flag(epoch_participation[index], flag_index):
                    epoch_participation[index] = remove_flag(epoch_participation[index], flag_index)
                    proposer_penalty_numerator += get_base_reward(state, index) * weight
        # Penalize the proposer
        proposer_penalty = Gwei(2 * proposer_penalty_numerator // proposer_reward_denominator)
        decrease_balance(state, proposer_index, proposer_penalty)
        return

    # Reward the proposer and set all the participation flags in case of correct attestations
    proposer_reward_numerator = 0
    for index in indexed_payload_attestation.attesting_indices:
        for flag_index, weight in enumerate(PARTICIPATION_FLAG_WEIGHTS):
            if not has_flag(epoch_participation[index], flag_index):
                epoch_participation[index] = add_flag(epoch_participation[index], flag_index)
                proposer_reward_numerator += get_base_reward(state, index) * weight

    # Reward proposer
    proposer_reward = Gwei(proposer_reward_numerator // proposer_reward_denominator)
    increase_balance(state, proposer_index, proposer_reward)
```

#### Modified `is_merge_transition_complete`

`is_merge_transition_complete` is modified only for testing purposes to add the
blob kzg commitments root for an empty list

```python
def is_merge_transition_complete(state: BeaconState) -> bool:
    header = ExecutionPayloadHeader()
    kzgs = List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]()
    header.blob_kzg_commitments_root = kzgs.hash_tree_root()

    return state.latest_execution_payload_header != header
```

#### Modified `validate_merge_block`

`validate_merge_block` is modified to use the new
`signed_execution_payload_header` message in the Beacon Block Body

```python
def validate_merge_block(block: BeaconBlock) -> None:
    """
    Check the parent PoW block of execution payload is a valid terminal PoW block.

    Note: Unavailable PoW block(s) may later become available,
    and a client software MAY delay a call to ``validate_merge_block``
    until the PoW block(s) become available.
    """
    if TERMINAL_BLOCK_HASH != Hash32():
        # If `TERMINAL_BLOCK_HASH` is used as an override, the activation epoch must be reached.
        assert compute_epoch_at_slot(block.slot) >= TERMINAL_BLOCK_HASH_ACTIVATION_EPOCH
        assert (
            block.body.signed_execution_payload_header.message.parent_block_hash
            == TERMINAL_BLOCK_HASH
        )
        return

    # Modified in EIP-7732
    pow_block = get_pow_block(block.body.signed_execution_payload_header.message.parent_block_hash)
    # Check if `pow_block` is available
    assert pow_block is not None
    pow_parent = get_pow_block(pow_block.parent_hash)
    # Check if `pow_parent` is available
    assert pow_parent is not None
    # Check if `pow_block` is a valid terminal PoW block
    assert is_valid_terminal_pow_block(pow_block, pow_parent)
```

### Execution payload processing

#### New `verify_execution_payload_envelope_signature`

```python
def verify_execution_payload_envelope_signature(
    state: BeaconState, signed_envelope: SignedExecutionPayloadEnvelope
) -> bool:
    builder = state.validators[signed_envelope.message.builder_index]
    signing_root = compute_signing_root(
        signed_envelope.message, get_domain(state, DOMAIN_BEACON_BUILDER)
    )
    return bls.Verify(builder.pubkey, signing_root, signed_envelope.signature)
```

#### New `process_execution_payload`

*Note*: `process_execution_payload` is now an independent check in state
transition. It is called when importing a signed execution payload proposed by
the builder of the current slot.

```python
def process_execution_payload(
    state: BeaconState,
    signed_envelope: SignedExecutionPayloadEnvelope,
    execution_engine: ExecutionEngine,
    verify: bool = True,
) -> None:
    # Verify signature
    if verify:
        assert verify_execution_payload_envelope_signature(state, signed_envelope)
    envelope = signed_envelope.message
    payload = envelope.payload
    # Cache latest block header state root
    previous_state_root = hash_tree_root(state)
    if state.latest_block_header.state_root == Root():
        state.latest_block_header.state_root = previous_state_root

    # Verify consistency with the beacon block
    assert envelope.beacon_block_root == hash_tree_root(state.latest_block_header)

    # Verify consistency with the committed header
    committed_header = state.latest_execution_payload_header
    assert envelope.builder_index == committed_header.builder_index
    assert committed_header.blob_kzg_commitments_root == hash_tree_root(
        envelope.blob_kzg_commitments
    )

    if not envelope.payload_withheld:
        # Verify the withdrawals root
        assert hash_tree_root(payload.withdrawals) == state.latest_withdrawals_root

        # Verify the gas_limit
        assert committed_header.gas_limit == payload.gas_limit

        assert committed_header.block_hash == payload.block_hash
        # Verify consistency of the parent hash with respect to the previous execution payload
        assert payload.parent_hash == state.latest_block_hash
        # Verify prev_randao
        assert payload.prev_randao == get_randao_mix(state, get_current_epoch(state))
        # Verify timestamp
        assert payload.timestamp == compute_time_at_slot(state, state.slot)
        # Verify commitments are under limit
        assert len(envelope.blob_kzg_commitments) <= MAX_BLOBS_PER_BLOCK
        # Verify the execution payload is valid
        versioned_hashes = [
            kzg_commitment_to_versioned_hash(commitment)
            for commitment in envelope.blob_kzg_commitments
        ]
        requests = envelope.execution_requests
        assert execution_engine.verify_and_notify_new_payload(
            NewPayloadRequest(
                execution_payload=payload,
                versioned_hashes=versioned_hashes,
                parent_beacon_block_root=state.latest_block_header.parent_root,
                execution_requests=requests,
            )
        )

        # Process Electra operations
        def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
            for operation in operations:
                fn(state, operation)

        for_ops(requests.deposits, process_deposit_request)
        for_ops(requests.withdrawals, process_withdrawal_request)
        for_ops(requests.consolidations, process_consolidation_request)

        # Cache the execution payload header and proposer
        state.latest_block_hash = payload.block_hash
        state.latest_full_slot = state.slot

    # Verify the state root
    if verify:
        assert envelope.state_root == hash_tree_root(state)
```

## Testing

### Modified `is_merge_transition_complete`

The function `is_merge_transition_complete` is modified for test purposes only
to include the hash tree root of the empty KZG commitment list

```python
def is_merge_transition_complete(state: BeaconState) -> bool:
    header = ExecutionPayloadHeader()
    kzgs = List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]()
    header.blob_kzg_commitments_root = kzgs.hash_tree_root()

    return state.latest_execution_payload_header != header
```
