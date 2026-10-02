# EIP-8198 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configs](#configs)
  - [Slot duration schedule](#slot-duration-schedule)
- [Helpers](#helpers)
  - [Misc](#misc)
    - [New `get_slot_duration_ms`](#new-get_slot_duration_ms)
    - [Modified `compute_time_at_slot_ms`](#modified-compute_time_at_slot_ms)
    - [Modified `compute_slot_at_time_ms`](#modified-compute_slot_at_time_ms)
  - [Beacon state accessors](#beacon-state-accessors)
    - [Modified `get_base_reward_per_increment`](#modified-get_base_reward_per_increment)
    - [Modified `get_base_reward`](#modified-get_base_reward)
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
    - [Sync aggregate processing](#sync-aggregate-processing)
      - [Modified `process_sync_aggregate`](#modified-process_sync_aggregate)

<!-- mdformat-toc end -->

## Introduction

EIP-8198 ("Quick Slots") makes the slot duration schedulable, with a first
reduction from 12 to 10 seconds intended at the fork epoch. The duration
schedule records the historical slot lengths. Intra-slot deadlines are
configured separately in basis points of the slot duration at
`EIP8198_FORK_EPOCH`; later forks may change the duties and their deadlines
independently. The remaining duration-dependent parameters are rescaled by the
ratio `r = get_slot_duration_ms(epoch) / get_slot_duration_ms(GENESIS_EPOCH)` to
keep their wall-clock behavior constant: issuance and churn are per-epoch rates
and scale by `r`, while the inactivity penalty scales by `r**2` so that the
cumulative leak over a fixed wall-clock duration is unchanged. Each formula
applies the ratio inline rather than pre-computing rounded constants. Epoch- and
slot-denominated quantities — withdrawability and slashing windows, sync
committee periods, per-payload and per-epoch processing limits — keep their
counts, so their wall-clock spans scale with the slot duration.

*Note*: This specification is built upon [Heze](../../heze/beacon-chain.md).

## Configs

### Slot duration schedule

The standalone `SLOT_DURATION_MS` configuration variable is deprecated in favor
of `SLOT_DURATION_SCHEDULE`.

*[New in EIP8198]* This schedule MUST list slot durations in strictly increasing
epoch order, beginning at `GENESIS_EPOCH` with the historical slot duration. The
genesis duration is the baseline for issuance, penalty, and churn calculations.
Entries contain only an activation epoch and a slot duration; deadline changes
do not require an entry.

The slot duration MUST be a positive multiple of `1000`, so that every slot
boundary has an integer-second timestamp.

The intended first reduction is to 10 seconds on mainnet. Its epoch and
accompanying blob parameters are not yet scheduled. Blob targets and limits must
be chosen jointly with the execution layer; integer rounding does not in general
preserve throughput per unit time exactly.

Gas targets should be coordinated ahead of the upgrade, or as part of the
upgrade's overall capacity increase, using the advisory `GAS_LIMIT_SCHEDULE` and
proposer preferences. The usual gas-limit adjustment rule applies at the
transition, so reaching a lower target requires advance coordination.

<!-- list-of-records:slot_duration_schedule -->

| Epoch | Slot Duration Ms |                             Date |
| ----: | ---------------: | -------------------------------: |
|     0 |            12000 | December 1, 2020, 12:00:23pm UTC |

## Helpers

### Misc

#### New `get_slot_duration_ms`

```python
def get_slot_duration_ms(epoch: Epoch) -> Uint64:
    """
    Return the slot duration in effect at ``epoch``.
    """
    for entry in reversed(SLOT_DURATION_SCHEDULE):
        if epoch >= entry["EPOCH"]:
            break
    return entry["SLOT_DURATION_MS"]
```

#### Modified `compute_time_at_slot_ms`

```python
def compute_time_at_slot_ms(genesis_time_ms: Uint64, slot: Slot) -> Uint64:
    """
    Return the Unix time in milliseconds at the start of ``slot``.
    """
    # [Modified in EIP8198]
    end_slot = slot
    time_ms = genesis_time_ms
    for entry in reversed(SLOT_DURATION_SCHEDULE):
        entry_slot = compute_start_slot_at_epoch(entry["EPOCH"])
        if entry_slot < end_slot:
            slots = end_slot - entry_slot
            time_ms += slots * entry["SLOT_DURATION_MS"]
            end_slot = entry_slot
    return time_ms
```

#### Modified `compute_slot_at_time_ms`

```python
def compute_slot_at_time_ms(genesis_time_ms: Uint64, time_ms: Uint64) -> Slot:
    """
    Return the slot at Unix time ``time_ms``.
    """
    # [Modified in EIP8198]
    for entry in reversed(SLOT_DURATION_SCHEDULE):
        entry_slot = compute_start_slot_at_epoch(entry["EPOCH"])
        entry_time_ms = compute_time_at_slot_ms(genesis_time_ms, entry_slot)
        if time_ms >= entry_time_ms:
            break
    time_diff_ms = time_ms - entry_time_ms
    slots = time_diff_ms // entry["SLOT_DURATION_MS"]
    return entry_slot + slots
```

### Beacon state accessors

#### Modified `get_base_reward_per_increment`

```python
def get_base_reward_per_increment(
    state: BeaconState,
    # [New in EIP8198]
    epoch: Epoch,
) -> Gwei:
    """
    Return the base reward per increment, priced at the slot duration in
    effect at ``epoch``.
    """
    # [Modified in EIP8198]
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
    # [New in EIP8198]
    epoch: Epoch,
) -> Gwei:
    """
    Return the base reward for ``index``, priced at the slot duration in
    effect at ``epoch``.
    """
    increments = state.validators[index].effective_balance // EFFECTIVE_BALANCE_INCREMENT
    # [Modified in EIP8198]
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
        # [Modified in EIP8198]
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
            # [Modified in EIP8198]
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
    # [Modified in EIP8198]
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
    # [Modified in EIP8198]
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
    # [Modified in EIP8198]
    churn = (
        churn
        * get_slot_duration_ms(get_current_epoch(state))
        // get_slot_duration_ms(GENESIS_EPOCH)
    )
    return churn - churn % EFFECTIVE_BALANCE_INCREMENT
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
    # [Modified in EIP8198]
    total_base_rewards = (
        get_base_reward_per_increment(state, get_current_epoch(state)) * total_active_increments
    )
    max_participant_rewards = (
        total_base_rewards * SYNC_REWARD_WEIGHT // WEIGHT_DENOMINATOR // Uint64(SLOTS_PER_EPOCH)
    )
    participant_reward = max_participant_rewards // SYNC_COMMITTEE_SIZE
    proposer_reward = participant_reward * PROPOSER_WEIGHT // (WEIGHT_DENOMINATOR - PROPOSER_WEIGHT)

    # Apply participant and proposer rewards
    all_pubkeys = [v.pubkey for v in state.validators]
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
