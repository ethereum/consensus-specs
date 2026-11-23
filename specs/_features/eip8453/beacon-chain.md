# EIP-8453 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
  - [New `AttestationCommittee`](#new-attestationcommittee)
  - [New `AttestationCommitteeBits`](#new-attestationcommitteebits)
  - [New `EffectiveBalanceIncrements`](#new-effectivebalanceincrements)
  - [New `FinalityRewardHistory`](#new-finalityrewardhistory)
  - [New `HeadVoteCommittee`](#new-headvotecommittee)
  - [New `HeadVoteCommitteeBits`](#new-headvotecommitteebits)
  - [New `HeadVoteCommitteeIndices`](#new-headvotecommitteeindices)
  - [New `HeadVoteCommitteeWindow`](#new-headvotecommitteewindow)
  - [New `HeadVoteParticipation`](#new-headvoteparticipation)
  - [New `HeadVoteSupport`](#new-headvotesupport)
  - [New `HeadVoteSupportBits`](#new-headvotesupportbits)
  - [New `HeadVotes`](#new-headvotes)
  - [New `Height`](#new-height)
  - [New `HeightParticipation`](#new-heightparticipation)
  - [New `LegacyAttesterSlashings`](#new-legacyattesterslashings)
  - [New `PendingFinalities`](#new-pendingfinalities)
  - [New `Round`](#new-round)
  - [New `RoundParticipation`](#new-roundparticipation)
- [Constants](#constants)
  - [Participation flag indices](#participation-flag-indices)
  - [Incentivization weights](#incentivization-weights)
  - [Domains](#domains)
  - [Misc](#misc)
- [Presets](#presets)
  - [Finality gadget](#finality-gadget)
  - [Rounds](#rounds)
  - [Head votes](#head-votes)
  - [Rewards](#rewards)
  - [Inactivity](#inactivity)
  - [Max operations per block](#max-operations-per-block)
- [Containers](#containers)
  - [New `HeightCheckpoint`](#new-heightcheckpoint)
  - [New `FinalityRewardSlot`](#new-finalityrewardslot)
  - [New `PendingFinality`](#new-pendingfinality)
  - [New `HeadVoteData`](#new-headvotedata)
  - [New `HeadVote`](#new-headvote)
  - [New `HeadVoteMessage`](#new-headvotemessage)
  - [Modified `AttestationData`](#modified-attestationdata)
  - [Modified `SingleAttestation`](#modified-singleattestation)
  - [Modified `Attestation`](#modified-attestation)
  - [Modified `IndexedAttestation`](#modified-indexedattestation)
  - [Modified `BeaconBlockBody`](#modified-beaconblockbody)
  - [Modified `BeaconState`](#modified-beaconstate)
- [Helpers](#helpers)
  - [Predicates](#predicates)
    - [New `is_well_formed_attestation_data`](#new-is_well_formed_attestation_data)
    - [New `is_valid_attestation_data`](#new-is_valid_attestation_data)
    - [Modified `is_valid_indexed_attestation`](#modified-is_valid_indexed_attestation)
    - [New `is_double_target_vote`](#new-is_double_target_vote)
    - [New `is_conflicting_with_finality_pair`](#new-is_conflicting_with_finality_pair)
    - [Modified `is_slashable_attestation_data`](#modified-is_slashable_attestation_data)
    - [New `is_slashable_legacy_attestation_data`](#new-is_slashable_legacy_attestation_data)
    - [New `is_valid_legacy_indexed_attestation`](#new-is_valid_legacy_indexed_attestation)
    - [Modified `is_eligible_for_activation`](#modified-is_eligible_for_activation)
    - [Modified `is_active_builder`](#modified-is_active_builder)
    - [New `is_head_vote_same_slot`](#new-is_head_vote_same_slot)
    - [New `has_builder_payment_quorum`](#new-has_builder_payment_quorum)
    - [New `has_quorum`](#new-has_quorum)
    - [New `is_valid_aggregation_bits`](#new-is_valid_aggregation_bits)
  - [Misc](#misc-1)
    - [New `compute_round_at_slot`](#new-compute_round_at_slot)
    - [New `compute_start_slot_at_round`](#new-compute_start_slot_at_round)
    - [New `compute_attestation_committee_slot`](#new-compute_attestation_committee_slot)
    - [New `compute_uniform_selection`](#new-compute_uniform_selection)
    - [Modified `compute_ptc`](#modified-compute_ptc)
    - [New `compute_head_vote_committee`](#new-compute_head_vote_committee)
  - [Beacon state accessors](#beacon-state-accessors)
    - [New `get_attestation_committee`](#new-get_attestation_committee)
    - [New `get_fg_duty_positions`](#new-get_fg_duty_positions)
    - [New `get_aggregate_participants`](#new-get_aggregate_participants)
    - [Modified `get_attesting_indices`](#modified-get_attesting_indices)
    - [Modified `get_indexed_attestation`](#modified-get_indexed_attestation)
    - [New `get_head_vote_committee`](#new-get_head_vote_committee)
    - [Modified `get_inclusion_list_committee`](#modified-get_inclusion_list_committee)
    - [New `get_validator_weight`](#new-get_validator_weight)
    - [New `get_total_weight`](#new-get_total_weight)
    - [New `get_participating_weight`](#new-get_participating_weight)
    - [New `get_round_base_reward_per_increment`](#new-get_round_base_reward_per_increment)
    - [New `get_fg_rewards`](#new-get_fg_rewards)
  - [Beacon state mutators](#beacon-state-mutators)
    - [New `process_fg_rewards`](#new-process_fg_rewards)
  - [Validator registry](#validator-registry)
    - [Modified `add_validator_to_registry`](#modified-add_validator_to_registry)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Modified `process_slots`](#modified-process_slots)
  - [Modified `process_slot`](#modified-process_slot)
  - [Slot incentive processing](#slot-incentive-processing)
    - [New `settle_fg_slot`](#new-settle_fg_slot)
    - [New `open_fg_duties`](#new-open_fg_duties)
    - [Modified `process_inactivity_updates`](#modified-process_inactivity_updates)
  - [Epoch processing](#epoch-processing)
    - [Modified `process_epoch`](#modified-process_epoch)
    - [Modified `process_builder_pending_payments`](#modified-process_builder_pending_payments)
    - [Modified `process_pending_deposits`](#modified-process_pending_deposits)
    - [New `process_head_vote_committee_window`](#new-process_head_vote_committee_window)
  - [Block processing](#block-processing)
    - [Modified `process_block`](#modified-process_block)
    - [Operations](#operations)
      - [Modified `process_operations`](#modified-process_operations)
      - [Legacy attester slashings](#legacy-attester-slashings)
        - [New `process_legacy_attester_slashing`](#new-process_legacy_attester_slashing)
      - [Attestations](#attestations)
        - [Modified `process_attestation`](#modified-process_attestation)
      - [Head votes](#head-votes-1)
        - [New `process_head_vote`](#new-process_head_vote)
        - [New `process_head_vote_rewards`](#new-process_head_vote_rewards)
    - [Height events](#height-events)
      - [New `process_height_events`](#new-process_height_events)
      - [New `advance_height`](#new-advance_height)

<!-- mdformat-toc end -->

## Introduction

EIP-8453 ("Decoupled Consensus") composes two parts: a finality gadget (FG) and
an available chain (AC). The FG decides which blocks are accepted and finalizes
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

The AC keeps its own state outside of the beacon state. In every slot, a head
vote committee of `HEAD_VOTE_COMMITTEE_SIZE` validators, sampled by effective
balance, casts head votes. A block carries head votes of the previous and
current epochs and records which of the previous slot's votes the proposer
counted as support. The state transition records which seats voted for the block
of their slot, which weighs builder payments.

For head votes from the previous slot, an unslashed attester earns a reward for
the correct head and payload status unless the block includes conflicting votes
from that attester. The proposer earns one inclusion reward per committee seat
represented by a valid vote, including when the votes conflict.

Validators cast FG attestations in rounds of `SLOTS_PER_ROUND` slots. Each
active validator attests once per round. Once per epoch, the active validators
are split into `ATTESTATION_COMMITTEES_PER_ROUND` attestation committees, spread
evenly over the slots of a round. Each validator sits on one committee and, in
every round, casts its FG attestation in that committee's slot. Aggregates
combine the attestations of several committees.

An attester can earn up to `FG_ATTESTER_WEIGHT / WEIGHT_DENOMINATOR` of its base
reward per duty when its attestation is included promptly, in the slot after its
voting slot. That slot's proposer can earn
`FG_PROPOSER_WEIGHT / WEIGHT_DENOMINATOR` of the same base reward. A target vote
earns these net rewards before rounding. If the same attestation also carries a
finality pair for the latest justification pending at the start of the voting
slot, the same reward weights apply separately to that pair.

The payments to the attester and the including proposer decay with each slot of
delay and reach zero after `FG_REWARD_WINDOW` slots. At the end of the first
inclusion slot, the attester and the proposer assigned to that slot each pay a
fixed penalty per duty. A prompt target vote or finality pair pays each party
twice its penalty, so a missed duty costs as much as a prompt one earns. Before
deductions, a timeout pays each party half as much as a target vote included at
the same delay. A prompt timeout therefore covers each party's height vote
penalty. A later proposer can still include the vote for payment even if the
height advances or the checkpoint finalizes.

The chain updates the validator's inactivity score once per assigned height
vote, when its 16-slot window ends. A target vote or timeout for the assigned
target reduces the score. Missing the vote increases it. Voting weight in FG
quorums falls with the square of the score. A short absence costs almost no
voting weight, a long one costs a lot, and a validator whose weight reaches zero
is exited and keeps its remaining stake. When finality is delayed, this lets the
participating validators regain a quorum. Attesters continue earning progress
and finality rewards throughout the delay.

*Note*: A quorum is two thirds of the total weight of the active validators. A
validator's weight is proportional to its current effective balance, reduced by
its inactivity score. Slashed validators count toward the total but not toward a
quorum.

*Note*: This specification is built upon [Heze](../../heze/beacon-chain.md).

## Types

### New `AttestationCommittee`

```python
class AttestationCommittee(ProgressiveList[ValidatorIndex]):
    """
    An attestation committee of an epoch.
    """
```

### New `AttestationCommitteeBits`

```python
class AttestationCommitteeBits(BitVector):
    """
    Bits marking which attestation committees of an epoch participate in an
    attestation.
    """

    LENGTH = ATTESTATION_COMMITTEES_PER_ROUND
```

### New `EffectiveBalanceIncrements`

```python
class EffectiveBalanceIncrements(ProgressiveList[Uint16]):
    """Effective balances in increments, in committee order."""
```

### New `FinalityRewardHistory`

```python
class FinalityRewardHistory(Vector[FinalityRewardSlot]):
    """The current voting slot and the preceding 16 voting slots."""

    LENGTH = FG_REWARD_WINDOW + 1
```

### New `HeadVoteCommittee`

```python
class HeadVoteCommittee(Vector[ValidatorIndex]):
    """
    The head vote committee of a slot.
    """

    LENGTH = HEAD_VOTE_COMMITTEE_SIZE
```

### New `HeadVoteCommitteeBits`

```python
class HeadVoteCommitteeBits(BitVector):
    """
    The participation bits of the head vote committee, one bit per member in
    committee order.
    """

    LENGTH = HEAD_VOTE_COMMITTEE_SIZE
```

### New `HeadVoteCommitteeIndices`

```python
class HeadVoteCommitteeIndices(List[ValidatorIndex]):
    """
    The indices of the validators participating in a head vote.
    """

    LIMIT = HEAD_VOTE_COMMITTEE_SIZE
```

### New `HeadVoteCommitteeWindow`

```python
class HeadVoteCommitteeWindow(Vector[HeadVoteCommittee]):
    """
    A rolling window of head vote committees for the previous, current, and
    lookahead epochs.
    """

    LENGTH = Uint64(MIN_SEED_LOOKAHEAD + 2) * Uint64(SLOTS_PER_EPOCH)
```

### New `HeadVoteParticipation`

```python
class HeadVoteParticipation(Vector[HeadVoteCommitteeBits]):
    """
    The seats of each slot's head vote committee that voted for the block of
    that slot, for the previous and current epochs.
    """

    LENGTH = 2 * SLOTS_PER_EPOCH
```

### New `HeadVoteSupport`

```python
class HeadVoteSupport(ProgressiveList[HeadVoteSupportBits]):
    """
    The support bits of each head vote in a beacon block.
    """
```

### New `HeadVoteSupportBits`

```python
class HeadVoteSupportBits(ProgressiveBitList):
    """
    One bit per voter of a head vote, in the order of its ``voter_indices``,
    set when the proposer counted that voter's vote as support.
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

### New `HeightParticipation`

```python
class HeightParticipation(ProgressiveList[Boolean]):
    """
    Whether each validator in the registry voted at a height, in validator index
    order.
    """
```

### New `LegacyAttesterSlashings`

```python
class LegacyAttesterSlashings(ProgressiveList[heze.AttesterSlashing]):
    """
    The attester slashings included in a beacon block for attestations made
    before this upgrade.
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

### New `Round`

```python
class Round(Uint64):
    """
    A round number. A round spans ``SLOTS_PER_ROUND`` slots, in which each
    active validator has one assigned FG voting slot.
    """
```

### New `RoundParticipation`

```python
class RoundParticipation(ProgressiveList[ParticipationFlags]):
    """
    Participation flags in registry order, or in committee order for one voting slot.
    """
```

## Constants

### Participation flag indices

| Name                        | Value       |
| --------------------------- | ----------- |
| `PROGRESS_FLAG_INDEX`       | `Uint64(0)` |
| `FINALITY_FLAG_INDEX`       | `Uint64(1)` |
| `TIMEOUT_REWARD_FLAG_INDEX` | `Uint64(2)` |
| `ACTIVITY_FLAG_INDEX`       | `Uint64(3)` |

In the reward records, a progress flag accompanied by the timeout reward flag
means the attester earned the progress reward for a timeout. The activity flag
records a target vote or timeout for the assigned target, including when its
reward rounds to zero.

### Incentivization weights

| Name                 | Value        |
| -------------------- | ------------ |
| `HEAD_VOTE_WEIGHT`   | `Uint64(4)`  |
| `FG_ATTESTER_WEIGHT` | `Uint64(24)` |
| `FG_PROPOSER_WEIGHT` | `Uint64(3)`  |

For each head vote, the attester and proposer have equal reward weights. For the
finality gadget, the table gives the net reward for a target vote or finality
pair included at the first opportunity and the penalty for a missed duty, before
rounding. A timeout included at the first opportunity earns zero net. With
target votes and both duties filled, the head, progress and finality weights sum
to `4 + 4 + 2 * (24 + 3) = 62`. Sync committee participants have weight 2, and
their proposers also earn the existing sync committee inclusion reward.

### Domains

| Name                         | Value                      |
| ---------------------------- | -------------------------- |
| `DOMAIN_HEAD_VOTE`           | `DomainType("0x12000000")` |
| `DOMAIN_HEAD_VOTE_COMMITTEE` | `DomainType("0x13000000")` |
| `DOMAIN_FINALITY_ATTESTER`   | `DomainType("0x14000000")` |

### Misc

| Name                  | Value             |
| --------------------- | ----------------- |
| `TIMEOUT_DELAY_SLOTS` | `SLOTS_PER_ROUND` |
| `FG_REWARD_WINDOW`    | `Slot(16)`        |

## Presets

### Finality gadget

| Name                      | Value                |
| ------------------------- | -------------------- |
| `PENDING_FINALITY_WINDOW` | `Uint64(2**2)` (= 4) |

*Note*: `PENDING_FINALITY_WINDOW` must be at least 2.

### Rounds

| Name                               | Value                       |
| ---------------------------------- | --------------------------- |
| `SLOTS_PER_ROUND`                  | `Slot(2**3)` (= 8)          |
| `ATTESTATION_COMMITTEES_PER_ROUND` | `Uint64(2**11)` (= 2,048)   |
| `MAX_VALIDATORS_PER_AGGREGATE`     | `Uint64(2**17)` (= 131,072) |

*Note*: `ATTESTATION_COMMITTEES_PER_ROUND` must be a multiple of
`SLOTS_PER_ROUND`.

### Head votes

| Name                       | Value                     |
| -------------------------- | ------------------------- |
| `HEAD_VOTE_COMMITTEE_SIZE` | `Uint64(2**10)` (= 1,024) |

### Rewards

| Name                  | Value                 |
| --------------------- | --------------------- |
| `ROUND_REWARD_FACTOR` | `Uint64(2**4)` (= 16) |

### Inactivity

| Name                        | Value                      |
| --------------------------- | -------------------------- |
| `EJECTION_INACTIVITY_SCORE` | `Uint64(2**16)` (= 65,536) |

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

### New `FinalityRewardSlot`

```python
class FinalityRewardSlot(Container):
    target: HeightCheckpoint
    finality: HeightCheckpoint
    finalized_epoch: Epoch
    reward_per_increment: Gwei
    increments: EffectiveBalanceIncrements
    flags: RoundParticipation
```

### New `PendingFinality`

```python
class PendingFinality(Container):
    checkpoint: HeightCheckpoint
    slot: Slot
    participation: HeightParticipation
```

### New `HeadVoteData`

```python
class HeadVoteData(Container):
    slot: Slot
    beacon_block_root: Root
    payload_status: PayloadStatus
```

### New `HeadVote`

```python
class HeadVote(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=3)

    voter_indices: HeadVoteCommitteeIndices
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
    # [Modified in EIP8453]
    # Removed `slot`
    # [Modified in EIP8453]
    # Removed `index`
    # [Modified in EIP8453]
    # Removed `beacon_block_root`
    # [Modified in EIP8453]
    # Removed `source`
    # [Modified in EIP8453]
    target: HeightCheckpoint
    # [New in EIP8453]
    timeout: Boolean
    # [New in EIP8453]
    finality: HeightCheckpoint
```

### Modified `SingleAttestation`

```python
class SingleAttestation(Container):
    committee_index: CommitteeIndex
    attester_index: ValidatorIndex
    data: AttestationData
    signature: BLSSignature
    # [New in EIP8453]
    epoch: Epoch
```

### Modified `Attestation`

*Note*: `epoch` is not signed. It selects the attestation committees that
`committee_bits` and `aggregation_bits` refer to, and the signature domain.

```python
class Attestation(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=5)

    aggregation_bits: AggregationBits
    data: AttestationData
    signature: BLSSignature
    # [Modified in EIP8453]
    committee_bits: AttestationCommitteeBits
    # [New in EIP8453]
    epoch: Epoch
```

### Modified `IndexedAttestation`

```python
class IndexedAttestation(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=4)

    attesting_indices: AttestingIndices
    data: AttestationData
    signature: BLSSignature
    # [New in EIP8453]
    epoch: Epoch
```

### Modified `BeaconBlockBody`

*Note*: `attester_slashings` now holds slashings of this upgrade's attestations.
`legacy_attester_slashings` holds slashings of attestations made before this
upgrade and should be removed in a later upgrade.

```python
class BeaconBlockBody(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=16, gaps=(1, 6))

    randao_reveal: BLSSignature
    graffiti: Bytes32
    proposer_slashings: ProposerSlashings
    attester_slashings: AttesterSlashings
    attestations: Attestations
    voluntary_exits: VoluntaryExits
    sync_aggregate: SyncAggregate
    bls_to_execution_changes: BLSToExecutionChanges
    signed_execution_payload_bid: SignedExecutionPayloadBid
    payload_attestations: PayloadAttestations
    parent_execution_requests: ExecutionRequests
    # [New in EIP8453]
    head_votes: HeadVotes
    # [New in EIP8453]
    head_vote_support: HeadVoteSupport
    # [New in EIP8453]
    legacy_attester_slashings: LegacyAttesterSlashings
```

### Modified `BeaconState`

*Note*: The positions of the epoch participation and Casper FFG fields are left
as gaps, so their generalized indices are never reused. `finalized_checkpoint`
keeps its name but moves to a new position.

```python
class BeaconState(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=58, gaps=(8, 9, 10, 15, 16, 17, 18, 19, 20, 28))

    genesis_time: Uint64
    genesis_validators_root: Root
    slot: Slot
    fork: Fork
    latest_block_header: BeaconBlockHeader
    block_roots: BlockRoots
    state_roots: StateRoots
    historical_roots: HistoricalRoots
    validators: Validators
    balances: Balances
    randao_mixes: RandaoMixes
    slashings: Slashings
    # [Modified in EIP8453]
    # Removed `previous_epoch_participation`
    # [Modified in EIP8453]
    # Removed `current_epoch_participation`
    # [Modified in EIP8453]
    # Removed `justification_bits`
    # [Modified in EIP8453]
    # Removed `previous_justified_checkpoint`
    # [Modified in EIP8453]
    # Removed `current_justified_checkpoint`
    # [Modified in EIP8453]
    # Removed `finalized_checkpoint`
    inactivity_scores: InactivityScores
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    latest_block_hash: Hash32
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
    historical_summaries: HistoricalSummaries
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
    # [New in EIP8453]
    target_checkpoint: HeightCheckpoint
    # [New in EIP8453]
    justified_checkpoint: HeightCheckpoint
    # [New in EIP8453]
    finalized_checkpoint: HeightCheckpoint
    # [New in EIP8453]
    target_slot: Slot
    # [New in EIP8453]
    finalized_slot: Slot
    # [New in EIP8453]
    target_participation: HeightParticipation
    # [New in EIP8453]
    progress_participation: HeightParticipation
    # [New in EIP8453]
    pending_finality: PendingFinalities
    # [New in EIP8453]
    head_vote_participation: HeadVoteParticipation
    # [New in EIP8453]
    head_vote_committee_window: HeadVoteCommitteeWindow
    # [New in EIP8453]
    reward_history: FinalityRewardHistory
    # [New in EIP8453]
    rewarded_flags: RoundParticipation
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
    return (
        data.finality in [pending.checkpoint for pending in state.pending_finality]
        and data.finality.height < data.target.height < state.target_checkpoint.height
    )
```

#### Modified `is_valid_indexed_attestation`

```python
def is_valid_indexed_attestation(
    state: BeaconState, indexed_attestation: IndexedAttestation
) -> bool:
    """
    Check if ``indexed_attestation`` is not empty, has sorted and unique
    indices and has a valid aggregate signature.
    """
    # Verify indices are sorted and unique
    indices = indexed_attestation.attesting_indices
    if (
        len(indices) == 0
        # [Modified in EIP8453]
        or len(indices) > MAX_VALIDATORS_PER_AGGREGATE
        or list(indices) != sorted(set(indices))
    ):
        return False
    # Verify aggregate signature
    pubkeys = [state.validators[i].pubkey for i in indices]
    # [Modified in EIP8453]
    domain = get_domain(state, DOMAIN_FINALITY_ATTESTER, indexed_attestation.epoch)
    signing_root = compute_signing_root(indexed_attestation.data, domain)
    return bls.FastAggregateVerify(pubkeys, signing_root, indexed_attestation.signature)
```

#### New `is_double_target_vote`

```python
def is_double_target_vote(data_1: AttestationData, data_2: AttestationData) -> bool:
    """
    Check if ``data_1`` and ``data_2`` are target votes for different roots
    at the same height.
    """
    if data_1.timeout:
        return False
    if data_2.timeout:
        return False
    if data_1.target.height != data_2.target.height:
        return False
    if data_1.target.root == data_2.target.root:
        return False
    return True
```

#### New `is_conflicting_with_finality_pair`

```python
def is_conflicting_with_finality_pair(data: AttestationData, finality: HeightCheckpoint) -> bool:
    """
    Check if ``data`` votes at the height of the non-empty ``finality`` pair
    without a target vote for its root.
    """
    if finality == HeightCheckpoint.empty():
        return False
    if data.target.height != finality.height:
        return False
    if data.timeout:
        return True
    if data.target.root != finality.root:
        return True
    return False
```

#### Modified `is_slashable_attestation_data`

*Note*: The function `is_slashable_attestation_data` is rewritten for the
finality gadget.

```python
def is_slashable_attestation_data(data_1: AttestationData, data_2: AttestationData) -> bool:
    """
    Check if ``data_1`` and ``data_2`` are slashable according to the finality
    gadget rules.
    """
    if is_double_target_vote(data_1, data_2):
        return True
    if is_conflicting_with_finality_pair(data_1, data_2.finality):
        return True
    if is_conflicting_with_finality_pair(data_2, data_1.finality):
        return True
    return False
```

#### New `is_slashable_legacy_attestation_data`

```python
def is_slashable_legacy_attestation_data(
    data_1: heze.AttestationData, data_2: heze.AttestationData
) -> bool:
    """
    Check if ``data_1`` and ``data_2`` are slashable under Casper FFG rules.
    """
    return (
        # Double vote
        (data_1 != data_2 and data_1.target.epoch == data_2.target.epoch)
        or
        # Surround vote
        (data_1.source.epoch < data_2.source.epoch and data_2.target.epoch < data_1.target.epoch)
    )
```

#### New `is_valid_legacy_indexed_attestation`

```python
def is_valid_legacy_indexed_attestation(
    state: BeaconState, indexed_attestation: heze.IndexedAttestation
) -> bool:
    """
    Check if ``indexed_attestation`` is not empty, has sorted and unique indices
    and has a valid aggregate signature.
    """
    indices = indexed_attestation.attesting_indices
    if (
        len(indices) == 0
        or len(indices) > MAX_VALIDATORS_PER_COMMITTEE * MAX_COMMITTEES_PER_SLOT
        or list(indices) != sorted(set(indices))
    ):
        return False
    pubkeys = [state.validators[i].pubkey for i in indices]
    domain = get_domain(state, DOMAIN_BEACON_ATTESTER, indexed_attestation.data.target.epoch)
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
        # [Modified in EIP8453]
        # Placement in queue is finalized
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
        # [Modified in EIP8453]
        # Placement in builder list is finalized
        builder.deposit_epoch < compute_epoch_at_slot(state.finalized_slot)
        # Has not initiated exit
        and builder.withdrawable_epoch == FAR_FUTURE_EPOCH
    )
```

#### New `is_head_vote_same_slot`

```python
def is_head_vote_same_slot(state: BeaconState, data: HeadVoteData) -> bool:
    """
    Check if ``data`` votes for the block proposed at its slot.
    """
    if data.slot == GENESIS_SLOT:
        return True
    if data.beacon_block_root != get_block_root_at_slot(state, data.slot):
        return False
    if data.beacon_block_root == get_block_root_at_slot(state, data.slot - 1):
        return False
    return True
```

#### New `has_builder_payment_quorum`

```python
def has_builder_payment_quorum(participation: HeadVoteCommitteeBits) -> bool:
    """
    Check if the seats set in ``participation`` reach the payment quorum.
    """
    seats = 0
    for is_set in participation:
        if is_set:
            seats += 1
    quorum = HEAD_VOTE_COMMITTEE_SIZE * BUILDER_PAYMENT_THRESHOLD_NUMERATOR
    return seats * BUILDER_PAYMENT_THRESHOLD_DENOMINATOR >= quorum
```

#### New `has_quorum`

```python
def has_quorum(state: BeaconState, participation: HeightParticipation) -> bool:
    """
    Check if the validators marked in ``participation`` hold at least two
    thirds of the total weight of the active validators.
    """
    active_indices = set(get_active_validator_indices(state, get_current_epoch(state)))
    participating_weight = get_participating_weight(state, participation)
    total_weight = get_total_weight(state, active_indices)
    return participating_weight > 0 and participating_weight * 3 >= total_weight * 2
```

#### New `is_valid_aggregation_bits`

```python
def is_valid_aggregation_bits(state: BeaconState, epoch: Epoch, aggregate: Attestation) -> bool:
    """
    Check if the ``aggregation_bits`` of ``aggregate`` has one bit for each
    member of the attestation committees marked in its ``committee_bits``,
    within the aggregate limit.
    """
    committees_size = 0
    for committee_index in get_committee_indices(aggregate.committee_bits):
        committees_size += len(get_attestation_committee(state, epoch, committee_index))
    if committees_size > MAX_VALIDATORS_PER_AGGREGATE:
        return False
    return len(aggregate.aggregation_bits) == committees_size
```

### Misc

#### New `compute_round_at_slot`

```python
def compute_round_at_slot(slot: Slot) -> Round:
    """
    Return the round number at ``slot``.
    """
    return Round(slot // SLOTS_PER_ROUND)
```

#### New `compute_start_slot_at_round`

```python
def compute_start_slot_at_round(round: Round) -> Slot:
    """
    Return the start slot of ``round``.
    """
    return Slot(round) * SLOTS_PER_ROUND
```

#### New `compute_attestation_committee_slot`

*Note*: The committees of a round are assigned to its slots in order, with
`ATTESTATION_COMMITTEES_PER_ROUND // SLOTS_PER_ROUND` committees per slot.

```python
def compute_attestation_committee_slot(round: Round, index: CommitteeIndex) -> Slot:
    """
    Return the slot of ``round`` assigned to the committee at ``index``.
    """
    committees_per_slot = ATTESTATION_COMMITTEES_PER_ROUND // Uint64(SLOTS_PER_ROUND)
    return compute_start_slot_at_round(round) + Slot(index // committees_per_slot)
```

#### New `compute_uniform_selection`

```python
def compute_uniform_selection(
    indices: Sequence[ValidatorIndex], seed: Bytes32, size: Uint64
) -> Sequence[ValidatorIndex]:
    """
    Return ``size`` indices sampled uniformly from ``indices`` by shuffling. The
    returned list contains duplicates only if ``size`` exceeds the number of
    ``indices``.
    """
    total = Uint64(len(indices))
    assert total > 0
    selected: list[ValidatorIndex] = []
    for i in range(size):
        selected.append(indices[compute_shuffled_index(Uint64(i) % total, total, seed)])
    return selected
```

#### Modified `compute_ptc`

```python
def compute_ptc(state: BeaconState, slot: Slot) -> PayloadTimelinessCommittee:
    """
    Get the payload timeliness committee for ``slot``, with possible duplicates.
    """
    epoch = compute_epoch_at_slot(slot)
    seed = sha256(get_seed(state, epoch, DOMAIN_PTC_ATTESTER) + uint_to_bytes(slot))
    # [Modified in EIP8453]
    indices = get_active_validator_indices(state, epoch)
    # [Modified in EIP8453]
    return PayloadTimelinessCommittee(
        data=compute_balance_weighted_selection(
            state,
            indices,
            seed,
            size=PTC_SIZE,
            shuffle_indices=True,
        )
    )
```

#### New `compute_head_vote_committee`

```python
def compute_head_vote_committee(state: BeaconState, slot: Slot) -> HeadVoteCommittee:
    """
    Return the head vote committee for ``slot``, with possible duplicates.
    """
    epoch = compute_epoch_at_slot(slot)
    seed = sha256(get_seed(state, epoch, DOMAIN_HEAD_VOTE_COMMITTEE) + uint_to_bytes(slot))
    indices = get_active_validator_indices(state, epoch)
    return HeadVoteCommittee(
        data=compute_balance_weighted_selection(
            state,
            indices,
            seed,
            size=HEAD_VOTE_COMMITTEE_SIZE,
            shuffle_indices=True,
        )
    )
```

### Beacon state accessors

#### New `get_attestation_committee`

*Note*: The active validators are not shuffled. They are split evenly into
`ATTESTATION_COMMITTEES_PER_ROUND` committees, in index order rotated by
`epoch`, so each validator sits on exactly one.

```python
def get_attestation_committee(
    state: BeaconState, epoch: Epoch, index: CommitteeIndex
) -> AttestationCommittee:
    """
    Return the attestation committee at ``index`` for ``epoch``.
    """
    indices = get_active_validator_indices(state, epoch)
    start = (len(indices) * index) // ATTESTATION_COMMITTEES_PER_ROUND
    end = (len(indices) * (index + 1)) // ATTESTATION_COMMITTEES_PER_ROUND
    committee = AttestationCommittee()
    for position in range(start, end):
        committee.append(indices[(position + epoch) % len(indices)])
    return committee
```

#### New `get_fg_duty_positions`

Return the position of each validator assigned to vote in `slot`, as used in
that slot's reward record. Implementations can cache the positions within an
epoch.

```python
def get_fg_duty_positions(state: BeaconState, slot: Slot) -> dict[ValidatorIndex, int]:
    epoch = compute_epoch_at_slot(slot)
    count = ATTESTATION_COMMITTEES_PER_ROUND // Uint64(SLOTS_PER_ROUND)
    start = int(slot % SLOTS_PER_ROUND) * int(count)
    positions = {}
    for committee in range(start, start + int(count)):
        for index in get_attestation_committee(state, epoch, CommitteeIndex(committee)):
            positions[index] = len(positions)
    return positions
```

#### New `get_aggregate_participants`

```python
def get_aggregate_participants(
    state: BeaconState, epoch: Epoch, aggregate: Attestation
) -> set[ValidatorIndex]:
    """
    Return the validators marked in the ``aggregation_bits`` of ``aggregate``,
    which concatenates the attestation committees marked in its
    ``committee_bits`` for ``epoch``.
    """
    participants: set[ValidatorIndex] = set()
    committee_offset = 0
    for committee_index in get_committee_indices(aggregate.committee_bits):
        committee = get_attestation_committee(state, epoch, committee_index)
        for i, validator_index in enumerate(committee):
            if aggregate.aggregation_bits[committee_offset + i]:
                participants.add(validator_index)
        committee_offset += len(committee)
    return participants
```

#### Modified `get_attesting_indices`

```python
def get_attesting_indices(state: BeaconState, attestation: Attestation) -> set[ValidatorIndex]:
    """
    Return the set of attesting indices corresponding to ``aggregation_bits``
    and ``committee_bits``.
    """
    return get_aggregate_participants(state, attestation.epoch, attestation)
```

#### Modified `get_indexed_attestation`

```python
def get_indexed_attestation(state: BeaconState, attestation: Attestation) -> IndexedAttestation:
    """
    Return the indexed attestation corresponding to ``attestation``.
    """
    attesting_indices = get_attesting_indices(state, attestation)

    return IndexedAttestation(
        attesting_indices=AttestingIndices(data=sorted(attesting_indices)),
        data=attestation.data,
        signature=attestation.signature,
        # [New in EIP8453]
        epoch=attestation.epoch,
    )
```

#### New `get_head_vote_committee`

```python
def get_head_vote_committee(state: BeaconState, slot: Slot) -> HeadVoteCommittee:
    """
    Return the head vote committee for ``slot``.
    """
    epoch = compute_epoch_at_slot(slot)
    assert epoch >= EIP8453_FORK_EPOCH
    state_epoch = get_current_epoch(state)
    if epoch < state_epoch:
        assert epoch + 1 == state_epoch
        return state.head_vote_committee_window[slot % SLOTS_PER_EPOCH]
    assert epoch <= state_epoch + MIN_SEED_LOOKAHEAD
    offset = Uint64(epoch - state_epoch + 1) * SLOTS_PER_EPOCH
    return state.head_vote_committee_window[offset + slot % SLOTS_PER_EPOCH]
```

#### Modified `get_inclusion_list_committee`

```python
def get_inclusion_list_committee(state: BeaconState, slot: Slot) -> InclusionListCommittee:
    """
    Get the inclusion list committee for the given ``slot``.
    """
    epoch = compute_epoch_at_slot(slot)
    seed = sha256(get_seed(state, epoch, DOMAIN_INCLUSION_LIST_COMMITTEE) + uint_to_bytes(slot))
    indices = get_active_validator_indices(state, epoch)
    return InclusionListCommittee(
        data=compute_uniform_selection(
            indices,
            seed,
            size=INCLUSION_LIST_COMMITTEE_SIZE,
        )
    )
```

#### New `get_validator_weight`

*Note*: A validator's weight is its current effective balance in increments,
multiplied by `EJECTION_INACTIVITY_SCORE**2 - inactivity_score**2`. The weight
reaches zero at `EJECTION_INACTIVITY_SCORE`. Weight calculations use `Uint256`
to avoid overflow when summing weights and checking quorums.

```python
def get_validator_weight(state: BeaconState, index: ValidatorIndex) -> Uint256:
    """
    Return the weight of the validator at ``index`` in finality gadget quorums.
    """
    increments = Uint256(state.validators[index].effective_balance // EFFECTIVE_BALANCE_INCREMENT)
    inactivity_score = min(state.inactivity_scores[index], EJECTION_INACTIVITY_SCORE)
    inactivity_weight = (EJECTION_INACTIVITY_SCORE - inactivity_score) * (
        EJECTION_INACTIVITY_SCORE + inactivity_score
    )
    return increments * Uint256(inactivity_weight)
```

#### New `get_total_weight`

```python
def get_total_weight(state: BeaconState, indices: set[ValidatorIndex]) -> Uint256:
    """
    Return the combined weight of the ``indices``.
    """
    total_weight = Uint256(0)
    for index in indices:
        total_weight += get_validator_weight(state, index)
    return total_weight
```

#### New `get_participating_weight`

```python
def get_participating_weight(state: BeaconState, participation: HeightParticipation) -> Uint256:
    """
    Return the combined weight of the active and unslashed validators marked in
    ``participation``.
    """
    participating_indices: set[ValidatorIndex] = set()
    for index in get_active_validator_indices(state, get_current_epoch(state)):
        if participation[index] and not state.validators[index].slashed:
            participating_indices.add(index)
    return get_total_weight(state, participating_indices)
```

#### New `get_round_base_reward_per_increment`

```python
def get_round_base_reward_per_increment(state: BeaconState) -> Gwei:
    total_balance_root = integer_squareroot(get_total_active_balance(state))
    return EFFECTIVE_BALANCE_INCREMENT * ROUND_REWARD_FACTOR // total_balance_root
```

#### New `get_fg_rewards`

Return the attester's and the including proposer's rewards before the fixed
penalty. For a vote included `d >= 1` slots after its first inclusion slot, let
`r = (7/8) * (23/24)**(d - 1)` and `x = (d - 1) / (FG_REWARD_WINDOW - 1)`. The
attester retains `r` of its reward and the proposer `2**(-d) + x * r / 4`, both
multiplied by the taper `(1 - x**3)**3`. A vote whose attester reward rounds to
zero earns neither payment.

```python
def get_fg_rewards(base_reward: Gwei, delay: Slot, timeout: bool = False) -> tuple[Gwei, Gwei]:
    if delay >= FG_REWARD_WINDOW:
        return Gwei(0), Gwei(0)
    gross = Uint256(base_reward) * (1 if timeout else 2)
    attester = gross * Uint256(FG_ATTESTER_WEIGHT)
    proposer = gross * Uint256(FG_PROPOSER_WEIGHT)
    denominator = Uint256(WEIGHT_DENOMINATOR)
    if delay > 0:
        elapsed = Uint256(delay - 1)
        span = Uint256(FG_REWARD_WINDOW - 1)
        taper = (span**3 - elapsed**3) ** 3
        retention_num = 7 * 23**elapsed
        retention_den = 8 * 24**elapsed
        halvings = 2 ** Uint256(delay)
        scale = 4 * span * halvings
        attester *= taper * retention_num * scale
        proposer *= taper * (4 * span * retention_den + elapsed * retention_num * halvings)
        denominator *= span**9 * retention_den * scale
    attester_reward = Gwei(attester // denominator)
    if attester_reward == 0:
        return Gwei(0), Gwei(0)
    return attester_reward, Gwei((proposer + denominator - 1) // denominator)
```

### Beacon state mutators

#### New `process_fg_rewards`

Return whether `data` earned a reward or recorded activity for an earlier voting
slot. A vote included in its own voting slot only records activity for that
slot. A reward first earned during the validator's next voting slot also carries
into that slot's duties: the progress reward if the target is the same, and the
finality reward if the same pair is still pending.

```python
def process_fg_rewards(
    state: BeaconState, data: AttestationData, indices: Sequence[ValidatorIndex], epoch: Epoch
) -> bool:
    current = state.reward_history[state.slot % len(state.reward_history)]
    current_positions = get_fg_duty_positions(state, state.slot)
    recorded = False
    proposer_reward = Gwei(0)
    for age in range(min(FG_REWARD_WINDOW, state.slot) + 1):
        voting_slot = state.slot - age
        row = state.reward_history[voting_slot % len(state.reward_history)]
        if len(row.flags) == 0 or epoch < row.finalized_epoch:
            continue
        components = []
        if data.target == row.target:
            components.append(PROGRESS_FLAG_INDEX)
        if row.finality != HeightCheckpoint.empty() and data.finality == row.finality:
            components.append(FINALITY_FLAG_INDEX)
        if not components:
            continue
        positions = current_positions if age == 0 else get_fg_duty_positions(state, voting_slot)
        for index in indices:
            pos = positions.get(index)
            if pos is None or state.validators[index].slashed:
                continue
            flags = row.flags[pos]
            if data.target == row.target and not (
                has_flag(flags, ACTIVITY_FLAG_INDEX) or has_flag(flags, PROGRESS_FLAG_INDEX)
            ):
                row.flags[pos] = add_flag(row.flags[pos], ACTIVITY_FLAG_INDEX)
                recorded |= age > 0
            if age == 0:
                continue
            delay = Slot(age - 1)
            base = Gwei(row.increments[pos]) * row.reward_per_increment
            for component in components:
                if has_flag(row.flags[pos], component):
                    continue
                timeout = component == PROGRESS_FLAG_INDEX and bool(data.timeout)
                attester, proposer = get_fg_rewards(base, delay, timeout)
                if attester == 0:
                    continue
                flags = add_flag(ParticipationFlags(0), component)
                if timeout:
                    flags = add_flag(flags, TIMEOUT_REWARD_FLAG_INDEX)
                row.flags[pos] |= flags
                recorded = True
                if delay > 0:
                    increase_balance(state, index, attester)
                    proposer_reward += proposer
                if not has_flag(state.rewarded_flags[index], component) and (
                    (component == PROGRESS_FLAG_INDEX and data.target == current.target)
                    or (component == FINALITY_FLAG_INDEX and data.finality == current.finality)
                ):
                    state.rewarded_flags[index] |= flags
                    current_pos = current_positions.get(index)
                    if current_pos is not None:
                        current.flags[current_pos] |= flags
    if proposer_reward > 0:
        increase_balance(state, get_beacon_proposer_index(state), proposer_reward)
    return recorded
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
    set_or_append_list(state.inactivity_scores, index, Uint64(0))
    # [New in EIP8453]
    set_or_append_list(state.rewarded_flags, index, ParticipationFlags(0))
    # [New in EIP8453]
    set_or_append_list(state.target_participation, index, Boolean(False))
    # [New in EIP8453]
    set_or_append_list(state.progress_participation, index, Boolean(False))
    # [New in EIP8453]
    for pending in state.pending_finality:
        set_or_append_list(pending.participation, index, Boolean(False))
```

## Beacon chain state transition function

### Modified `process_slots`

```python
def process_slots(state: BeaconState, slot: Slot) -> None:
    assert state.slot < slot
    while state.slot < slot:
        process_slot(state)
        # Process epoch on the start slot of the next epoch
        if (state.slot + 1) % SLOTS_PER_EPOCH == 0:
            process_epoch(state)
        state.slot = state.slot + 1
        # [New in EIP8453]
        open_fg_duties(state)
```

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
    # [New in EIP8453]
    # Cache target checkpoint root
    if state.target_checkpoint.root == Root():
        state.target_checkpoint.root = previous_block_root
    # [New in EIP8453]
    settle_fg_slot(state)
    # [New in EIP8453]
    process_inactivity_updates(state)
    # Unset the next payload availability
    next_slot_index = (state.slot + 1) % SLOTS_PER_HISTORICAL_ROOT
    state.execution_payload_availability[next_slot_index] = Boolean(False)
```

### Slot incentive processing

#### New `settle_fg_slot`

A missed block still charges the slot's proposer and pays the attesters whose
votes carried forward.

```python
def settle_fg_slot(state: BeaconState) -> None:
    if state.slot == 0:
        return
    voting_slot = state.slot - 1
    slot_index = voting_slot % len(state.reward_history)
    row = state.reward_history[slot_index]
    if len(row.flags) == 0:
        return
    component_count = 1 + int(row.finality != HeightCheckpoint.empty())
    produced = state.latest_block_header.slot == state.slot
    proposer = get_beacon_proposer_index(state)
    proposer_earned, proposer_penalty = Gwei(0), Gwei(0)
    for index, pos in get_fg_duty_positions(state, voting_slot).items():
        if state.validators[index].slashed:
            continue
        base = Gwei(row.increments[pos]) * row.reward_per_increment
        attester_gross, proposer_gross = get_fg_rewards(base, Slot(0))
        if attester_gross == 0:
            continue
        # A prompt timeout covers each party's penalty.
        attester_half, proposer_half = get_fg_rewards(base, Slot(0), timeout=True)
        flags = row.flags[pos]
        paid = int(has_flag(flags, PROGRESS_FLAG_INDEX)) + int(has_flag(flags, FINALITY_FLAG_INDEX))
        timeouts = int(has_flag(flags, TIMEOUT_REWARD_FLAG_INDEX))
        full = paid - timeouts
        earned = attester_gross * full + attester_half * timeouts
        penalty = attester_half * component_count
        if index == proposer:
            proposer_earned += earned
            proposer_penalty += penalty
        else:
            increase_balance(state, index, earned)
            decrease_balance(state, index, penalty)
        if produced:
            proposer_earned += proposer_gross * full + proposer_half * timeouts
        proposer_penalty += proposer_half * component_count
    increase_balance(state, proposer, proposer_earned)
    decrease_balance(state, proposer, proposer_penalty)
```

#### New `open_fg_duties`

A vote already rewarded for the same target or finality pair carries forward and
earns the first-slot reward again each round. A timeout carries forward at the
timeout rate.

```python
def open_fg_duties(state: BeaconState) -> None:
    finality = state.justified_checkpoint
    if finality.height <= state.finalized_checkpoint.height:
        finality = HeightCheckpoint.empty()
    row = FinalityRewardSlot(
        target=state.target_checkpoint.copy(),
        finality=finality.copy(),
        finalized_epoch=compute_epoch_at_slot(state.finalized_slot),
        reward_per_increment=get_round_base_reward_per_increment(state),
        increments=EffectiveBalanceIncrements(),
        flags=RoundParticipation(),
    )
    for index in get_fg_duty_positions(state, state.slot):
        validator = state.validators[index]
        increments = validator.effective_balance // EFFECTIVE_BALANCE_INCREMENT
        row.increments.append(Uint16(increments))
        flags = state.rewarded_flags[index]
        if state.progress_participation[index]:
            flags = add_flag(flags, ACTIVITY_FLAG_INDEX)
        if finality == HeightCheckpoint.empty():
            flags &= ~add_flag(ParticipationFlags(0), FINALITY_FLAG_INDEX)
        row.flags.append(flags)
    state.reward_history[state.slot % len(state.reward_history)] = row
```

#### Modified `process_inactivity_updates`

Update each assigned validator once its inclusion window has closed. This keeps
score changes in assignment order when several rounds have outstanding duties.

```python
def process_inactivity_updates(state: BeaconState) -> None:
    if state.slot < FG_REWARD_WINDOW:
        return
    voting_slot = state.slot - FG_REWARD_WINDOW
    row = state.reward_history[voting_slot % len(state.reward_history)]
    if len(row.flags) == 0:
        return
    for index, pos in get_fg_duty_positions(state, voting_slot).items():
        flags = row.flags[pos]
        participated = has_flag(flags, PROGRESS_FLAG_INDEX) or has_flag(flags, ACTIVITY_FLAG_INDEX)
        if participated and not state.validators[index].slashed:
            state.inactivity_scores[index] = saturating_sub(
                state.inactivity_scores[index], INACTIVITY_SCORE_RECOVERY_RATE
            )
        else:
            state.inactivity_scores[index] += INACTIVITY_SCORE_BIAS
            if state.inactivity_scores[index] >= EJECTION_INACTIVITY_SCORE:
                initiate_validator_exit(state, index)
```

*Note*: A validator gains `INACTIVITY_SCORE_BIAS` points for each missed height
vote once its inclusion window closes. Its weight falls with the square of its
score. The table below shows the weight of a validator that was fully active and
then stays offline. Weights are shown as a percentage of full weight. The
inactivity score itself affects voting weight. Ordinary missed-duty deductions
also apply. When the weight reaches zero, the validator is force-exited and
keeps its stake.

| Rounds offline | Inactivity score | Voting weight |
| -------------: | ---------------: | ------------: |
|              0 |                0 |       100.00% |
|          1,024 |            4,096 |        99.61% |
|          2,048 |            8,192 |        98.44% |
|          3,072 |           12,288 |        96.48% |
|          4,096 |           16,384 |        93.75% |
|          5,120 |           20,480 |        90.23% |
|          6,144 |           24,576 |        85.94% |
|          7,168 |           28,672 |        80.86% |
|          8,192 |           32,768 |        75.00% |
|          9,216 |           36,864 |        68.36% |
|         10,240 |           40,960 |        60.94% |
|         11,264 |           45,056 |        52.73% |
|         12,288 |           49,152 |        43.75% |
|         13,312 |           53,248 |        33.98% |
|         14,336 |           57,344 |        23.44% |
|         15,360 |           61,440 |        12.11% |
|         16,384 |           65,536 |         0.00% |

### Epoch processing

#### Modified `process_epoch`

```python
def process_epoch(state: BeaconState) -> None:
    # [Modified in EIP8453]
    # Removed `process_justification_and_finalization`
    # [Modified in EIP8453]
    # Removed `process_inactivity_updates`
    # [Modified in EIP8453]
    # Removed `process_rewards_and_penalties`
    process_registry_updates(state)
    process_slashings(state)
    process_pending_deposits(state)
    process_pending_consolidations(state)
    process_builder_pending_payments(state)
    process_effective_balance_updates(state)
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_summaries_update(state)
    # [Modified in EIP8453]
    # Removed `process_participation_flag_updates`
    process_sync_committee_updates(state)
    process_proposer_lookahead(state)
    process_ptc_window(state)
    # [New in EIP8453]
    process_head_vote_committee_window(state)
```

#### Modified `process_builder_pending_payments`

*Note*: The function `process_builder_pending_payments` is rewritten to weigh
payments by the head votes recorded in `head_vote_participation`.

```python
def process_builder_pending_payments(state: BeaconState) -> None:
    """
    Processes the builder pending payments from the previous epoch.
    """
    for index in range(SLOTS_PER_EPOCH):
        payment = state.builder_pending_payments[index]
        if payment.withdrawal.amount == 0:
            continue
        if has_builder_payment_quorum(state.head_vote_participation[index]):
            state.builder_pending_withdrawals.append(payment.withdrawal)

    old_payments = state.builder_pending_payments[SLOTS_PER_EPOCH:]
    state.builder_pending_payments[:SLOTS_PER_EPOCH] = old_payments
    new_payments = [BuilderPendingPayment.empty() for _ in range(SLOTS_PER_EPOCH)]
    state.builder_pending_payments[SLOTS_PER_EPOCH:] = new_payments

    old_participation = state.head_vote_participation[SLOTS_PER_EPOCH:]
    state.head_vote_participation[:SLOTS_PER_EPOCH] = old_participation
    new_participation = [HeadVoteCommitteeBits() for _ in range(SLOTS_PER_EPOCH)]
    state.head_vote_participation[SLOTS_PER_EPOCH:] = new_participation
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

    for deposit in state.pending_deposits:
        # [Modified in EIP8453]
        # Check if deposit has been finalized, otherwise, stop processing.
        if deposit.slot > state.finalized_slot:
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

#### New `process_head_vote_committee_window`

```python
def process_head_vote_committee_window(state: BeaconState) -> None:
    """
    Update the cached head vote committee window.
    """
    current_epoch = get_current_epoch(state)
    committees = list(state.head_vote_committee_window[SLOTS_PER_EPOCH:])
    start_slot = compute_start_slot_at_epoch(current_epoch + MIN_SEED_LOOKAHEAD + 1)
    for slot in range(start_slot, start_slot + SLOTS_PER_EPOCH):
        committees.append(compute_head_vote_committee(state, Slot(slot)))
    state.head_vote_committee_window = HeadVoteCommitteeWindow(data=committees)
```

### Block processing

#### Modified `process_block`

*Note*: The height events of a block are processed once, after all of its
attestations.

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    parent_slot = state.latest_block_header.slot
    process_parent_execution_payload(state, block)
    process_block_header(state, block)
    process_withdrawals(state)
    process_execution_payload_bid(state, block.body.signed_execution_payload_bid)
    process_randao(state, block.body)
    process_operations(state, block.body, parent_slot)
    process_sync_aggregate(state, block.body.sync_aggregate)
    # [New in EIP8453]
    process_height_events(state)
```

#### Operations

##### Modified `process_operations`

```python
def process_operations(
    state: BeaconState,
    body: BeaconBlockBody,
    parent_slot: Slot,
) -> None:
    def for_ops(operations: Sequence[Any], fn: Callable[..., None], *args: Any) -> None:
        for operation in operations:
            fn(state, operation, *args)

    assert len(body.proposer_slashings) <= MAX_PROPOSER_SLASHINGS
    assert len(body.attester_slashings) <= MAX_ATTESTER_SLASHINGS_ELECTRA
    # [New in EIP8453]
    assert len(body.legacy_attester_slashings) <= MAX_ATTESTER_SLASHINGS_ELECTRA
    assert len(body.attestations) <= MAX_ATTESTATIONS_ELECTRA
    assert len(body.voluntary_exits) <= MAX_VOLUNTARY_EXITS
    assert len(body.bls_to_execution_changes) <= MAX_BLS_TO_EXECUTION_CHANGES
    assert len(body.payload_attestations) <= MAX_PAYLOAD_ATTESTATIONS
    # [New in EIP8453]
    assert len(body.head_votes) <= MAX_HEAD_VOTES
    # [New in EIP8453]
    assert len(body.head_vote_support) == len(body.head_votes)

    for_ops(body.proposer_slashings, process_proposer_slashing)
    for_ops(body.attester_slashings, process_attester_slashing)
    # [New in EIP8453]
    for_ops(body.legacy_attester_slashings, process_legacy_attester_slashing)
    # [Modified in EIP8453]
    for_ops(body.attestations, process_attestation)
    for_ops(body.voluntary_exits, process_voluntary_exit)
    for_ops(body.bls_to_execution_changes, process_bls_to_execution_change)
    for_ops(body.payload_attestations, process_payload_attestation)
    # [New in EIP8453]
    for vote_index in range(len(body.head_votes)):
        process_head_vote(state, body.head_votes[vote_index], body.head_vote_support[vote_index])
    process_head_vote_rewards(state, body.head_votes, parent_slot)
```

##### Legacy attester slashings

###### New `process_legacy_attester_slashing`

```python
def process_legacy_attester_slashing(
    state: BeaconState, attester_slashing: heze.AttesterSlashing
) -> None:
    attestation_1 = attester_slashing.attestation_1
    attestation_2 = attester_slashing.attestation_2
    assert is_slashable_legacy_attestation_data(attestation_1.data, attestation_2.data)
    assert is_valid_legacy_indexed_attestation(state, attestation_1)
    assert is_valid_legacy_indexed_attestation(state, attestation_2)

    slashed_any = False
    indices = set(attestation_1.attesting_indices).intersection(attestation_2.attesting_indices)
    for index in sorted(indices):
        if is_slashable_validator(state.validators[index], get_current_epoch(state)):
            slash_validator(state, index)
            slashed_any = True
    assert slashed_any
```

##### Attestations

###### Modified `process_attestation`

An attestation is live when its committee epoch is not older than the finalized
epoch and its data names the current target, or is a vote below the current
height whose finality pair is pending. Any other attestation is valid only if it
earns a reward or records activity for a duty in the reward window. A duty
accepts committee epochs from the finalized epoch recorded at its assignment.
Clients can check for a matching duty before looking up the committees.

A timeout earns the lower progress reward. A finality pair in the same
attestation still earns its full reward at that delay.

```python
def process_attestation(state: BeaconState, attestation: Attestation) -> None:
    data = attestation.data
    epoch = attestation.epoch
    assert is_well_formed_attestation_data(data)
    assert EIP8453_FORK_EPOCH <= epoch <= get_current_epoch(state)
    live = epoch >= compute_epoch_at_slot(state.finalized_slot) and is_valid_attestation_data(
        state, data
    )
    if not live:
        assert (
            data.target == state.target_checkpoint
            or data.target.height < state.target_checkpoint.height
        )
    assert is_valid_aggregation_bits(state, epoch, attestation)
    indexed = get_indexed_attestation(state, attestation)
    assert is_valid_indexed_attestation(state, indexed)

    recorded = process_fg_rewards(state, data, indexed.attesting_indices, epoch)
    assert live or recorded
    if not live:
        return
    for index in indexed.attesting_indices:
        for pending in state.pending_finality:
            if pending.checkpoint == data.finality and not pending.participation[index]:
                pending.participation[index] = Boolean(True)
        if data.target == state.target_checkpoint:
            state.progress_participation[index] = Boolean(True)
            if not data.timeout:
                state.target_participation[index] = Boolean(True)
```

##### Head votes

###### New `process_head_vote`

*Note*: Head votes belong to the available chain. Votes for the block of their
slot also count toward builder payments throughout the inclusion window.

```python
def process_head_vote(
    state: BeaconState, vote: HeadVote, support_bits: HeadVoteSupportBits
) -> None:
    data = vote.data
    assert data.slot + MIN_ATTESTATION_INCLUSION_DELAY <= state.slot
    assert compute_epoch_at_slot(data.slot) in (get_previous_epoch(state), get_current_epoch(state))
    assert data.payload_status in (
        PAYLOAD_STATUS_EMPTY,
        PAYLOAD_STATUS_FULL,
        PAYLOAD_STATUS_PENDING,
    )
    if is_head_vote_same_slot(state, data):
        assert data.payload_status == PAYLOAD_STATUS_PENDING

    committee = get_head_vote_committee(state, data.slot)
    assert len(vote.voter_indices) > 0
    assert list(vote.voter_indices) == sorted(set(vote.voter_indices))
    for index in vote.voter_indices:
        assert index in committee

    assert len(support_bits) == len(vote.voter_indices)
    for is_supported in support_bits:
        if is_supported:
            assert data.slot == state.slot - 1

    # Verify signature
    pubkeys = [state.validators[index].pubkey for index in vote.voter_indices]
    domain = get_domain(state, DOMAIN_HEAD_VOTE, compute_epoch_at_slot(data.slot))
    signing_root = compute_signing_root(data, domain)
    assert bls.FastAggregateVerify(pubkeys, signing_root, vote.signature)

    # Record the seats that voted for the block of their slot
    if is_head_vote_same_slot(state, data):
        if compute_epoch_at_slot(data.slot) == get_current_epoch(state):
            participation_index = SLOTS_PER_EPOCH + data.slot % SLOTS_PER_EPOCH
        else:
            participation_index = data.slot % SLOTS_PER_EPOCH
        for position, index in enumerate(committee):
            if index in vote.voter_indices:
                state.head_vote_participation[participation_index][position] = Boolean(True)
```

###### New `process_head_vote_rewards`

Only head votes from the previous slot earn rewards. An attester whose votes in
the block disagree on the head or payload status earns nothing, while the
proposer still earns one inclusion reward for each seat that attester holds. A
validator with several committee seats earns once per seat.

```python
def process_head_vote_rewards(state: BeaconState, head_votes: HeadVotes, parent_slot: Slot) -> None:
    timely_votes = [vote for vote in head_votes if vote.data.slot + 1 == state.slot]
    if len(timely_votes) == 0:
        return

    vote_slot = state.slot - 1
    correct_root = get_block_root_at_slot(state, vote_slot)
    if parent_slot == vote_slot:
        correct_status = PAYLOAD_STATUS_PENDING
    elif state.execution_payload_availability[parent_slot % SLOTS_PER_HISTORICAL_ROOT]:
        correct_status = PAYLOAD_STATUS_FULL
    else:
        correct_status = PAYLOAD_STATUS_EMPTY
    correct_indices: set[ValidatorIndex] = set()
    other_indices: set[ValidatorIndex] = set()
    for vote in timely_votes:
        if (
            vote.data.beacon_block_root == correct_root
            and vote.data.payload_status == correct_status
        ):
            correct_indices.update(vote.voter_indices)
        else:
            other_indices.update(vote.voter_indices)
    included_indices = correct_indices | other_indices
    rewarded_indices = correct_indices - other_indices

    active_increments = get_total_active_balance(state) // EFFECTIVE_BALANCE_INCREMENT
    total_base_rewards = get_round_base_reward_per_increment(state) * active_increments
    divisor = WEIGHT_DENOMINATOR * Uint64(SLOTS_PER_ROUND) * HEAD_VOTE_COMMITTEE_SIZE
    reward = total_base_rewards * HEAD_VOTE_WEIGHT // divisor

    committee = get_head_vote_committee(state, vote_slot)
    for index in committee:
        if index in rewarded_indices and not state.validators[index].slashed:
            increase_balance(state, index, reward)
    included_seats = sum(1 for index in committee if index in included_indices)
    increase_balance(state, get_beacon_proposer_index(state), reward * included_seats)
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
                participation=HeightParticipation(data=[Boolean(False)] * len(state.validators)),
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
    if state.target_checkpoint == state.justified_checkpoint:
        state.rewarded_flags = RoundParticipation(
            data=[ParticipationFlags(0)] * len(state.validators)
        )
    else:
        finality_flag = add_flag(ParticipationFlags(0), FINALITY_FLAG_INDEX)
        state.rewarded_flags = RoundParticipation(
            data=[flags & finality_flag for flags in state.rewarded_flags]
        )
    state.target_checkpoint = HeightCheckpoint(
        height=state.target_checkpoint.height + 1,
        # Filled in by the next ``process_slot``
        root=Root(),
    )
    state.target_slot = state.latest_block_header.slot
    state.target_participation = HeightParticipation(data=[Boolean(False)] * len(state.validators))
    state.progress_participation = HeightParticipation(
        data=[Boolean(False)] * len(state.validators)
    )
```
