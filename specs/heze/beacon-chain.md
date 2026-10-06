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
- [Configs](#configs)
  - [Time parameters](#time-parameters)
  - [Blob schedule](#blob-schedule)
  - [Gas limit schedule](#gas-limit-schedule)
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
  - [Misc](#misc)
    - [New `get_slot_durations`](#new-get_slot_durations)
    - [New `get_slot_duration_ms`](#new-get_slot_duration_ms)
    - [Modified `compute_time_at_slot_ms`](#modified-compute_time_at_slot_ms)
    - [Modified `compute_slot_at_time_ms`](#modified-compute_slot_at_time_ms)
  - [Predicates](#predicates)
    - [New `is_valid_inclusion_list_signature`](#new-is_valid_inclusion_list_signature)
  - [Beacon state accessors](#beacon-state-accessors)
    - [New `get_inclusion_list_committee`](#new-get_inclusion_list_committee)
    - [Modified `get_base_reward_per_increment`](#modified-get_base_reward_per_increment)
    - [Modified `get_base_reward`](#modified-get_base_reward)
    - [Modified `get_flag_index_deltas`](#modified-get_flag_index_deltas)
    - [Modified `get_inactivity_penalty_deltas`](#modified-get_inactivity_penalty_deltas)
    - [Modified `get_activation_churn_limit`](#modified-get_activation_churn_limit)
    - [Modified `get_exit_churn_limit`](#modified-get_exit_churn_limit)
    - [Modified `get_consolidation_churn_limit`](#modified-get_consolidation_churn_limit)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Epoch processing](#epoch-processing)
    - [Modified `apply_pending_deposit`](#modified-apply_pending_deposit)
    - [Modified `process_epoch`](#modified-process_epoch)
  - [Block processing](#block-processing)
    - [Modified `process_block`](#modified-process_block)
    - [Operations](#operations)
      - [Modified `process_operations`](#modified-process_operations)
      - [Attestations](#attestations)
        - [Modified `process_attestation`](#modified-process_attestation)
    - [Sync aggregate processing](#sync-aggregate-processing)
      - [Modified `process_sync_aggregate`](#modified-process_sync_aggregate)

<!-- mdformat-toc end -->

## Introduction

Heze is a consensus-layer upgrade containing a number of features. Including:

- [EIP-7805](https://github.com/ethereum/EIPs/blob/9a345f96c2295a678b0ce33e94d41276ddb3fdef/EIPS/eip-7805.md):
  Fork-choice enforced Inclusion Lists (FOCIL)
- [EIP-8015](https://github.com/ethereum/EIPs/blob/0ebff04bf89b696d51ebf2ff9d029940ef3ed693/EIPS/eip-8015.md):
  Remove `deposit` and `eth1data` fields
- [EIP-8198](https://github.com/ethereum/EIPs/blob/afb6a2a0013c8b732c37615eef486c6b7ffd4522/EIPS/eip-8198.md):
  Quick Slots
- [EIP-8365](https://github.com/ethereum/EIPs/blob/718595d75a86eafcf6f005c2b79e23ef941381e5/EIPS/eip-8365.md):
  Disallow new `0x00` validators

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
| `DOMAIN_INCLUSION_LIST_COMMITTEE` | `DomainType("0x10000000")` |

## Presets

### Inclusion list committee

| Name                            | Value                 |
| ------------------------------- | --------------------- |
| `INCLUSION_LIST_COMMITTEE_SIZE` | `Uint64(2**4)` (= 16) |

## Configs

### Time parameters

| Name                    | Value           |
| ----------------------- | --------------- |
| `SLOT_DURATION_MS_HEZE` | `Uint64(10000)` |

The slot duration MUST be a positive multiple of `1000` so that
`ExecutionPayload.timestamp` matches the slot start time in seconds.

### Blob schedule

*[Modified in Heze:EIP8198]*

*Note*: The target and maximum blobs per block limit MUST be coordinated with
the execution layer. Integer rounding may change blob throughput per unit time.

<!-- list-of-records:blob_schedule -->

|  Epoch | Max Blobs Per Block |                             Date |
| -----: | ------------------: | -------------------------------: |
| 412672 |                  15 | December 9, 2025, 02:21:11pm UTC |
| 419072 |                  21 |  January 7, 2026, 01:01:11am UTC |

### Gas limit schedule

*[Modified in Heze:EIP8198]*

*Note*: Gas limit changes should be coordinated through `GAS_LIMIT_SCHEDULE` and
proposer preferences ahead of the fork. Integer rounding may change gas
throughput per unit time.

<!-- list-of-records:gas_limit_schedule -->

| Epoch | Gas Limit | Date |
| ----: | --------: | ---: |

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

### Misc

#### New `get_slot_durations`

*Note*: This function returns slot durations with their activation epochs. A
fork that changes the slot duration MUST add an entry with its activation epoch
and slot duration.

```python
def get_slot_durations() -> Sequence[tuple[Epoch, Uint64]]:
    """
    Return slot durations derived from the configuration.
    """
    return [
        (fork_epoch, slot_duration_ms)
        for fork_epoch, slot_duration_ms in [
            (GENESIS_EPOCH, SLOT_DURATION_MS),
            (HEZE_FORK_EPOCH, SLOT_DURATION_MS_HEZE),
        ]
        if fork_epoch != FAR_FUTURE_EPOCH
    ]
```

#### New `get_slot_duration_ms`

```python
def get_slot_duration_ms(epoch: Epoch) -> Uint64:
    """
    Return the slot duration in effect at ``epoch``.
    """
    for fork_epoch, fork_slot_duration_ms in get_slot_durations():
        if epoch >= fork_epoch:
            slot_duration_ms = fork_slot_duration_ms
    return slot_duration_ms
```

#### Modified `compute_time_at_slot_ms`

```python
def compute_time_at_slot_ms(genesis_time_ms: Uint64, slot: Slot) -> Uint64:
    """
    Return the Unix time in milliseconds at the start of ``slot``.
    """
    # [Modified in Heze:EIP8198]
    end_slot = slot
    time_ms = genesis_time_ms
    for fork_epoch, slot_duration_ms in reversed(get_slot_durations()):
        fork_slot = compute_start_slot_at_epoch(fork_epoch)
        if fork_slot < end_slot:
            slots = end_slot - fork_slot
            time_ms += slots * slot_duration_ms
            end_slot = fork_slot
    return time_ms
```

#### Modified `compute_slot_at_time_ms`

```python
def compute_slot_at_time_ms(genesis_time_ms: Uint64, time_ms: Uint64) -> Slot:
    """
    Return the slot at Unix time ``time_ms``.
    """
    # [Modified in Heze:EIP8198]
    for fork_epoch, fork_slot_duration_ms in get_slot_durations():
        fork_slot = compute_start_slot_at_epoch(fork_epoch)
        fork_time_ms = compute_time_at_slot_ms(genesis_time_ms, fork_slot)
        if time_ms >= fork_time_ms:
            start_slot = fork_slot
            start_time_ms = fork_time_ms
            slot_duration_ms = fork_slot_duration_ms
    time_diff_ms = time_ms - start_time_ms
    slots = time_diff_ms // slot_duration_ms
    return start_slot + slots
```

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
        data=[indices[index % len(indices)] for index in range(INCLUSION_LIST_COMMITTEE_SIZE)]
    )
```

#### Modified `get_base_reward_per_increment`

```python
def get_base_reward_per_increment(
    state: BeaconState,
    # [New in Heze:EIP8198]
    epoch: Epoch,
) -> Gwei:
    """
    Return the base reward per increment, priced at the slot duration in
    effect at ``epoch``.
    """
    # [Modified in Heze:EIP8198]
    return Gwei(
        EFFECTIVE_BALANCE_INCREMENT
        * BASE_REWARD_FACTOR
        * get_slot_duration_ms(epoch)
        // get_slot_duration_ms(GENESIS_EPOCH)
        // integer_squareroot(get_total_active_balance(state))
    )
```

#### Modified `get_base_reward`

```python
def get_base_reward(
    state: BeaconState,
    index: ValidatorIndex,
    # [New in Heze:EIP8198]
    epoch: Epoch,
) -> Gwei:
    """
    Return the base reward for ``index``, priced at the slot duration in
    effect at ``epoch``.
    """
    increments = state.validators[index].effective_balance // EFFECTIVE_BALANCE_INCREMENT
    # [Modified in Heze:EIP8198]
    return increments * get_base_reward_per_increment(state, epoch)
```

#### Modified `get_flag_index_deltas`

*Note*: Participation deltas pay for the previous epoch, so they are priced at
the slot duration in effect at that epoch, which differs from the current one in
the first epoch after a slot duration change.

```python
def get_flag_index_deltas(
    state: BeaconState, flag_index: int
) -> tuple[Sequence[Gwei], Sequence[Gwei]]:
    """
    Return the deltas for a given ``flag_index`` by scanning through the participation flags.
    """
    rewards = [Gwei(0)] * len(state.validators)
    penalties = [Gwei(0)] * len(state.validators)
    previous_epoch = get_previous_epoch(state)
    unslashed_participating_indices = get_unslashed_participating_indices(
        state, flag_index, previous_epoch
    )
    weight = PARTICIPATION_FLAG_WEIGHTS[flag_index]
    unslashed_participating_balance = get_total_balance(state, unslashed_participating_indices)
    unslashed_participating_increments = (
        unslashed_participating_balance // EFFECTIVE_BALANCE_INCREMENT
    )
    active_increments = get_total_active_balance(state) // EFFECTIVE_BALANCE_INCREMENT
    for index in get_eligible_validator_indices(state):
        # [Modified in Heze:EIP8198]
        base_reward = get_base_reward(state, index, previous_epoch)
        if index in unslashed_participating_indices:
            if not is_in_inactivity_leak(state):
                reward_numerator = base_reward * weight * unslashed_participating_increments
                rewards[index] += reward_numerator // (active_increments * WEIGHT_DENOMINATOR)
        elif flag_index != TIMELY_HEAD_FLAG_INDEX:
            penalties[index] += base_reward * weight // WEIGHT_DENOMINATOR
    return rewards, penalties
```

#### Modified `get_inactivity_penalty_deltas`

*Note*: The inactivity penalty scales with the square of the epoch duration, so
the cumulative penalty over a fixed wall-clock leak duration is unchanged. The
penalty pays for the previous epoch and is priced at its slot duration.

```python
def get_inactivity_penalty_deltas(state: BeaconState) -> tuple[Sequence[Gwei], Sequence[Gwei]]:
    """
    Return the inactivity penalty deltas by considering timely target participation flags and inactivity scores.
    """
    rewards = [Gwei(0) for _ in range(len(state.validators))]
    penalties = [Gwei(0) for _ in range(len(state.validators))]
    previous_epoch = get_previous_epoch(state)
    matching_target_indices = get_unslashed_participating_indices(
        state, TIMELY_TARGET_FLAG_INDEX, previous_epoch
    )
    for index in get_eligible_validator_indices(state):
        if index not in matching_target_indices:
            penalty_numerator = (
                state.validators[index].effective_balance * state.inactivity_scores[index]
            )
            # [Modified in Heze:EIP8198]
            penalty_denominator = (
                INACTIVITY_SCORE_BIAS
                * INACTIVITY_PENALTY_QUOTIENT_BELLATRIX
                * get_slot_duration_ms(GENESIS_EPOCH) ** 2
                // get_slot_duration_ms(previous_epoch) ** 2
            )
            penalties[index] += penalty_numerator // penalty_denominator
    return rewards, penalties
```

#### Modified `get_activation_churn_limit`

*Note*: The cap is applied before scaling, so the maximum activation rate is
scaled too, and the increment rounding is applied once, after scaling.

```python
def get_activation_churn_limit(state: BeaconState) -> Gwei:
    """
    Per-epoch churn limit for activations, rounded to
    ``EFFECTIVE_BALANCE_INCREMENT``.
    """
    churn = max(
        MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA,
        get_total_active_balance(state) // CHURN_LIMIT_QUOTIENT_GLOAS,
    )
    # [Modified in Heze:EIP8198]
    churn = min(MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT_GLOAS, churn)
    churn = (
        churn
        * get_slot_duration_ms(get_current_epoch(state))
        // get_slot_duration_ms(GENESIS_EPOCH)
    )
    return churn - churn % EFFECTIVE_BALANCE_INCREMENT
```

#### Modified `get_exit_churn_limit`

*Note*: Exit and consolidation epochs assigned before a duration change keep
their assigned epochs and consumed quota.

```python
def get_exit_churn_limit(state: BeaconState) -> Gwei:
    """
    Per-epoch churn limit for exits, rounded to
    ``EFFECTIVE_BALANCE_INCREMENT``.
    """
    churn = max(
        MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA,
        get_total_active_balance(state) // CHURN_LIMIT_QUOTIENT_GLOAS,
    )
    # [Modified in Heze:EIP8198]
    churn = (
        churn
        * get_slot_duration_ms(get_current_epoch(state))
        // get_slot_duration_ms(GENESIS_EPOCH)
    )
    return churn - churn % EFFECTIVE_BALANCE_INCREMENT
```

#### Modified `get_consolidation_churn_limit`

```python
def get_consolidation_churn_limit(state: BeaconState) -> Gwei:
    """
    Per-epoch churn limit reserved for consolidations (EIP-7521).
    Derived from total active balance and rounded to
    ``EFFECTIVE_BALANCE_INCREMENT``.
    """
    churn = get_total_active_balance(state) // CONSOLIDATION_CHURN_LIMIT_QUOTIENT
    # [Modified in Heze:EIP8198]
    churn = (
        churn
        * get_slot_duration_ms(get_current_epoch(state))
        // get_slot_duration_ms(GENESIS_EPOCH)
    )
    return churn - churn % EFFECTIVE_BALANCE_INCREMENT
```

## Beacon chain state transition function

### Epoch processing

#### Modified `apply_pending_deposit`

*Note*: Deposits that would create new validators with BLS withdrawal
credentials are skipped without a refund, including deposits submitted before
Heze. Top-ups to existing validators are unaffected.

```python
def apply_pending_deposit(state: BeaconState, deposit: PendingDeposit) -> None:
    """
    Applies ``deposit`` to the ``state`` without creating validators with BLS withdrawal credentials.
    """
    validator_pubkeys = [validator.pubkey for validator in state.validators]
    if deposit.pubkey not in validator_pubkeys:
        # [New in Heze:EIP8365]
        # Do not create validators with BLS withdrawal credentials
        if deposit.withdrawal_credentials[:1] == BLS_WITHDRAWAL_PREFIX:
            return
        # Verify the deposit signature (proof of possession) which is not checked by the deposit contract
        if is_valid_deposit_signature(
            deposit.pubkey, deposit.withdrawal_credentials, deposit.amount, deposit.signature
        ):
            add_validator_to_registry(
                state, deposit.pubkey, deposit.withdrawal_credentials, deposit.amount
            )
    else:
        validator_index = ValidatorIndex(validator_pubkeys.index(deposit.pubkey))
        increase_balance(state, validator_index, deposit.amount)
```

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

##### Attestations

###### Modified `process_attestation`

*Note*: The proposer reward for a newly included attestation is priced at the
attestation's target epoch, so around a slot duration change the proposer's
share matches the attesters' rewards for the same epoch.

```python
def process_attestation(
    state: BeaconState,
    attestation: Attestation,
    parent_slot: Slot,
) -> None:
    data = attestation.data
    assert data.target.epoch in (get_previous_epoch(state), get_current_epoch(state))
    assert data.target.epoch == compute_epoch_at_slot(data.slot)
    assert data.slot + MIN_ATTESTATION_INCLUSION_DELAY <= state.slot

    assert data.index < 2
    committee_indices = get_committee_indices(attestation.committee_bits)
    committee_offset = 0
    for committee_index in committee_indices:
        assert committee_index < get_committee_count_per_slot(state, data.target.epoch)
        committee = get_beacon_committee(state, data.slot, committee_index)
        committee_attesters = {
            attester_index
            for index, attester_index in enumerate(committee)
            if attestation.aggregation_bits[committee_offset + index]
        }
        assert len(committee_attesters) > 0
        committee_offset += len(committee)

    # Bitfield length matches total number of participants
    assert len(attestation.aggregation_bits) == committee_offset

    # Participation flag indices
    participation_flag_indices = get_attestation_participation_flag_indices(
        state, data, state.slot - data.slot, parent_slot
    )

    # Verify signature
    assert is_valid_indexed_attestation(state, get_indexed_attestation(state, attestation))

    if data.target.epoch == get_current_epoch(state):
        current_epoch_target = True
        epoch_participation = state.current_epoch_participation
        payment = state.builder_pending_payments[SLOTS_PER_EPOCH + data.slot % SLOTS_PER_EPOCH]
    else:
        current_epoch_target = False
        epoch_participation = state.previous_epoch_participation
        payment = state.builder_pending_payments[data.slot % SLOTS_PER_EPOCH]

    proposer_reward_numerator = 0
    for index in get_attesting_indices(state, attestation):
        had_no_participation = epoch_participation[index] == 0b0000_0000
        will_set_new_flag = False

        for flag_index, weight in enumerate(PARTICIPATION_FLAG_WEIGHTS):
            if flag_index in participation_flag_indices and not has_flag(
                epoch_participation[index], flag_index
            ):
                epoch_participation[index] = add_flag(epoch_participation[index], flag_index)
                # [Modified in Heze:EIP8198]
                proposer_reward_numerator += (
                    get_base_reward(state, index, data.target.epoch) * weight
                )
                will_set_new_flag = True

        if (
            will_set_new_flag
            and had_no_participation
            and is_attestation_same_slot(state, data)
            and payment.withdrawal.amount > 0
        ):
            payment.weight += state.validators[index].effective_balance

    # Reward proposer
    proposer_reward_denominator = (
        (WEIGHT_DENOMINATOR - PROPOSER_WEIGHT) * WEIGHT_DENOMINATOR // PROPOSER_WEIGHT
    )
    proposer_reward = Gwei(proposer_reward_numerator // proposer_reward_denominator)
    increase_balance(state, get_beacon_proposer_index(state), proposer_reward)

    # Update builder payment weight
    if current_epoch_target:
        state.builder_pending_payments[SLOTS_PER_EPOCH + data.slot % SLOTS_PER_EPOCH] = payment
    else:
        state.builder_pending_payments[data.slot % SLOTS_PER_EPOCH] = payment
```

#### Sync aggregate processing

##### Modified `process_sync_aggregate`

```python
def process_sync_aggregate(state: BeaconState, sync_aggregate: SyncAggregate) -> None:
    # Verify sync committee aggregate signature signing over the previous slot block root
    committee_pubkeys = state.current_sync_committee.pubkeys
    committee_bits = sync_aggregate.sync_committee_bits
    if get_set_bit_count(committee_bits) == SYNC_COMMITTEE_SIZE:
        # All members participated - use precomputed aggregate key
        participant_pubkeys = [state.current_sync_committee.aggregate_pubkey]
    elif get_set_bit_count(committee_bits) > SYNC_COMMITTEE_SIZE // 2:
        # More than half participated - subtract non-participant keys.
        # First determine nonparticipating members
        non_participant_pubkeys = [
            pubkey for pubkey, bit in zip(committee_pubkeys, committee_bits, strict=True) if not bit
        ]
        # Compute aggregate of non-participants
        non_participant_aggregate = eth_aggregate_pubkeys(non_participant_pubkeys)
        # Subtract non-participants from the full aggregate
        # This is equivalent to: aggregate_pubkey + (-non_participant_aggregate)
        participant_pubkey = bls.add(
            bls.bytes48_to_G1(state.current_sync_committee.aggregate_pubkey),
            bls.neg(bls.bytes48_to_G1(non_participant_aggregate)),
        )
        participant_pubkeys = [BLSPubkey(bls.G1_to_bytes48(participant_pubkey))]
    else:
        # Less than half participated - aggregate participant keys
        participant_pubkeys = [
            pubkey
            for pubkey, bit in zip(
                committee_pubkeys, sync_aggregate.sync_committee_bits, strict=True
            )
            if bit
        ]
    previous_slot = saturating_sub(state.slot, 1)
    domain = get_domain(state, DOMAIN_SYNC_COMMITTEE, compute_epoch_at_slot(previous_slot))
    signing_root = compute_signing_root(get_block_root_at_slot(state, previous_slot), domain)
    # Note: eth_fast_aggregate_verify works with a singleton list containing an aggregated key
    assert eth_fast_aggregate_verify(
        participant_pubkeys, signing_root, sync_aggregate.sync_committee_signature
    )

    # Compute participant and proposer rewards
    total_active_increments = get_total_active_balance(state) // EFFECTIVE_BALANCE_INCREMENT
    # [Modified in Heze:EIP8198]
    total_base_rewards = (
        get_base_reward_per_increment(state, get_current_epoch(state)) * total_active_increments
    )
    max_participant_rewards = (
        total_base_rewards * SYNC_REWARD_WEIGHT // WEIGHT_DENOMINATOR // Uint64(SLOTS_PER_EPOCH)
    )
    participant_reward = max_participant_rewards // SYNC_COMMITTEE_SIZE
    proposer_reward = participant_reward * PROPOSER_WEIGHT // (WEIGHT_DENOMINATOR - PROPOSER_WEIGHT)

    # Apply participant and proposer rewards
    all_pubkeys = [validator.pubkey for validator in state.validators]
    committee_indices = [
        ValidatorIndex(all_pubkeys.index(pubkey)) for pubkey in state.current_sync_committee.pubkeys
    ]
    for participant_index, participation_bit in zip(
        committee_indices, sync_aggregate.sync_committee_bits, strict=True
    ):
        if participation_bit:
            increase_balance(state, participant_index, participant_reward)
            increase_balance(state, get_beacon_proposer_index(state), proposer_reward)
        else:
            decrease_balance(state, participant_index, participant_reward)
```
