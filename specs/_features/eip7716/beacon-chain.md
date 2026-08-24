# EIP-7716 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Preset](#preset)
  - [Penalty factor](#penalty-factor)
- [Containers](#containers)
  - [Modified containers](#modified-containers)
    - [`BeaconState`](#beaconstate)
- [Helper functions](#helper-functions)
  - [Predicates](#predicates)
    - [New `is_offline_in_previous_epoch`](#new-is_offline_in_previous_epoch)
  - [Beacon state accessors](#beacon-state-accessors)
    - [New `get_slot_offline_balance`](#new-get_slot_offline_balance)
    - [New `get_slot_reference_balance`](#new-get_slot_reference_balance)
    - [New `get_updated_smoothed_offline_balance`](#new-get_updated_smoothed_offline_balance)
    - [New `get_slot_penalty_factors`](#new-get_slot_penalty_factors)
    - [New `get_validator_slot_offsets`](#new-get_validator_slot_offsets)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Epoch processing](#epoch-processing)
    - [Modified `process_epoch`](#modified-process_epoch)
    - [Rewards and penalties](#rewards-and-penalties)
      - [Modified `get_flag_index_deltas`](#modified-get_flag_index_deltas)
    - [New `process_smoothed_offline_balance`](#new-process_smoothed_offline_balance)

<!-- mdformat-toc end -->

## Introduction

This feature introduces anti-correlation attestation penalties for validators.
The timely target penalty of a validator that produced no timely attestation at
all — missing both the timely source and timely target flags, the signature of
an infrastructure failure rather than a view disagreement — is scaled by a
per-slot `penalty_factor`. The factor is proportional to the excess of that
slot's offline balance over an exponential moving average of offline balance,
and is `1` whenever the offline balance does not exceed the moving average, so
uncorrelated failures pay exactly the pre-fork penalty. `PENALTY_SLOPE` is set
to `3 * (MAX_PENALTY_FACTOR - 1)` so that the factor saturates at its cap when
one third of stake is newly offline — the point at which the inactivity leak
takes over as the protocol's correlation pricing mechanism.

*Note*: This specification is built upon [Heze](../../heze/beacon-chain.md).

## Preset

### Penalty factor

| Name                               | Value                       | Description                                                                                                                |
| ---------------------------------- | --------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `MAX_PENALTY_FACTOR`               | `uint64(2**8)` (= 256)      | *[New in EIP7716]* Ceiling on the penalty factor; the single severity parameter                                            |
| `PENALTY_SLOPE`                    | `uint64(765)`               | *[New in EIP7716]* Slope of the penalty factor in excess offline stake; equal to `3 * (MAX_PENALTY_FACTOR - 1)`            |
| `OFFLINE_BALANCE_SMOOTHING_FACTOR` | `uint64(2**17)` (= 131,072) | *[New in EIP7716]* Smoothing divisor of the offline balance moving average; half-life of roughly 91,000 slots (~12.6 days) |

## Containers

### Modified containers

#### `BeaconState`

*Note*: The `BeaconState` container is modified to track
`smoothed_offline_balance`, an exponential moving average of the per-slot
offline balance.

```python
class BeaconState(ProgressiveContainer(active_fields=[1] * 47)):
    genesis_time: Uint64
    genesis_validators_root: Root
    slot: Slot
    fork: Fork
    latest_block_header: BeaconBlockHeader
    block_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    state_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    historical_roots: List[Root, HISTORICAL_ROOTS_LIMIT]
    eth1_data: Eth1Data
    eth1_data_votes: List[Eth1Data, EPOCHS_PER_ETH1_VOTING_PERIOD * SLOTS_PER_EPOCH]
    eth1_deposit_index: Uint64
    validators: ProgressiveList[Validator]
    balances: ProgressiveList[Gwei]
    randao_mixes: Vector[Bytes32, EPOCHS_PER_HISTORICAL_VECTOR]
    slashings: Vector[Gwei, EPOCHS_PER_SLASHINGS_VECTOR]
    previous_epoch_participation: ProgressiveList[ParticipationFlags]
    current_epoch_participation: ProgressiveList[ParticipationFlags]
    justification_bits: Bitvector[JUSTIFICATION_BITS_LENGTH]
    previous_justified_checkpoint: Checkpoint
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    inactivity_scores: ProgressiveList[Uint64]
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    latest_block_hash: Hash32
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
    historical_summaries: List[HistoricalSummary, HISTORICAL_ROOTS_LIMIT]
    deposit_requests_start_index: Uint64
    deposit_balance_to_consume: Gwei
    exit_balance_to_consume: Gwei
    earliest_exit_epoch: Epoch
    consolidation_balance_to_consume: Gwei
    earliest_consolidation_epoch: Epoch
    pending_deposits: ProgressiveList[PendingDeposit]
    pending_partial_withdrawals: ProgressiveList[PendingPartialWithdrawal]
    pending_consolidations: ProgressiveList[PendingConsolidation]
    proposer_lookahead: Vector[ValidatorIndex, (MIN_SEED_LOOKAHEAD + 1) * SLOTS_PER_EPOCH]
    builders: ProgressiveList[Builder]
    next_withdrawal_builder_index: BuilderIndex
    execution_payload_availability: Bitvector[SLOTS_PER_HISTORICAL_ROOT]
    builder_pending_payments: Vector[BuilderPendingPayment, 2 * SLOTS_PER_EPOCH]
    builder_pending_withdrawals: ProgressiveList[BuilderPendingWithdrawal]
    latest_execution_payload_bid: ExecutionPayloadBid
    payload_expected_withdrawals: ProgressiveList[Withdrawal]
    ptc_window: Vector[Vector[ValidatorIndex, PTC_SIZE], (2 + MIN_SEED_LOOKAHEAD) * SLOTS_PER_EPOCH]
    # [New in EIP7716]
    smoothed_offline_balance: Gwei
```

## Helper functions

### Predicates

#### New `is_offline_in_previous_epoch`

```python
def is_offline_in_previous_epoch(state: BeaconState, index: ValidatorIndex) -> bool:
    """
    Check if ``index`` produced no timely attestation at all in the previous epoch.
    Validators that attested with a correct and timely source but an incorrect
    target demonstrated liveness and are not considered offline.
    """
    return (
        not state.validators[index].slashed
        and not has_flag(state.previous_epoch_participation[index], TIMELY_SOURCE_FLAG_INDEX)
        and not has_flag(state.previous_epoch_participation[index], TIMELY_TARGET_FLAG_INDEX)
    )
```

### Beacon state accessors

#### New `get_slot_offline_balance`

```python
def get_slot_offline_balance(state: BeaconState, slot: Slot) -> Gwei:
    """
    Return the sum of effective balances of offline validators whose committees
    were assigned to ``slot``. ``slot`` must be within the previous epoch.
    """
    epoch = compute_epoch_at_slot(slot)
    offline_balance = Gwei(0)
    for committee_index in range(get_committee_count_per_slot(state, epoch)):
        committee = get_beacon_committee(state, slot, CommitteeIndex(committee_index))
        for index in committee:
            if is_offline_in_previous_epoch(state, index):
                offline_balance += state.validators[index].effective_balance
    return offline_balance
```

#### New `get_slot_reference_balance`

```python
def get_slot_reference_balance(state: BeaconState) -> Gwei:
    """
    Return the average active balance per slot, the normalizer of the penalty factor.
    """
    return Gwei(get_total_active_balance(state) // SLOTS_PER_EPOCH)
```

#### New `get_updated_smoothed_offline_balance`

```python
def get_updated_smoothed_offline_balance(smoothed_balance: Gwei, offline_balance: Gwei) -> Gwei:
    """
    Return the exponential moving average updated with one slot's offline balance.
    """
    if offline_balance > smoothed_balance:
        return Gwei(
            smoothed_balance
            + (offline_balance - smoothed_balance) // OFFLINE_BALANCE_SMOOTHING_FACTOR
        )
    else:
        return Gwei(
            smoothed_balance
            - (smoothed_balance - offline_balance) // OFFLINE_BALANCE_SMOOTHING_FACTOR
        )
```

#### New `get_slot_penalty_factors`

```python
def get_slot_penalty_factors(state: BeaconState) -> Sequence[Uint64]:
    """
    Return the penalty factor for each slot of the previous epoch.
    Does not mutate ``state``; the moving average is persisted by
    ``process_smoothed_offline_balance``.
    """
    factors = []
    smoothed_balance = state.smoothed_offline_balance
    reference_balance = get_slot_reference_balance(state)
    start_slot = compute_start_slot_at_epoch(get_previous_epoch(state))
    for slot_offset in range(SLOTS_PER_EPOCH):
        slot = Slot(start_slot + slot_offset)
        offline_balance = get_slot_offline_balance(state, slot)
        excess = offline_balance - min(offline_balance, smoothed_balance)
        excess_factor = PENALTY_SLOPE * excess // reference_balance
        penalty_factor = min(Uint64(1) + excess_factor, MAX_PENALTY_FACTOR)
        factors.append(penalty_factor)
        smoothed_balance = get_updated_smoothed_offline_balance(smoothed_balance, offline_balance)
    return factors
```

#### New `get_validator_slot_offsets`

```python
def get_validator_slot_offsets(state: BeaconState) -> Sequence[Uint64]:
    """
    Return the slot offset within the previous epoch of each validator's
    committee assignment.
    """
    slot_offsets = [Uint64(0)] * len(state.validators)
    previous_epoch = get_previous_epoch(state)
    start_slot = compute_start_slot_at_epoch(previous_epoch)
    for slot_offset in range(SLOTS_PER_EPOCH):
        slot = Slot(start_slot + slot_offset)
        for committee_index in range(get_committee_count_per_slot(state, previous_epoch)):
            committee = get_beacon_committee(state, slot, CommitteeIndex(committee_index))
            for index in committee:
                slot_offsets[index] = Uint64(slot_offset)
    return slot_offsets
```

## Beacon chain state transition function

### Epoch processing

#### Modified `process_epoch`

*Note*: The function `process_epoch` is modified to call the new helper
`process_smoothed_offline_balance` after `process_rewards_and_penalties`, so
that the penalty factors applied for the previous epoch are computed against the
moving average as of the start of that epoch.

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_inactivity_updates(state)
    process_rewards_and_penalties(state)
    # [New in EIP7716]
    process_smoothed_offline_balance(state)
    process_registry_updates(state)
    process_slashings(state)
    process_eth1_data_reset(state)
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

#### Rewards and penalties

##### Modified `get_flag_index_deltas`

*Note*: The function `get_flag_index_deltas` is modified to scale the timely
target penalty of offline validators by the penalty factor of the slot their
committee was assigned to. The timely source penalty is unchanged, timely head
misses remain unpenalized, and validators that missed the target but attested
with a timely source pay the unscaled penalty.

```python
def get_flag_index_deltas(
    state: BeaconState, flag_index: int
) -> Tuple[Sequence[Gwei], Sequence[Gwei]]:
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

    # [New in EIP7716]
    if flag_index == TIMELY_TARGET_FLAG_INDEX:
        penalty_factors = get_slot_penalty_factors(state)
        slot_offsets = get_validator_slot_offsets(state)

    for index in get_eligible_validator_indices(state):
        base_reward = get_base_reward(state, index)
        if index in unslashed_participating_indices:
            if not is_in_inactivity_leak(state):
                reward_numerator = base_reward * weight * unslashed_participating_increments
                rewards[index] += Gwei(reward_numerator // (active_increments * WEIGHT_DENOMINATOR))
        # [New in EIP7716]
        elif flag_index == TIMELY_TARGET_FLAG_INDEX:
            penalty_factor = Uint64(1)
            if is_offline_in_previous_epoch(state, index):
                penalty_factor = penalty_factors[slot_offsets[index]]
            penalties[index] += Gwei(penalty_factor * base_reward * weight // WEIGHT_DENOMINATOR)
        elif flag_index != TIMELY_HEAD_FLAG_INDEX:
            penalties[index] += Gwei(base_reward * weight // WEIGHT_DENOMINATOR)
    return rewards, penalties
```

#### New `process_smoothed_offline_balance`

```python
def process_smoothed_offline_balance(state: BeaconState) -> None:
    start_slot = compute_start_slot_at_epoch(get_previous_epoch(state))
    for slot_offset in range(SLOTS_PER_EPOCH):
        slot = Slot(start_slot + slot_offset)
        state.smoothed_offline_balance = get_updated_smoothed_offline_balance(
            state.smoothed_offline_balance, get_slot_offline_balance(state, slot)
        )
```
