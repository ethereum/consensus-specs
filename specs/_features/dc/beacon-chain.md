# Decoupled Consensus -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
  - [Modified `AggregationBits`](#modified-aggregationbits)
  - [New `HeadVoteSupportBits`](#new-headvotesupportbits)
  - [New `HeadVotes`](#new-headvotes)
  - [New `Height`](#new-height)
  - [New `Participation`](#new-participation)
  - [New `PendingFinalities`](#new-pendingfinalities)
- [Constants](#constants)
  - [Participation flag indices](#participation-flag-indices)
  - [Incentivization weights](#incentivization-weights)
  - [Domains](#domains)
  - [Misc](#misc)
- [Presets](#presets)
  - [Finality gadget](#finality-gadget)
  - [Inactivity leak](#inactivity-leak)
  - [Max operations per block](#max-operations-per-block)
- [Containers](#containers)
  - [New `HeightCheckpoint`](#new-heightcheckpoint)
  - [New `PendingFinality`](#new-pendingfinality)
  - [New `HeadVoteData`](#new-headvotedata)
  - [New `HeadVote`](#new-headvote)
  - [New `HeadVoteMessage`](#new-headvotemessage)
  - [Modified `AttestationData`](#modified-attestationdata)
  - [Modified `SingleAttestation`](#modified-singleattestation)
  - [Modified `Attestation`](#modified-attestation)
  - [Modified `BeaconBlockBody`](#modified-beaconblockbody)
  - [Modified `BeaconState`](#modified-beaconstate)
- [Helpers](#helpers)
  - [Predicates](#predicates)
    - [New `is_well_formed_attestation_data`](#new-is_well_formed_attestation_data)
    - [New `is_valid_attestation_data`](#new-is_valid_attestation_data)
    - [Modified `is_valid_indexed_attestation`](#modified-is_valid_indexed_attestation)
    - [Modified `is_eligible_for_activation`](#modified-is_eligible_for_activation)
    - [Modified `is_active_builder`](#modified-is_active_builder)
    - [New `has_quorum`](#new-has_quorum)
  - [Beacon state accessors](#beacon-state-accessors)
    - [Modified `get_attesting_indices`](#modified-get_attesting_indices)
    - [New `get_validator_weight`](#new-get_validator_weight)
    - [New `get_total_weight`](#new-get_total_weight)
    - [New `get_participating_weight`](#new-get_participating_weight)
    - [Modified `get_finality_delay`](#modified-get_finality_delay)
    - [Modified `get_attestation_participation_flag_indices`](#modified-get_attestation_participation_flag_indices)
    - [New `get_flag_index_rewards`](#new-get_flag_index_rewards)
  - [Validator registry](#validator-registry)
    - [Modified `add_validator_to_registry`](#modified-add_validator_to_registry)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Modified `process_slot`](#modified-process_slot)
  - [Epoch processing](#epoch-processing)
    - [Modified `process_epoch`](#modified-process_epoch)
    - [Modified `process_inactivity_updates`](#modified-process_inactivity_updates)
    - [New `process_rewards`](#new-process_rewards)
    - [Modified `process_pending_deposits`](#modified-process_pending_deposits)
    - [Modified `process_participation_flag_updates`](#modified-process_participation_flag_updates)
  - [Block processing](#block-processing)
    - [Operations](#operations)
      - [Modified `process_operations`](#modified-process_operations)
      - [Attestations](#attestations)
        - [Modified `process_attestation`](#modified-process_attestation)
      - [Head votes](#head-votes)
        - [New `process_head_vote`](#new-process_head_vote)
    - [Height events](#height-events)
      - [New `process_height_events`](#new-process_height_events)
      - [New `advance_height`](#new-advance_height)

<!-- mdformat-toc end -->

## Introduction

Decoupled consensus (DC) composes two parts: a finality gadget (FG) and an
available chain (AC). The FG decides which blocks are accepted and finalizes
them; the AC follows the head and confirms blocks quickly, reading the FG only
through a narrow interface. This upgrade replaces Casper FFG with the FG, whose
chain state lives in the beacon state, and adds the payload of the AC, head
votes, to the beacon block.

The FG advances through heights. The block that brings the chain into a height
is the target of that height. An attestation carries a height pair, which is a
target vote or a timeout for a height and its target, and an optional finality
pair, which names a justification that the chain has not yet finalized. A block
justifies the target of the current height when the target votes for it reach a
quorum, and the chain then moves to the next height. A quorum of target votes
and timeouts together also moves the chain to the next height, but only
`TIMEOUT_DELAY_SLOTS` slots after the target. A pending justification whose
finality pairs reach a quorum is finalized.

The AC keeps its own state outside of the beacon state. A block carries the head
votes of the previous slot and records which of them the proposer counted as
support. The state transition checks these votes but does not store them.

Validators are rewarded per epoch, as in Altair, with two participation flags.
The progress flag is earned by a target vote or a timeout counted at the current
height, and the finality flag by a finality pair counted for a pending
justification. A validator without a flag forfeits that reward; there are no
penalties.

Inactivity costs weight instead of balance. Each epoch without the progress flag
adds to a validator's inactivity score, each epoch with it removes more, and the
validator's weight in FG quorums falls with the square of its score. A short
absence costs almost nothing, a long one costs a lot, and a validator whose
weight reaches zero is exited and keeps its stake. When finality is delayed,
this is what lets the participating validators regain a quorum, and no rewards
are paid until it does.

*Note*: A quorum is two thirds of the total weight of the active validators. A
validator's weight is its effective balance, reduced by its inactivity score.
Slashed validators count toward the total but not toward a quorum, as in Casper
FFG.

*Note*: This upgrade does not yet specify rewards for head votes, slashing
conditions for FG attestations, or how attestations weigh builder payments. A
block therefore carries no attester slashings.

*Note*: This specification is built upon [Heze](../../heze/beacon-chain.md).

## Types

### Modified `AggregationBits`

```python
class AggregationBits(ProgressiveBitList):
    """
    The participation bits of an aggregate, one bit per validator in the
    registry, in validator index order.
    """
```

### New `HeadVoteSupportBits`

```python
class HeadVoteSupportBits(ProgressiveBitList):
    """
    One bit per head vote in a beacon block, set when the proposer counted
    that vote as support.
    """
```

### New `HeadVotes`

```python
class HeadVotes(ProgressiveList[HeadVote]):
    """
    The head votes included in a beacon block.
    """
```

### New `Height`

```python
class Height(Uint64):
    """
    A height of the finality gadget. The chain moves to the next height when it
    justifies the target of the current height, or after a delay when target
    votes and timeouts together reach a quorum.
    """
```

### New `Participation`

```python
class Participation(ProgressiveList[Boolean]):
    """
    Whether each validator in the registry participates, in validator index
    order.
    """
```

### New `PendingFinalities`

```python
class PendingFinalities(List[PendingFinality]):
    """
    The justifications on the chain that are not yet finalized, in increasing
    order of height.
    """

    LIMIT = PENDING_FINALITY_WINDOW
```

## Constants

### Participation flag indices

| Name                  | Value       |
| --------------------- | ----------- |
| `PROGRESS_FLAG_INDEX` | `Uint64(0)` |
| `FINALITY_FLAG_INDEX` | `Uint64(1)` |

### Incentivization weights

| Name              | Value        |
| ----------------- | ------------ |
| `PROGRESS_WEIGHT` | `Uint64(40)` |
| `FINALITY_WEIGHT` | `Uint64(14)` |

*Note*: The progress flag takes the Altair weights of the source and target
flags, and the finality flag takes the weight of the head flag, so the sum of
the weights still equals `WEIGHT_DENOMINATOR`.

### Domains

| Name               | Value                      |
| ------------------ | -------------------------- |
| `DOMAIN_HEAD_VOTE` | `DomainType("0x12000000")` |

### Misc

| Name                            | Value                                |
| ------------------------------- | ------------------------------------ |
| `PARTICIPATION_FLAG_WEIGHTS_DC` | `[PROGRESS_WEIGHT, FINALITY_WEIGHT]` |

## Presets

### Finality gadget

| Name                      | Value                |
| ------------------------- | -------------------- |
| `PENDING_FINALITY_WINDOW` | `Uint64(2**2)` (= 4) |
| `TIMEOUT_DELAY_SLOTS`     | `Slot(2**1)` (= 2)   |

*Note*: `PENDING_FINALITY_WINDOW` must be at least 2.

### Inactivity leak

| Name                        | Value                      |
| --------------------------- | -------------------------- |
| `EJECTION_INACTIVITY_SCORE` | `Uint64(2**14)` (= 16,384) |

### Max operations per block

| Name             | Value                |
| ---------------- | -------------------- |
| `MAX_HEAD_VOTES` | `Uint64(2**3)` (= 8) |

## Containers

### New `HeightCheckpoint`

*Note*: The empty checkpoint, `HeightCheckpoint.empty()`, stands for an absent
finality pair.

```python
class HeightCheckpoint(Container):
    height: Height
    root: Root
```

### New `PendingFinality`

```python
class PendingFinality(Container):
    checkpoint: HeightCheckpoint
    slot: Slot
    participation: Participation
```

### New `HeadVoteData`

```python
class HeadVoteData(Container):
    slot: Slot
    beacon_block_root: Root
```

### New `HeadVote`

```python
class HeadVote(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=3)

    aggregation_bits: AggregationBits
    data: HeadVoteData
    signature: BLSSignature
```

### New `HeadVoteMessage`

```python
class HeadVoteMessage(Container):
    validator_index: ValidatorIndex
    data: HeadVoteData
    signature: BLSSignature
```

### Modified `AttestationData`

*Note*: The height pair is (`target`, `timeout`): a target vote when `timeout`
is false, and a timeout when it is true. The finality pair is `finality`.

```python
class AttestationData(Container):
    # [Modified in DC]
    # Removed `slot`
    # [Modified in DC]
    # Removed `index`
    # [Modified in DC]
    # Removed `beacon_block_root`
    # [Modified in DC]
    # Removed `source`
    # [Modified in DC]
    target: HeightCheckpoint
    # [New in DC]
    timeout: Boolean
    # [New in DC]
    finality: HeightCheckpoint
```

### Modified `SingleAttestation`

```python
class SingleAttestation(Container):
    # [Modified in DC]
    # Removed `committee_index`
    attester_index: ValidatorIndex
    data: AttestationData
    signature: BLSSignature
```

### Modified `Attestation`

*Note*: A field layout cannot end on a gap, so the position of the removed
`committee_bits` is dropped from the layout. A field added later must skip that
position.

```python
class Attestation(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=3)

    aggregation_bits: AggregationBits
    data: AttestationData
    signature: BLSSignature
    # [Modified in DC]
    # Removed `committee_bits`
```

### Modified `BeaconBlockBody`

*Note*: Support is recorded per aggregate rather than per vote. The validators
in an aggregate share its head, so their votes resolve together.

```python
class BeaconBlockBody(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=15)

    randao_reveal: BLSSignature
    eth1_data: Eth1Data
    graffiti: Bytes32
    proposer_slashings: ProposerSlashings
    attester_slashings: AttesterSlashings
    attestations: Attestations
    deposits: Deposits
    voluntary_exits: VoluntaryExits
    sync_aggregate: SyncAggregate
    bls_to_execution_changes: BLSToExecutionChanges
    signed_execution_payload_bid: SignedExecutionPayloadBid
    payload_attestations: PayloadAttestations
    parent_execution_requests: ExecutionRequests
    # [New in DC]
    head_votes: HeadVotes
    # [New in DC]
    head_vote_support_bits: HeadVoteSupportBits
```

### Modified `BeaconState`

*Note*: The positions of the Casper FFG fields are left as gaps, so their
generalized indices are never reused. `finalized_checkpoint` keeps its name but
moves to a new position.

```python
class BeaconState(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=54, gaps=(17, 18, 19, 20))

    genesis_time: Uint64
    genesis_validators_root: Root
    slot: Slot
    fork: Fork
    latest_block_header: BeaconBlockHeader
    block_roots: BlockRoots
    state_roots: StateRoots
    historical_roots: HistoricalRoots
    eth1_data: Eth1Data
    eth1_data_votes: Eth1DataVotes
    eth1_deposit_index: Uint64
    validators: Validators
    balances: Balances
    randao_mixes: RandaoMixes
    slashings: Slashings
    previous_epoch_participation: EpochParticipation
    current_epoch_participation: EpochParticipation
    # [Modified in DC]
    # Removed `justification_bits`
    # [Modified in DC]
    # Removed `previous_justified_checkpoint`
    # [Modified in DC]
    # Removed `current_justified_checkpoint`
    # [Modified in DC]
    # Removed `finalized_checkpoint`
    inactivity_scores: InactivityScores
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    latest_block_hash: Hash32
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
    historical_summaries: HistoricalSummaries
    deposit_requests_start_index: Uint64
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
    latest_execution_payload_bid: ExecutionPayloadBid
    payload_expected_withdrawals: Withdrawals
    ptc_window: PayloadTimelinessCommitteeWindow
    # [New in DC]
    target_checkpoint: HeightCheckpoint
    # [New in DC]
    justified_checkpoint: HeightCheckpoint
    # [New in DC]
    finalized_checkpoint: HeightCheckpoint
    # [New in DC]
    target_slot: Slot
    # [New in DC]
    finalized_slot: Slot
    # [New in DC]
    target_participation: Participation
    # [New in DC]
    progress_participation: Participation
    # [New in DC]
    pending_finality: PendingFinalities
```

## Helpers

### Predicates

#### New `is_well_formed_attestation_data`

```python
def is_well_formed_attestation_data(data: AttestationData) -> bool:
    """
    Check if the height pair and the finality pair of ``data`` have valid
    forms.
    """
    if data.target.height == 0 or data.target.root == Root():
        return False
    if data.finality == HeightCheckpoint.empty():
        return True
    return data.finality.root != Root() and data.finality.height < data.target.height
```

#### New `is_valid_attestation_data`

```python
def is_valid_attestation_data(state: BeaconState, data: AttestationData) -> bool:
    """
    Check if ``data`` names the target checkpoint of ``state``, or is a vote
    below the current height whose finality pair is pending.
    """
    if data.target == state.target_checkpoint:
        return True
    pending_checkpoints = [pending.checkpoint for pending in state.pending_finality]
    return (
        data.finality in pending_checkpoints
        and data.finality.height < data.target.height < state.target_checkpoint.height
    )
```

#### Modified `is_valid_indexed_attestation`

*Note*: An aggregate can include every validator in the registry, so the number
of attesting indices is no longer bounded by the committee sizes. The
attestation data has no epoch, so the signature domain uses the current epoch.

```python
def is_valid_indexed_attestation(
    state: BeaconState, indexed_attestation: IndexedAttestation
) -> bool:
    """
    Check if ``indexed_attestation`` is not empty, has sorted and unique indices and has a valid aggregate signature.
    """
    # Verify indices are sorted and unique
    indices = indexed_attestation.attesting_indices
    # [Modified in DC]
    if len(indices) == 0 or list(indices) != sorted(set(indices)):
        return False
    # Verify aggregate signature
    pubkeys = [state.validators[i].pubkey for i in indices]
    # [Modified in DC]
    domain = get_domain(state, DOMAIN_BEACON_ATTESTER)
    signing_root = compute_signing_root(indexed_attestation.data, domain)
    return bls.FastAggregateVerify(pubkeys, signing_root, indexed_attestation.signature)
```

#### Modified `is_eligible_for_activation`

```python
def is_eligible_for_activation(state: BeaconState, validator: Validator) -> bool:
    """
    Check if ``validator`` is eligible for activation.
    """
    return (
        # Placement in queue is finalized
        # [Modified in DC]
        validator.activation_eligibility_epoch <= compute_epoch_at_slot(state.finalized_slot)
        # Has not yet been activated
        and validator.activation_epoch == FAR_FUTURE_EPOCH
    )
```

#### Modified `is_active_builder`

```python
def is_active_builder(state: BeaconState, builder_index: BuilderIndex) -> bool:
    """
    Check if the builder at ``builder_index`` is active for the given ``state``.
    """
    builder = state.builders[builder_index]
    return (
        # Placement in builder list is finalized
        # [Modified in DC]
        builder.deposit_epoch < compute_epoch_at_slot(state.finalized_slot)
        # Has not initiated exit
        and builder.withdrawable_epoch == FAR_FUTURE_EPOCH
    )
```

#### New `has_quorum`

```python
def has_quorum(state: BeaconState, participation: Participation) -> bool:
    """
    Check if the validators marked in ``participation`` hold at least two
    thirds of the total weight of the active validators.
    """
    active_indices = set(get_active_validator_indices(state, get_current_epoch(state)))
    participating_weight = get_participating_weight(state, participation)
    return participating_weight * 3 >= get_total_weight(state, active_indices) * 2
```

### Beacon state accessors

#### Modified `get_attesting_indices`

```python
def get_attesting_indices(
    state: BeaconState,  # noqa: ARG001
    attestation: Attestation,
) -> set[ValidatorIndex]:
    """
    Return the set of attesting indices corresponding to ``aggregation_bits``.
    """
    attesting_indices: set[ValidatorIndex] = set()
    for index, bit in enumerate(attestation.aggregation_bits):
        if bit:
            attesting_indices.add(ValidatorIndex(index))
    return attesting_indices
```

#### New `get_validator_weight`

*Note*: The weight is the effective balance times
`1 - (score / EJECTION_INACTIVITY_SCORE)**2`, computed as two integer factors to
avoid overflow.

```python
def get_validator_weight(state: BeaconState, index: ValidatorIndex) -> Gwei:
    """
    Return the weight of the validator at ``index`` in finality gadget quorums.
    """
    effective_balance = state.validators[index].effective_balance
    inactivity_score = min(state.inactivity_scores[index], EJECTION_INACTIVITY_SCORE)
    weight = effective_balance * (EJECTION_INACTIVITY_SCORE - inactivity_score)
    weight = weight // EJECTION_INACTIVITY_SCORE * (EJECTION_INACTIVITY_SCORE + inactivity_score)
    return Gwei(weight // EJECTION_INACTIVITY_SCORE)
```

#### New `get_total_weight`

```python
def get_total_weight(state: BeaconState, indices: set[ValidatorIndex]) -> Gwei:
    """
    Return the combined weight of the ``indices``.
    ``EFFECTIVE_BALANCE_INCREMENT`` Gwei minimum, so that no validators never
    form a quorum.
    """
    total_weight = Gwei(0)
    for index in indices:
        total_weight += get_validator_weight(state, index)
    return max(EFFECTIVE_BALANCE_INCREMENT, total_weight)
```

#### New `get_participating_weight`

```python
def get_participating_weight(state: BeaconState, participation: Participation) -> Gwei:
    """
    Return the combined weight of the active and unslashed validators marked in
    ``participation``.
    """
    epoch = get_current_epoch(state)
    participating_indices: set[ValidatorIndex] = set()
    for index in get_active_validator_indices(state, epoch):
        if participation[index] and not state.validators[index].slashed:
            participating_indices.add(index)
    return get_total_weight(state, participating_indices)
```

#### Modified `get_finality_delay`

*Note*: The finality gadget can finalize a block of the current epoch, so the
delay stops at zero rather than going negative.

```python
def get_finality_delay(state: BeaconState) -> Epoch:
    previous_epoch = get_previous_epoch(state)
    # [Modified in DC]
    finalized_epoch = compute_epoch_at_slot(state.finalized_slot)
    if finalized_epoch > previous_epoch:
        return Epoch(0)
    return previous_epoch - finalized_epoch
```

#### Modified `get_attestation_participation_flag_indices`

*Note*: The function `get_attestation_participation_flag_indices` is rewritten
for the finality gadget. It has no inclusion-delay check, since an attestation
counts only while its height is current or its finality pair is pending.

```python
def get_attestation_participation_flag_indices(
    state: BeaconState, data: AttestationData
) -> Sequence[int]:
    """
    Return the flag indices that are satisfied by an attestation.
    """
    participation_flag_indices = []
    if data.target == state.target_checkpoint:
        participation_flag_indices.append(PROGRESS_FLAG_INDEX)
    for pending in state.pending_finality:
        if pending.checkpoint == data.finality:
            participation_flag_indices.append(FINALITY_FLAG_INDEX)
    return participation_flag_indices
```

#### New `get_flag_index_rewards`

*Note*: This replaces `get_flag_index_deltas`. A validator without the flag
forfeits the reward and is not penalized, and no rewards are paid during an
inactivity leak.

```python
def get_flag_index_rewards(state: BeaconState, flag_index: int) -> Sequence[Gwei]:
    """
    Return the rewards for a given ``flag_index`` by scanning through the
    participation flags.
    """
    rewards = [Gwei(0)] * len(state.validators)
    if is_in_inactivity_leak(state):
        return rewards

    previous_epoch = get_previous_epoch(state)
    unslashed_participating_indices = get_unslashed_participating_indices(
        state, flag_index, previous_epoch
    )
    weight = PARTICIPATION_FLAG_WEIGHTS_DC[flag_index]
    unslashed_participating_balance = get_total_balance(state, unslashed_participating_indices)
    unslashed_participating_increments = (
        unslashed_participating_balance // EFFECTIVE_BALANCE_INCREMENT
    )
    active_increments = get_total_active_balance(state) // EFFECTIVE_BALANCE_INCREMENT
    for index in unslashed_participating_indices:
        base_reward = get_base_reward(state, index)
        reward_numerator = base_reward * weight * unslashed_participating_increments
        rewards[index] += reward_numerator // (active_increments * WEIGHT_DENOMINATOR)
    return rewards
```

### Validator registry

#### Modified `add_validator_to_registry`

```python
def add_validator_to_registry(
    state: BeaconState, pubkey: BLSPubkey, withdrawal_credentials: Bytes32, amount: Gwei
) -> None:
    index = get_index_for_new_validator(state)
    validator = get_validator_from_deposit(pubkey, withdrawal_credentials, amount)
    set_or_append_list(state.validators, index, validator)
    set_or_append_list(state.balances, index, amount)
    set_or_append_list(state.previous_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.current_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.inactivity_scores, index, Uint64(0))
    # [New in DC]
    set_or_append_list(state.target_participation, index, Boolean(False))
    # [New in DC]
    set_or_append_list(state.progress_participation, index, Boolean(False))
    # [New in DC]
    for pending in state.pending_finality:
        set_or_append_list(pending.participation, index, Boolean(False))
```

## Beacon chain state transition function

### Modified `process_slot`

*Note*: The block that moves the chain to a new height is the target of that
height, and a post-state cannot contain the root of its own block. So
`advance_height` leaves the root of `target_checkpoint` empty, and the next
`process_slot` fills it in, as it does for the state root of
`latest_block_header`.

```python
def process_slot(state: BeaconState) -> None:
    slot_index = state.slot % SLOTS_PER_HISTORICAL_ROOT
    # Cache state root
    previous_state_root = hash_tree_root(state)
    state.state_roots[slot_index] = previous_state_root
    # Cache latest block header state root
    if state.latest_block_header.state_root == Bytes32():
        state.latest_block_header.state_root = previous_state_root
    # Cache block root
    previous_block_root = hash_tree_root(state.latest_block_header)
    state.block_roots[slot_index] = previous_block_root
    # [New in DC]
    # Cache target checkpoint root
    if state.target_checkpoint.root == Root():
        state.target_checkpoint.root = previous_block_root
    # Unset the next payload availability
    next_slot_index = (state.slot + 1) % SLOTS_PER_HISTORICAL_ROOT
    state.execution_payload_availability[next_slot_index] = Boolean(False)
```

### Epoch processing

#### Modified `process_epoch`

```python
def process_epoch(state: BeaconState) -> None:
    # [Modified in DC]
    # Removed `process_justification_and_finalization`
    process_inactivity_updates(state)
    # [New in DC]
    process_rewards(state)
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

#### Modified `process_inactivity_updates`

*Note*: The function `process_inactivity_updates` is rewritten to use a virtual
penalty system. Inactivity scores are updated in every epoch, not only during an
inactivity leak.

```python
def process_inactivity_updates(state: BeaconState) -> None:
    if get_current_epoch(state) == GENESIS_EPOCH:
        return

    participating_indices = get_unslashed_participating_indices(
        state, PROGRESS_FLAG_INDEX, get_previous_epoch(state)
    )
    for index in get_eligible_validator_indices(state):
        if index in participating_indices:
            state.inactivity_scores[index] = saturating_sub(
                state.inactivity_scores[index], INACTIVITY_SCORE_RECOVERY_RATE
            )
        else:
            state.inactivity_scores[index] += INACTIVITY_SCORE_BIAS
            if state.inactivity_scores[index] >= EJECTION_INACTIVITY_SCORE:
                initiate_validator_exit(state, index)
```

*Note*: A validator gains `INACTIVITY_SCORE_BIAS` points for each epoch it is
offline, and its weight falls with the square of its score. The table below
shows the weight of a validator that was fully active and then stays offline.
These percentages are the same for every validator, regardless of its balance.
Inactivity does not reduce a validator's balance. When the weight reaches zero,
the validator is force-exited and keeps its stake.

| Epochs offline | Inactivity score | Voting weight |
| -------------: | ---------------: | ------------: |
|              0 |                0 |       100.00% |
|            256 |            1,024 |        99.61% |
|            512 |            2,048 |        98.44% |
|            768 |            3,072 |        96.48% |
|          1,024 |            4,096 |        93.75% |
|          1,280 |            5,120 |        90.23% |
|          1,536 |            6,144 |        85.94% |
|          1,792 |            7,168 |        80.86% |
|          2,048 |            8,192 |        75.00% |
|          2,304 |            9,216 |        68.36% |
|          2,560 |           10,240 |        60.94% |
|          2,816 |           11,264 |        52.73% |
|          3,072 |           12,288 |        43.75% |
|          3,328 |           13,312 |        33.98% |
|          3,584 |           14,336 |        23.44% |
|          3,840 |           15,360 |        12.11% |
|          4,096 |           16,384 |         0.00% |

#### New `process_rewards`

*Note*: This replaces `process_rewards_and_penalties`, since inactivity is no
longer penalized.

```python
def process_rewards(state: BeaconState) -> None:
    if get_current_epoch(state) == GENESIS_EPOCH:
        return

    for flag_index in range(len(PARTICIPATION_FLAG_WEIGHTS_DC)):
        rewards = get_flag_index_rewards(state, flag_index)
        for index in range(len(state.validators)):
            increase_balance(state, ValidatorIndex(index), rewards[index])
```

#### Modified `process_pending_deposits`

```python
def process_pending_deposits(state: BeaconState) -> None:
    next_epoch = get_current_epoch(state) + 1
    # Deposits still consume the activation-only churn budget in Gloas.
    available_for_processing = state.deposit_balance_to_consume + get_activation_churn_limit(state)
    processed_amount = 0
    next_deposit_index = 0
    deposits_to_postpone = []
    is_churn_limit_reached = False
    # [Modified in DC]
    finalized_slot = state.finalized_slot

    for deposit in state.pending_deposits:
        # Check if deposit has been finalized, otherwise, stop processing.
        if deposit.slot > finalized_slot:
            break

        # Check if number of processed deposits has not reached the limit, otherwise, stop processing.
        if next_deposit_index >= MAX_PENDING_DEPOSITS_PER_EPOCH:
            break

        # Read validator state
        is_validator_exited = False
        is_validator_withdrawn = False
        validator_pubkeys = [v.pubkey for v in state.validators]
        if deposit.pubkey in validator_pubkeys:
            validator = state.validators[ValidatorIndex(validator_pubkeys.index(deposit.pubkey))]
            is_validator_exited = validator.exit_epoch < FAR_FUTURE_EPOCH
            is_validator_withdrawn = validator.withdrawable_epoch < next_epoch

        if is_validator_withdrawn:
            # Deposited balance will never become active. Increase balance but do not consume churn
            apply_pending_deposit(state, deposit)
        elif is_validator_exited:
            # Validator is exiting, postpone the deposit until after withdrawable epoch
            deposits_to_postpone.append(deposit)
        else:
            # Check if deposit fits in the churn, otherwise, do no more deposit processing in this epoch.
            is_churn_limit_reached = processed_amount + deposit.amount > available_for_processing
            if is_churn_limit_reached:
                break

            # Consume churn and apply deposit.
            processed_amount += deposit.amount
            apply_pending_deposit(state, deposit)

        # Regardless of how the deposit was handled, we move on in the queue.
        next_deposit_index += 1

    state.pending_deposits = state.pending_deposits[next_deposit_index:] + deposits_to_postpone

    # Accumulate churn only if the churn limit has been hit.
    if is_churn_limit_reached:
        state.deposit_balance_to_consume = available_for_processing - processed_amount
    else:
        state.deposit_balance_to_consume = Gwei(0)
```

#### Modified `process_participation_flag_updates`

*Note*: A validator sends at most one target vote per height and names each
entry at most once, so it cannot vote again while a height lasts across epochs.
Progress already made at the current height therefore carries into the new
epoch.

```python
def process_participation_flag_updates(state: BeaconState) -> None:
    state.previous_epoch_participation = state.current_epoch_participation
    state.current_epoch_participation = EpochParticipation(
        data=[ParticipationFlags(0b0000_0000) for _ in range(len(state.validators))]
    )
    # [New in DC]
    for index in range(len(state.validators)):
        if state.progress_participation[index]:
            state.current_epoch_participation[index] = add_flag(
                state.current_epoch_participation[index], PROGRESS_FLAG_INDEX
            )
```

### Block processing

*Note*: The height events of a block are processed once, after all of its
attestations.

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_parent_execution_payload(state, block)
    process_block_header(state, block)
    process_withdrawals(state)
    process_execution_payload_bid(state, block.body.signed_execution_payload_bid)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    # [Modified in DC]
    process_operations(state, block.body)
    process_sync_aggregate(state, block.body.sync_aggregate)
    # [New in DC]
    process_height_events(state)
```

#### Operations

##### Modified `process_operations`

```python
def process_operations(
    state: BeaconState,
    body: BeaconBlockBody,
    # [Modified in DC]
    # Removed `parent_slot`
) -> None:
    assert len(body.deposits) == 0
    # [New in DC]
    assert len(body.attester_slashings) == 0

    def for_ops(operations: Sequence[Any], fn: Callable[..., None], *args: Any) -> None:
        for operation in operations:
            fn(state, operation, *args)

    assert len(body.proposer_slashings) <= MAX_PROPOSER_SLASHINGS
    assert len(body.attestations) <= MAX_ATTESTATIONS_ELECTRA
    assert len(body.voluntary_exits) <= MAX_VOLUNTARY_EXITS
    assert len(body.bls_to_execution_changes) <= MAX_BLS_TO_EXECUTION_CHANGES
    assert len(body.payload_attestations) <= MAX_PAYLOAD_ATTESTATIONS
    # [New in DC]
    assert len(body.head_votes) <= MAX_HEAD_VOTES
    # [New in DC]
    assert len(body.head_vote_support_bits) == len(body.head_votes)

    for_ops(body.proposer_slashings, process_proposer_slashing)
    # [Modified in DC]
    for_ops(body.attestations, process_attestation)
    for_ops(body.voluntary_exits, process_voluntary_exit)
    for_ops(body.bls_to_execution_changes, process_bls_to_execution_change)
    for_ops(body.payload_attestations, process_payload_attestation)
    # [New in DC]
    for_ops(body.head_votes, process_head_vote)
```

##### Attestations

###### Modified `process_attestation`

*Note*: The function `process_attestation` is rewritten for the finality gadget.
Its checks read only the parts of the state that attestations do not modify, so
each attestation is checked against the state as it was before the block's
attestations.

```python
def process_attestation(state: BeaconState, attestation: Attestation) -> None:
    data = attestation.data
    assert is_well_formed_attestation_data(data)
    assert is_valid_attestation_data(state, data)

    # Bitfield length matches the number of validators
    assert len(attestation.aggregation_bits) == len(state.validators)
    attesting_indices = get_attesting_indices(state, attestation)
    current_epoch = get_current_epoch(state)
    for index in attesting_indices:
        assert is_active_validator(state.validators[index], current_epoch)

    # Participation flag indices
    participation_flag_indices = get_attestation_participation_flag_indices(state, data)

    # Verify signature
    assert is_valid_indexed_attestation(state, get_indexed_attestation(state, attestation))

    epoch_participation = state.current_epoch_participation
    proposer_reward_numerator = 0
    for index in attesting_indices:
        for pending in state.pending_finality:
            if pending.checkpoint == data.finality:
                pending.participation[index] = Boolean(True)
        if data.target == state.target_checkpoint:
            state.progress_participation[index] = Boolean(True)
            if not data.timeout:
                state.target_participation[index] = Boolean(True)

        for flag_index, weight in enumerate(PARTICIPATION_FLAG_WEIGHTS_DC):
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

##### Head votes

###### New `process_head_vote`

*Note*: Head votes belong to the available chain. A block must carry only valid
votes of the previous slot, but the votes do not modify the beacon state.

```python
def process_head_vote(state: BeaconState, vote: HeadVote) -> None:
    data = vote.data
    assert data.slot == state.slot - 1

    # Bitfield length matches the number of validators
    assert len(vote.aggregation_bits) == len(state.validators)
    voter_indices: list[ValidatorIndex] = []
    for index, bit in enumerate(vote.aggregation_bits):
        if bit:
            voter_indices.append(ValidatorIndex(index))
    assert len(voter_indices) > 0
    epoch = compute_epoch_at_slot(data.slot)
    for index in voter_indices:
        assert is_active_validator(state.validators[index], epoch)

    # Verify signature
    pubkeys = [state.validators[index].pubkey for index in voter_indices]
    domain = get_domain(state, DOMAIN_HEAD_VOTE, epoch)
    signing_root = compute_signing_root(data, domain)
    assert bls.FastAggregateVerify(pubkeys, signing_root, vote.signature)
```

#### Height events

##### New `process_height_events`

```python
def process_height_events(state: BeaconState) -> None:
    # Finalize the highest pending justification with a quorum
    for pending in state.pending_finality:
        if has_quorum(state, pending.participation):
            state.finalized_checkpoint = pending.checkpoint
            state.finalized_slot = pending.slot
    state.pending_finality = PendingFinalities(
        data=[
            pending
            for pending in state.pending_finality
            if pending.checkpoint.height > state.finalized_checkpoint.height
        ]
    )

    if has_quorum(state, state.target_participation):
        state.justified_checkpoint = state.target_checkpoint
        # Keep only the newest pending justifications
        if len(state.pending_finality) == PENDING_FINALITY_WINDOW:
            state.pending_finality = state.pending_finality[1:]
        state.pending_finality.append(
            PendingFinality(
                checkpoint=state.target_checkpoint,
                slot=state.target_slot,
                participation=Participation(
                    data=[Boolean(False) for _ in range(len(state.validators))]
                ),
            )
        )
        advance_height(state)
    elif (
        has_quorum(state, state.progress_participation)
        # Timeouts count only after the delay
        and state.slot >= state.target_slot + TIMEOUT_DELAY_SLOTS
    ):
        advance_height(state)
```

##### New `advance_height`

```python
def advance_height(state: BeaconState) -> None:
    state.target_checkpoint = HeightCheckpoint(
        height=state.target_checkpoint.height + 1,
        # Filled in by the next ``process_slot``
        root=Root(),
    )
    state.target_slot = state.latest_block_header.slot
    state.target_participation = Participation(
        data=[Boolean(False) for _ in range(len(state.validators))]
    )
    state.progress_participation = Participation(
        data=[Boolean(False) for _ in range(len(state.validators))]
    )
```
