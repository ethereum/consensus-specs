# Decoupled Consensus -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Helpers](#helpers)
  - [New `FinalitySigningRecord`](#new-finalitysigningrecord)
- [Validator assignments](#validator-assignments)
  - [Voting committees](#voting-committees)
  - [Lookahead](#lookahead)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block and sidecar proposal](#block-and-sidecar-proposal)
    - [Preparing for a `BeaconBlock`](#preparing-for-a-beaconblock)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [Head votes](#head-votes)
      - [Attestations](#attestations)
      - [Attester slashings](#attester-slashings)
  - [Head voting](#head-voting)
    - [Head vote data](#head-vote-data)
    - [Construct head vote](#construct-head-vote)
    - [Broadcast head vote](#broadcast-head-vote)
  - [Attesting](#attesting)
    - [Attestation data](#attestation-data)
      - [Finality pair](#finality-pair)
      - [Height pair](#height-pair)
      - [Construct data](#construct-data)
      - [Record attestation](#record-attestation)
    - [Construct attestation](#construct-attestation)
    - [Broadcast attestation](#broadcast-attestation)
  - [Attestation aggregation](#attestation-aggregation)
    - [Aggregation selection](#aggregation-selection)
    - [Construct aggregate](#construct-aggregate)
      - [Head votes](#head-votes-1)
      - [FG attestations](#fg-attestations)
      - [Aggregation bits](#aggregation-bits)
    - [Broadcast aggregate](#broadcast-aggregate)
- [How to avoid slashing](#how-to-avoid-slashing)
  - [Attester slashing](#attester-slashing)
- [Protection best practices](#protection-best-practices)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
validator" to implement decoupled consensus (DC).

DC replaces the combined LMD-GHOST and Casper FFG attestation with separate
head votes for the available chain (AC) and attestations for the finality gadget
(FG). Validators are assigned to voting committees once per round.

## Prerequisites

This document is an extension of the
[Heze -- Honest Validator](../../heze/validator.md) guide. All behaviors and
definitions in that document, and documents it extends, carry over unless
explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in
[Decoupled Consensus -- The Beacon Chain](./beacon-chain.md) are requisite for
this document and used throughout.

*TODO*: Specify the DC fork-choice interfaces and duty deadlines referenced
below.

## Helpers

### New `FinalitySigningRecord`

The `FinalitySigningRecord` tracks a validator's FG signing history. A separate
record is maintained for each validator key, independently of whether its
attestations are included on chain.

```python
@dataclass
class FinalitySigningRecord:
    targets: dict[Height, Root]
    timeouts: set[Height]
    finality_locks: dict[Height, Root]
    entries: dict[Height, set[Root]]
```

The fields are initialized empty for a validator with no prior DC signing
history:

- `targets[h]`: the first target voted for at height `h`.
- `timeouts`: heights at which a timeout was signed.
- `finality_locks[h]`: the block named by a finality vote at height `h`.
- `entries[h]`: entries named by any height vote at height `h`.

*Note*: The record persists across restarts. Finality signing locks do not
expire and are distinct from the temporary AC locks maintained by fork choice.

## Validator assignments

### Voting committees

To determine its voting committee assignment, a validator calls
`get_voting_committee_assignment(state, attestation_round, validator_index)`.
The returned committee index and slot apply to both head voting and FG
attestation.

```python
def get_voting_committee_assignment(
    state: BeaconState, attestation_round: Round, validator_index: ValidatorIndex
) -> tuple[CommitteeIndex, Slot] | None:
    """
    Return the validator's voting committee index and assigned slot, if any.
    """
    for index in range(COMMITTEES_PER_ROUND):
        committee_index = CommitteeIndex(index)
        if validator_index in get_voting_committee(state, attestation_round, committee_index):
            return committee_index, compute_voting_committee_slot(attestation_round, committee_index)
    return None
```

A validator has at most one voting assignment per round. Validators excluded by
the committee-size cap have no assignment for that round. Round numbering is
defined by `compute_round_at_slot` and does not restart at the DC fork.

### Lookahead

Assignments are computed from the chain state using `get_voting_committee`.
A validator should recompute its assignment when the dependent chain state
changes.

*TODO*: Specify assignment lookahead and the dependent root in the DC
fork-choice and networking specifications.

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below.

### Block and sidecar proposal

A validator is expected to propose a `SignedBeaconBlock` at the beginning of
any slot during which `is_proposer(state, validator_index)` returns `True`.

#### Preparing for a `BeaconBlock`

Let `parent` be the block returned by the AC proposal procedure, together with
its previous slot head-vote view.

*TODO*: Specify the DC proposal helper, including full or empty execution
payload selection and inclusion-list checks.

#### Constructing the `BeaconBlockBody`

*Note*: In this section, `state` is the parent state processed through any empty
slots up to the proposal slot using `process_slots`, before applying the block.

##### Head votes

Set `block.body.head_votes` to aggregates from the AC proposal view, up to
`MAX_HEAD_VOTES`. Each aggregate must satisfy the verification conditions in
[`process_head_vote`](./beacon-chain.md#new-process_head_vote), including the
requirement that its vote slot is `block.slot - 1`.

Set `block.body.head_vote_support_bits` to a `HeadVoteSupportBits` with one bit
per included aggregate, in the same order. Set bit `i` if the block named by
`block.body.head_votes[i].data.beacon_block_root` is in the accepted tree at
proposal time and its slot is no later than the vote's slot. Otherwise, clear
bit `i`.

*Note*: A vote for an unknown block may be included with its support bit cleared.

*TODO*: Specify aggregate selection when the proposal view exceeds
`MAX_HEAD_VOTES`, preserving the requirements of view merge.

##### Attestations

Set `block.body.attestations` to aggregates selected from the FG attestation
pool, up to `MAX_ATTESTATIONS_ELECTRA`. Each aggregate must satisfy the
verification conditions in
[`process_attestation`](./beacon-chain.md#modified-process_attestation),
including its round, committee encoding and signature.

A proposer should prefer aggregates that add target, progress or
pending-finality participation. An attestation for a previous height can still
contribute to a retained finality pair.

##### Attester slashings

Set `block.body.attester_slashings` to valid DC attester slashing evidence and
`block.body.legacy_attester_slashings` to valid pre-DC evidence. Each list may
contain up to `MAX_ATTESTER_SLASHINGS_ELECTRA` items.

The evidence must satisfy `process_attester_slashing` or
`process_legacy_attester_slashing`, respectively, against the state at its
position in block processing.

### Head voting

A validator assigned to vote during `slot` creates, signs and broadcasts a
`HeadVoteMessage` for that slot.

*Note*: In the Goldilocks schedule, head voting occurs one quarter of the way
through the slot, after unlocking against the previous slot's votes. The
validator must satisfy the fork choice's observation requirement after waking up.

*TODO*: Specify the DC head-vote deadline and voting helper.

#### Head vote data

First, the validator constructs `head_vote_data`, a
[`HeadVoteData`](./beacon-chain.md#new-headvotedata) object:

- Let `head` be the head selected by the AC voting procedure for `slot`.
- Set `head_vote_data.slot = slot`.
- Set `head_vote_data.beacon_block_root = hash_tree_root(head)`.

The AC voting procedure applies view merge, AC locks and FG restrictions using
its voting view.

#### Construct head vote

The validator creates `head_vote_message` as a
[`HeadVoteMessage`](./beacon-chain.md#new-headvotemessage):

- Set `head_vote_message.validator_index = validator_index`.
- Set `head_vote_message.data = head_vote_data`.
- Set `head_vote_message.signature` to
  `get_head_vote_signature(state, head_vote_data, privkey)`.

```python
def get_head_vote_signature(
    state: BeaconState, data: HeadVoteData, privkey: int
) -> BLSSignature:
    domain = get_domain(state, DOMAIN_HEAD_VOTE, compute_epoch_at_slot(data.slot))
    signing_root = compute_signing_root(data, domain)
    return bls.Sign(privkey, signing_root)
```

The validator must record the selected root before signing and must not sign
another head for the same slot.

#### Broadcast head vote

The validator broadcasts `head_vote_message` and processes it locally.

*TODO*: Specify the head-vote gossip topic and subnet assignment.

### Attesting

A validator assigned to vote during `slot` attempts to create an FG attestation
using the rules below. It sends no new attestation if there is no FG source or
if its signing history suppresses the vote.

*TODO*: Specify the FG attestation deadline and source observation for each
assigned slot and staggered committee schedule.

#### Attestation data

First, obtain `source` and `head` from the same AC-to-FG observation. The source
is the deepest block in the viable tree passing the fast test in the applicable
confirmation update. If no such block exists, the validator does not attest.

Let `source_state` and `head_state` be the states after processing `source` and
`head`, respectively:

- Let `target` be a copy of `source_state.target_checkpoint`.
- Let `justified = head_state.justified_checkpoint`.
- Let `finalized_height = head_state.finalized_checkpoint.height`.

If `target.root == Root()` because `source` advanced the height, set
`target.root = hash_tree_root(source)`.

*Note*: The height vote comes from the source state. The finality pair comes
from the head state.

##### Finality pair

The validator selects the finality pair using `get_finality_vote`:

```python
def get_finality_vote(
    record: FinalitySigningRecord,
    justified: HeightCheckpoint,
    finalized_height: Height,
) -> HeightCheckpoint:
    height, root = justified.height, justified.root
    if height <= finalized_height:
        return HeightCheckpoint.empty()
    if record.targets.get(height) not in (None, root):
        return HeightCheckpoint.empty()
    if height in record.timeouts:
        return HeightCheckpoint.empty()
    if record.finality_locks.get(height) not in (None, root):
        return HeightCheckpoint.empty()
    return justified.copy()
```

##### Height pair

The validator selects the height pair using `get_height_vote`:

```python
def get_height_vote(
    record: FinalitySigningRecord,
    target: HeightCheckpoint,
    finality: HeightCheckpoint,
) -> tuple[HeightCheckpoint, bool] | None:
    height, root = target.height, target.root
    if height == 0 or root == Root():
        return None

    lock = record.finality_locks.get(height)
    if finality != HeightCheckpoint.empty() and finality.height == height:
        lock = finality.root

    if height in record.timeouts:
        return target.copy(), True
    if lock is not None:
        if lock == root:
            return target.copy(), False
        return None
    if record.targets.get(height) in (None, root):
        return target.copy(), False
    return target.copy(), True
```

*Note*: The candidate finality pair constrains the height vote before it is
removed, if necessary, by `get_finality_attestation_data` below.

##### Construct data

Set `attestation_data` to
`get_finality_attestation_data(record, target, justified, finalized_height)`.
If it returns `None`, the validator sends no new attestation.

*Note*: The duplicate-vote checks suppress the entire attestation, including
any new finality pair.

```python
def get_finality_attestation_data(
    record: FinalitySigningRecord,
    target: HeightCheckpoint,
    justified: HeightCheckpoint,
    finalized_height: Height,
) -> AttestationData | None:
    finality = get_finality_vote(record, justified, finalized_height)
    vote = get_height_vote(record, target, finality)
    if vote is None:
        return None
    target, timeout = vote

    entries = record.entries.get(target.height, set())
    if (not timeout and len(entries) > 0) or target.root in entries:
        return None

    if finality != HeightCheckpoint.empty() and target.height <= finality.height:
        finality = HeightCheckpoint.empty()

    return AttestationData(target=target, timeout=Boolean(timeout), finality=finality)
```

##### Record attestation

Before signing, the validator records the selected `attestation_data`:

```python
def record_finality_attestation(
    record: FinalitySigningRecord, data: AttestationData
) -> None:
    height, root = data.target.height, data.target.root
    record.entries.setdefault(height, set()).add(root)
    if data.finality != HeightCheckpoint.empty():
        record.finality_locks[data.finality.height] = data.finality.root
    if data.timeout:
        record.timeouts.add(height)
    else:
        record.targets.setdefault(height, root)
```

Selecting and recording the data must be serialized per validator key. The
record and selected data must be persisted before signing. See
[Protection best practices](#protection-best-practices) for interrupted duties.

#### Construct attestation

The validator creates `attestation` as a
[`SingleAttestation`](./beacon-chain.md#modified-singleattestation) with the
following fields:

- Set `attestation.committee_index` to the assigned committee index.
- Set `attestation.attester_index = validator_index`.
- Set `attestation.round` to the assigned round.
- Set `attestation.data = attestation_data`.
- Set `attestation.signature` to
  `get_attestation_signature(state, attestation_data, privkey)`.

*Note*: Here `state` is the duty's chain state advanced to the current slot,
rather than the historical source state. This matches the signature domain used
by `is_valid_indexed_attestation`.

```python
def get_attestation_signature(
    state: BeaconState, attestation_data: AttestationData, privkey: int
) -> BLSSignature:
    # [Modified in DC]
    domain = get_domain(state, DOMAIN_BEACON_ATTESTER)
    signing_root = compute_signing_root(attestation_data, domain)
    return bls.Sign(privkey, signing_root)
```

The signature covers `attestation.data`; it does not cover `attestation.round`
or `attestation.committee_index`.

*TODO*: Specify domain handling for delayed FG signatures across a fork-version
change.

#### Broadcast attestation

The validator broadcasts `attestation` and processes it locally.

*TODO*: Specify the FG attestation gossip topic and subnet assignment.

### Attestation aggregation

Validators aggregate head votes and FG attestations separately. The messages
passed to the helpers below must have valid signatures under the same domain
and valid committee assignments for `state`.

*Note*: The helpers aggregate individual messages. Aggregates with overlapping
signers cannot be combined by adding their signatures.

#### Aggregation selection

*TODO*: Specify aggregator selection and selection proofs for both message
types. The legacy aggregation helpers require adaptation to DC committees.

#### Construct aggregate

##### Head votes

Construct `aggregate_vote` using `get_aggregate_head_vote` with head vote
messages for the same slot and block root:

```python
def get_aggregate_head_vote(
    state: BeaconState, messages: Sequence[HeadVoteMessage]
) -> HeadVote:
    """
    Aggregate head vote messages with identical data and distinct signers.
    """
    assert len(messages) > 0
    data = messages[0].data
    assert all(message.data == data for message in messages)
    participants = {message.validator_index for message in messages}
    assert len(participants) == len(messages)

    attestation_round = compute_round_at_slot(data.slot)
    committee_bits = CommitteeBits()
    for index in range(COMMITTEES_PER_ROUND):
        committee_index = CommitteeIndex(index)
        if compute_voting_committee_slot(attestation_round, committee_index) != data.slot:
            continue
        committee = get_voting_committee(state, attestation_round, committee_index)
        committee_bits[index] = any(validator_index in participants for validator_index in committee)

    aggregation_bits = get_vote_aggregation_bits(
        state, attestation_round, committee_bits, participants
    )
    return HeadVote(
        aggregation_bits=aggregation_bits,
        data=data,
        signature=bls.Aggregate([message.signature for message in messages]),
        committee_bits=committee_bits,
    )
```

##### FG attestations

Construct `aggregate_attestation` using `get_aggregate_attestation` with
individual attestations for the same data and round:

```python
def get_aggregate_attestation(
    state: BeaconState, attestations: Sequence[SingleAttestation]
) -> Attestation:
    """
    Aggregate attestations with identical data and round, and distinct signers.
    """
    assert len(attestations) > 0
    data = attestations[0].data
    attestation_round = attestations[0].round
    assert all(a.data == data and a.round == attestation_round for a in attestations)
    participants = {a.attester_index for a in attestations}
    assert len(participants) == len(attestations)

    committee_bits = CommitteeBits()
    for attestation in attestations:
        assert attestation.committee_index < COMMITTEES_PER_ROUND
        committee_bits[attestation.committee_index] = True

    aggregation_bits = get_vote_aggregation_bits(
        state, attestation_round, committee_bits, participants
    )
    return Attestation(
        aggregation_bits=aggregation_bits,
        data=data,
        signature=bls.Aggregate([a.signature for a in attestations]),
        committee_bits=committee_bits,
        round=attestation_round,
    )
```

##### Aggregation bits

`get_vote_aggregation_bits` encodes signers in committee-index order, matching
`get_aggregate_participants` in the beacon-chain specification. The size bound
applies to all members of the represented committees, not only the signers.
Split messages into separate aggregates when the bound would be exceeded.

```python
def get_vote_aggregation_bits(
    state: BeaconState,
    attestation_round: Round,
    committee_bits: CommitteeBits,
    participants: set[ValidatorIndex],
) -> AggregationBits:
    """
    Encode participants in the concatenation of the selected voting committees.
    """
    aggregation_bits = AggregationBits()
    represented_participants: set[ValidatorIndex] = set()
    for committee_index in get_committee_indices(committee_bits):
        committee = get_voting_committee(state, attestation_round, committee_index)
        assert len(aggregation_bits) + len(committee) <= MAX_VALIDATORS_PER_AGGREGATE
        for validator_index in committee:
            is_participant = validator_index in participants
            aggregation_bits.append(is_participant)
            if is_participant:
                represented_participants.add(validator_index)
    assert represented_participants == participants
    return aggregation_bits
```

#### Broadcast aggregate

The validator broadcasts the aggregate for block inclusion.

*TODO*: Specify aggregate gossip messages, selection-proof wrappers and
broadcast deadlines.

*Note*: An FG aggregate's round must be between
`compute_round_at_slot(state.finalized_slot)` and `get_current_round(state)`,
inclusive, when included in a block. Its data must also remain valid against
the inclusion state. Forwarding an aggregate preserves its original round:
changing the round changes the committee encoding, even though the round is
not signed.
