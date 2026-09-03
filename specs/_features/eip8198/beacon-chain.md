# EIP-8198 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configuration](#configuration)
  - [Slot duration schedule](#slot-duration-schedule)
- [Helpers](#helpers)
  - [Misc](#misc)
    - [New `SlotTimingParameters`](#new-slottimingparameters)
    - [New `get_slot_timing_parameters`](#new-get_slot_timing_parameters)
    - [New `get_slot_duration_ms`](#new-get_slot_duration_ms)
    - [New `compute_slot_start_time_ms`](#new-compute_slot_start_time_ms)
    - [New `compute_slot_at_time_ms`](#new-compute_slot_at_time_ms)
    - [New `compute_slot_range_duration_ms`](#new-compute_slot_range_duration_ms)
    - [Modified `compute_time_at_slot`](#modified-compute_time_at_slot)
  - [Beacon state accessors](#beacon-state-accessors)
    - [New `get_base_reward_per_increment_at_epoch`](#new-get_base_reward_per_increment_at_epoch)
    - [New `get_base_reward_at_epoch`](#new-get_base_reward_at_epoch)
    - [Modified `get_base_reward_per_increment`](#modified-get_base_reward_per_increment)
    - [Modified `get_flag_index_deltas`](#modified-get_flag_index_deltas)
    - [Modified `get_inactivity_penalty_deltas`](#modified-get_inactivity_penalty_deltas)
    - [Modified `get_activation_churn_limit`](#modified-get_activation_churn_limit)
    - [Modified `get_exit_churn_limit`](#modified-get_exit_churn_limit)
    - [Modified `get_consolidation_churn_limit`](#modified-get_consolidation_churn_limit)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Operations](#operations)
      - [Attestations](#attestations)
        - [Modified `process_attestation`](#modified-process_attestation)

<!-- mdformat-toc end -->

## Introduction

EIP-8198 ("Quick Slots") makes the slot duration schedulable, with a first
reduction from 12 to 10 seconds intended at the fork epoch. The slot structure
is unchanged, and each schedule entry carries the intra-slot deadlines of its
slot duration era as explicit millisecond values, so they can be adjusted
whenever the slot duration changes. The remaining duration-dependent parameters
are rescaled by the ratio `r = get_slot_duration_ms(epoch) / SLOT_DURATION_MS`
to keep their wall-clock behavior constant: issuance and churn are per-epoch
rates and scale by `r`, while the inactivity penalty scales by `r**2` so that
the cumulative leak over a fixed wall-clock duration is unchanged. Each formula
applies the ratio inline rather than pre-computing rounded constants. Epoch- and
slot-denominated quantities — withdrawability and slashing windows, sync
committee periods, per-payload and per-epoch processing limits — keep their
counts, so their wall-clock spans scale with the slot duration.

*Note*: This specification is built upon [Heze](../../heze/beacon-chain.md).

## Configuration

### Slot duration schedule

*[New in EIP8198]* This schedule defines the slot duration and the intra-slot
deadlines for a given epoch. Epochs before the first entry use
`SLOT_DURATION_MS` and the inherited basis-point deadlines.

There MUST NOT exist multiple slot duration schedule entries with the same epoch
value. The epoch value in each entry MUST be greater than or equal to
`EIP8198_FORK_EPOCH`. The slot duration in each entry MUST be a positive
multiple of `1000`, so that every slot boundary has an exact integer-second
timestamp. Every deadline in an entry MUST be positive and less than the entry's
slot duration, and the deadlines MUST preserve the inherited ordering: the
proposer reorg cutoff before the attestation deadline before the aggregate
deadline, the sync message deadline before the contribution deadline, and the
payload deadline before the payload attestation deadline. The slot duration
schedule entries SHOULD be sorted by epoch in ascending order. The slot duration
schedule MAY be empty. Once scheduled, an entry that changes the slot duration
MUST be accompanied by a `BLOB_SCHEDULE` entry at the same epoch that scales the
maximum blobs per block by the slot-duration ratio (rounding down), keeping blob
throughput per unit time constant.

The schedule is empty until the epoch of the first slot duration change is
decided; the intended mainnet entry is a 10-second slot duration at the fork
epoch.

<!-- list-of-records:slot_duration_schedule -->

| Epoch | Slot Duration Ms | Proposer Reorg Cutoff Ms | Attestation Due Ms | Aggregate Due Ms | Sync Message Due Ms | Contribution Due Ms | Payload Due Ms | Payload Attestation Due Ms | Inclusion List Due Ms | Description |
| ----: | ---------------: | -----------------------: | -----------------: | ---------------: | ------------------: | ------------------: | -------------: | -------------------------: | --------------------: | ----------- |

## Helpers

### Misc

#### New `SlotTimingParameters`

```python
@dataclass
class SlotTimingParameters:
    slot_duration_ms: Uint64
    proposer_reorg_cutoff_ms: Uint64
    attestation_due_ms: Uint64
    aggregate_due_ms: Uint64
    sync_message_due_ms: Uint64
    contribution_due_ms: Uint64
    payload_due_ms: Uint64
    payload_attestation_due_ms: Uint64
    inclusion_list_due_ms: Uint64
```

#### New `get_slot_timing_parameters`

```python
def get_slot_timing_parameters(epoch: Epoch) -> SlotTimingParameters:
    """
    Return the slot timing parameters in effect at ``epoch``.
    """
    for entry in sorted(SLOT_DURATION_SCHEDULE, key=lambda entry: entry["EPOCH"], reverse=True):
        if epoch >= entry["EPOCH"]:
            return SlotTimingParameters(
                slot_duration_ms=entry["SLOT_DURATION_MS"],
                proposer_reorg_cutoff_ms=entry["PROPOSER_REORG_CUTOFF_MS"],
                attestation_due_ms=entry["ATTESTATION_DUE_MS"],
                aggregate_due_ms=entry["AGGREGATE_DUE_MS"],
                sync_message_due_ms=entry["SYNC_MESSAGE_DUE_MS"],
                contribution_due_ms=entry["CONTRIBUTION_DUE_MS"],
                payload_due_ms=entry["PAYLOAD_DUE_MS"],
                payload_attestation_due_ms=entry["PAYLOAD_ATTESTATION_DUE_MS"],
                inclusion_list_due_ms=entry["INCLUSION_LIST_DUE_MS"],
            )
    return SlotTimingParameters(
        slot_duration_ms=SLOT_DURATION_MS,
        proposer_reorg_cutoff_ms=get_slot_component_duration_ms(PROPOSER_REORG_CUTOFF_BPS),
        attestation_due_ms=get_slot_component_duration_ms(ATTESTATION_DUE_BPS_GLOAS),
        aggregate_due_ms=get_slot_component_duration_ms(AGGREGATE_DUE_BPS_GLOAS),
        sync_message_due_ms=get_slot_component_duration_ms(SYNC_MESSAGE_DUE_BPS_GLOAS),
        contribution_due_ms=get_slot_component_duration_ms(CONTRIBUTION_DUE_BPS_GLOAS),
        payload_due_ms=get_slot_component_duration_ms(PAYLOAD_DUE_BPS),
        payload_attestation_due_ms=get_slot_component_duration_ms(PAYLOAD_ATTESTATION_DUE_BPS),
        inclusion_list_due_ms=get_slot_component_duration_ms(INCLUSION_LIST_DUE_BPS),
    )
```

#### New `get_slot_duration_ms`

```python
def get_slot_duration_ms(epoch: Epoch) -> Uint64:
    """
    Return the slot duration in effect at ``epoch``.
    """
    return get_slot_timing_parameters(epoch).slot_duration_ms
```

#### New `compute_slot_start_time_ms`

```python
def compute_slot_start_time_ms(genesis_time: Uint64, slot: Slot) -> Uint64:
    """
    Return the Unix time in milliseconds at the start of ``slot``.
    """
    time_ms = genesis_time * 1000
    era_start_slot = GENESIS_SLOT
    era_duration_ms = SLOT_DURATION_MS
    for entry in sorted(SLOT_DURATION_SCHEDULE, key=lambda entry: entry["EPOCH"]):
        entry_slot = compute_start_slot_at_epoch(entry["EPOCH"])
        if slot < entry_slot:
            break
        time_ms += (entry_slot - era_start_slot) * era_duration_ms
        era_start_slot = entry_slot
        era_duration_ms = entry["SLOT_DURATION_MS"]
    return Uint64(time_ms + (slot - era_start_slot) * era_duration_ms)
```

#### New `compute_slot_at_time_ms`

```python
def compute_slot_at_time_ms(genesis_time: Uint64, time_ms: Uint64) -> Slot:
    """
    Return the slot at Unix time ``time_ms``.
    """
    assert time_ms >= genesis_time * 1000
    remaining_ms = time_ms - genesis_time * 1000
    era_start_slot = GENESIS_SLOT
    era_duration_ms = SLOT_DURATION_MS
    for entry in sorted(SLOT_DURATION_SCHEDULE, key=lambda entry: entry["EPOCH"]):
        entry_slot = compute_start_slot_at_epoch(entry["EPOCH"])
        era_length_ms = (entry_slot - era_start_slot) * era_duration_ms
        if remaining_ms < era_length_ms:
            break
        remaining_ms -= era_length_ms
        era_start_slot = entry_slot
        era_duration_ms = entry["SLOT_DURATION_MS"]
    return Slot(era_start_slot + remaining_ms // era_duration_ms)
```

#### New `compute_slot_range_duration_ms`

```python
def compute_slot_range_duration_ms(start_slot: Slot, end_slot: Slot) -> Uint64:
    """
    Return the duration of ``[start_slot, end_slot)`` in milliseconds.
    """
    assert start_slot <= end_slot
    return compute_slot_start_time_ms(Uint64(0), end_slot) - compute_slot_start_time_ms(
        Uint64(0), start_slot
    )
```

#### Modified `compute_time_at_slot`

*Note*: Without this override, the execution payload timestamp validated in
`process_execution_payload` would drift from wall-clock time after a slot
duration change.

```python
def compute_time_at_slot(state: BeaconState, slot: Slot) -> Uint64:
    # [Modified in EIP8198]
    return compute_slot_start_time_ms(state.genesis_time, slot) // 1000
```

### Beacon state accessors

#### New `get_base_reward_per_increment_at_epoch`

*Note*: The division is deferred so that the exact
`get_slot_duration_ms(epoch) / SLOT_DURATION_MS` ratio applies, rather than
rounding `BASE_REWARD_FACTOR` to a new integer constant.

```python
def get_base_reward_per_increment_at_epoch(state: BeaconState, epoch: Epoch) -> Gwei:
    """
    Return the base reward per increment, priced at the slot duration in
    effect at ``epoch``.
    """
    return Gwei(
        EFFECTIVE_BALANCE_INCREMENT
        * BASE_REWARD_FACTOR
        * get_slot_duration_ms(epoch)
        // SLOT_DURATION_MS
        // integer_squareroot(get_total_active_balance(state))
    )
```

#### New `get_base_reward_at_epoch`

```python
def get_base_reward_at_epoch(state: BeaconState, index: ValidatorIndex, epoch: Epoch) -> Gwei:
    """
    Return the base reward for ``index``, priced at the slot duration in
    effect at ``epoch``.
    """
    increments = state.validators[index].effective_balance // EFFECTIVE_BALANCE_INCREMENT
    return increments * get_base_reward_per_increment_at_epoch(state, epoch)
```

#### Modified `get_base_reward_per_increment`

```python
def get_base_reward_per_increment(state: BeaconState) -> Gwei:
    # [Modified in EIP8198]
    return get_base_reward_per_increment_at_epoch(state, get_current_epoch(state))
```

#### Modified `get_flag_index_deltas`

*Note*: Participation deltas pay for the previous epoch, so they are priced at
the slot duration in effect at that epoch, which differs from the current one in
the first epoch after a slot duration change.

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
    for index in get_eligible_validator_indices(state):
        # [Modified in EIP8198]
        base_reward = get_base_reward_at_epoch(state, index, previous_epoch)
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
def get_inactivity_penalty_deltas(state: BeaconState) -> Tuple[Sequence[Gwei], Sequence[Gwei]]:
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
            # [Modified in EIP8198]
            slot_duration_ms = get_slot_duration_ms(get_previous_epoch(state))
            duration_squared = slot_duration_ms * slot_duration_ms
            base_duration_squared = SLOT_DURATION_MS * SLOT_DURATION_MS
            penalty_quotient = INACTIVITY_SCORE_BIAS * INACTIVITY_PENALTY_QUOTIENT_BELLATRIX
            penalty_denominator = penalty_quotient * base_duration_squared // duration_squared
            penalties[index] += Gwei(penalty_numerator // penalty_denominator)
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
    # [Modified in EIP8198]
    churn = min(MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT_GLOAS, churn)
    churn = churn * get_slot_duration_ms(get_current_epoch(state)) // SLOT_DURATION_MS
    return Gwei(churn - churn % EFFECTIVE_BALANCE_INCREMENT)
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
    # [Modified in EIP8198]
    churn = churn * get_slot_duration_ms(get_current_epoch(state)) // SLOT_DURATION_MS
    return Gwei(churn - churn % EFFECTIVE_BALANCE_INCREMENT)
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
    # [Modified in EIP8198]
    churn = churn * get_slot_duration_ms(get_current_epoch(state)) // SLOT_DURATION_MS
    return Gwei(churn - churn % EFFECTIVE_BALANCE_INCREMENT)
```

## Beacon chain state transition function

### Block processing

#### Operations

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
            for i, attester_index in enumerate(committee)
            if attestation.aggregation_bits[committee_offset + i]
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
                # [Modified in EIP8198]
                proposer_reward_numerator += (
                    get_base_reward_at_epoch(state, index, data.target.epoch) * weight
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
