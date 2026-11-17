# PQ -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Containers](#containers)
- [Helpers](#helpers)
  - [New `FinalitySigningRecord`](#new-finalitysigningrecord)
- [Becoming a validator](#becoming-a-validator)
  - [Initialization](#initialization)
    - [VRF tree](#vrf-tree)
    - [XMSS public key](#xmss-public-key)
  - [Preregister](#preregister)
  - [Submit deposit](#submit-deposit)
- [Validator assignments](#validator-assignments)
  - [Attestation committees](#attestation-committees)
  - [Head vote committees](#head-vote-committees)
  - [Lookahead](#lookahead)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block and sidecar proposal](#block-and-sidecar-proposal)
    - [Broadcasting `SignedProposerPreferences`](#broadcasting-signedproposerpreferences)
    - [Preparing for a `BeaconBlock`](#preparing-for-a-beaconblock)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [Randao reveal](#randao-reveal)
      - [Head votes](#head-votes)
      - [Attestations](#attestations)
      - [Attester slashings](#attester-slashings)
      - [Proof](#proof)
      - [Voluntary exits](#voluntary-exits)
      - [Sync committee](#sync-committee)
      - [BLS to execution changes](#bls-to-execution-changes)
      - [Payload attestations](#payload-attestations)
      - [Signed execution payload bid](#signed-execution-payload-bid)
      - [Execution requests](#execution-requests)
    - [Packaging into a `SignedBeaconBlock`](#packaging-into-a-signedbeaconblock)
      - [State root](#state-root)
      - [Signature](#signature)
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
  - [Sync committees](#sync-committees)
  - [Payload timeliness attestation](#payload-timeliness-attestation)
    - [Constructing the `PayloadAttestationMessage`](#constructing-the-payloadattestationmessage)
- [Protection best practices](#protection-best-practices)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
validator" to implement PQ.

Validators sign with leanXMSS instead of BLS. Every message is signed at the
leaf that `compute_xmss_leaf_index` assigns to its slot and type, except an
attestation, which is signed at the leaf that
`compute_xmss_attestation_leaf_index` assigns to its round, and a message
without a leaf of its own, such as a voluntary exit, which is signed at a
reserved leaf, see [Protection best practices](#protection-best-practices). At
the upgrade, each validator that registered an XMSS public key with EIP-8483
takes it in place of its BLS public key. A validator without a registration is
exited at the upgrade and becomes withdrawable
`UNREGISTERED_VALIDATOR_WITHDRAWABILITY_DELAY` epochs later. Its balance is then
withdrawn, unless it has `0x00` withdrawal credentials, in which case its
balance stays locked. See [the fork document](./fork.md) for details.

PQ replaces the combined LMD-GHOST and Casper FFG attestation with separate head
votes for the available chain (AC) and attestations for the finality gadget
(FG). Each epoch, every active validator sits on one attestation committee and,
in every round, casts its FG attestation in that committee's slot. In every
slot, a head vote committee casts head votes.

*TODO*: Specify the fork-choice interfaces and duty deadlines referenced below.

## Containers

*TODO*: Specify the containers that carry an aggregate and the proof of its
signatures on the wire. `AggregateAndProof` and `SignedAggregateAndProof` are
deprecated, and the leaf offset `LEAF_OFFSET_AGGREGATE_AND_PROOF` stays reserved
for their replacement.

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

The fields are initialized empty for a validator with no prior FG signing
history:

- `targets[h]`: the first target voted for at height `h`.
- `timeouts`: heights at which a timeout was signed.
- `finality_locks[h]`: the block named by a finality vote at height `h`.
- `entries[h]`: entries named by any height vote at height `h`.

*Note*: The record persists across restarts. Finality signing locks do not
expire and are distinct from the temporary AC locks maintained by fork choice.

## Becoming a validator

### Initialization

#### VRF tree

A validator builds a Merkle tree of depth `VRF_TREE_DEPTH` whose leaves are
secret random values, one for each slot, and registers the root of the tree as
its VRF root with EIP-8483, as the last 32 bytes of the registration's
`pq_data`. Its VRF proof for a slot is the leaf at index `slot`, followed by the
leaf's Merkle branch. It reveals the proof as its RANDAO reveal when it
proposes. The tree is fixed at registration, so a validator cannot grind its
proofs, and nobody can predict them before they are revealed.

#### XMSS public key

A validator's XMSS private key, `privkey`, is a 32-byte seed from which its
leanXMSS key is derived. It must be securely generated along with the resultant
XMSS public key. This `privkey` must be "hot", that is, constantly available to
sign data throughout the lifetime of the validator.

The XMSS public key is registered with EIP-8483 before the upgrade, as the first
32 bytes of the registration's `pq_data`. The remaining 32 bytes are the
validator's VRF root.

*Note*: A validator that joins after the upgrade provides its XMSS public key
and VRF root in its deposit instead, see [Submit deposit](#submit-deposit).

### Preregister

A deposit carries no signature, so anyone who sees the first deposit for a new
XMSS public key before it is included could get in first with a deposit of their
own withdrawal credentials and VRF root. To prevent this, a validator first
preregisters, binding its XMSS public key to its withdrawal credentials and VRF
root. It signs the binding at a reserved leaf and submits it with the signature
to the system contract, which verifies the signature and emits a
`ValidatorPreregistrationRequest` without it.

The validator waits until its binding is in `state.validator_preregistrations`,
then submits its deposit before the binding's `expiry_slot`. If the binding is
not stored, a deposit for the key may already be pending, so the validator
generates a new key and preregisters that one instead.

To renew an expired binding, the validator resubmits the same request. To change
its binding, it generates a new key, since anyone can resubmit the old binding
once it expires.

### Submit deposit

After the upgrade, a deposit carries no signature. Its `pubkey` is
`XMSS_DEPOSIT_PREFIX`, 16 zero bytes, followed by the validator's XMSS public
key, and its `signature` holds the validator's VRF root followed by 64 zero
bytes. A deposit whose XMSS public key is already in `state.validators` tops up
that validator. While the key has an active validator preregistration, a deposit
for it is discarded unless its withdrawal credentials and VRF root match the
binding.

*Note*: A deposit whose `pubkey` does not start with 16 zero bytes is treated as
a legacy deposit, so the validator it creates is exited at once.

## Validator assignments

### Attestation committees

To determine its attestation committee for `epoch`, a validator calls
`get_attestation_committee_assignment(state, epoch, validator_index)`.

```python
def get_attestation_committee_assignment(
    state: BeaconState, epoch: Epoch, validator_index: ValidatorIndex
) -> CommitteeIndex | None:
    """
    Return the index of the validator's attestation committee in ``epoch``, if
    any.
    """
    for index in range(ATTESTATION_COMMITTEES_PER_ROUND):
        committee_index = CommitteeIndex(index)
        if validator_index in get_attestation_committee(state, epoch, committee_index):
            return committee_index
    return None
```

Every active validator sits on exactly one attestation committee per epoch. In
each round, it attests in the slot
`compute_attestation_committee_slot(round, committee_index)`, using the
committee of that slot's epoch. Round numbering is defined by
`compute_round_at_slot` and does not restart at the PQ fork.

### Head vote committees

To determine the slots in which it casts head votes, a validator calls
`get_head_vote_committee_assignments(state, epoch, validator_index)`.

```python
def get_head_vote_committee_assignments(
    state: BeaconState, epoch: Epoch, validator_index: ValidatorIndex
) -> Sequence[Slot]:
    """
    Return the slots of ``epoch`` in which the validator sits on the head vote
    committee.
    """
    assert epoch <= get_current_epoch(state) + 1

    slots: list[Slot] = []
    start_slot = compute_start_slot_at_epoch(epoch)
    for slot in range(start_slot, start_slot + SLOTS_PER_EPOCH):
        if validator_index in get_head_vote_committee(state, Slot(slot)):
            slots.append(Slot(slot))
    return slots
```

A validator can sit on the head vote committee in several slots of an epoch, or
in none. It casts one head vote per assigned slot, even if it holds several
seats in that slot's committee.

### Lookahead

Assignments are computed from the chain state using `get_attestation_committee`
and `get_head_vote_committee`. A validator should recompute its assignment when
the dependent chain state changes.

*TODO*: Specify assignment lookahead and the dependent root in the PQ
fork-choice and networking specifications.

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below.

### Block and sidecar proposal

#### Broadcasting `SignedProposerPreferences`

*Note*: Preferences for a proposal slot are always signed at the same leaf. A
validator MUST NOT sign two different preferences for the same proposal slot,
even if the dependent root changes.

```python
def get_signed_proposer_preferences(
    store: Store,
    state: BeaconState,
    head_root: Root,
    proposal_slot: Slot,
    validator_index: ValidatorIndex,
    fee_recipient: ExecutionAddress,
    target_gas_limit: Uint64,
    # [Modified in PQ]
    privkey: Bytes32,
) -> SignedProposerPreferences:
    proposal_epoch = compute_epoch_at_slot(proposal_slot)
    dependent_root = get_shuffling_dependent_root(store, head_root, proposal_epoch)
    preferences = ProposerPreferences(
        dependent_root=dependent_root,
        proposal_slot=proposal_slot,
        validator_index=validator_index,
        fee_recipient=fee_recipient,
        target_gas_limit=target_gas_limit,
    )
    domain = compute_domain(
        DOMAIN_PROPOSER_PREFERENCES,
        compute_fork_version(proposal_epoch),
        state.genesis_validators_root,
    )
    signing_root = compute_signing_root(preferences, domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(proposal_slot, LEAF_OFFSET_PROPOSER_PREFERENCES)
    signature = xmss.Sign(privkey, leaf_index, signing_root)
    return SignedProposerPreferences(message=preferences, signature=signature)
```

#### Preparing for a `BeaconBlock`

Let `parent` be the block returned by the AC proposal procedure, together with
its previous slot head-vote view.

*TODO*: Specify the PQ proposal helper, including full or empty execution
payload selection.

#### Constructing the `BeaconBlockBody`

##### Randao reveal

Set `block.body.randao_reveal` to the proposer's VRF proof for `block.slot`, the
leaf at index `block.slot` of its VRF tree followed by the leaf's Merkle branch.
`get_epoch_signature` is deprecated.

##### Head votes

Set `block.body.head_votes` to aggregates from the AC proposal view, up to
`MAX_HEAD_VOTES`. Each aggregate must satisfy the verification conditions in
[`process_head_vote`](./beacon-chain.md#new-process_head_vote). Votes of
`block.slot - 1` come first. The remaining space may hold votes of earlier slots
in the previous and current epochs that add seats for the block of their slot,
since these weigh builder payments.

Set `block.body.head_vote_support` to one `HeadVoteSupportBits` per included
aggregate, in the same order, with one bit per voter in that aggregate, in the
order of its `voter_indices`. Set a voter's bit if the proposer counted that
voter's vote as support in its previous slot head-vote view. A counted vote must
be of slot `block.slot - 1`, for a block in the accepted tree at proposal time
whose slot is no later than the vote's slot. Otherwise, clear the bit.

*Note*: A vote for an unknown block may be included with its support bits
cleared.

*TODO*: Specify aggregate selection when the proposal view exceeds
`MAX_HEAD_VOTES`, preserving the requirements of view merge.

##### Attestations

Set `block.body.attestations` to aggregates selected from the FG attestation
pool, up to `MAX_ATTESTATIONS_PQ`. Each aggregate must satisfy the verification
conditions in
[`process_attestation`](./beacon-chain.md#modified-process_attestation),
including its round and committee encoding. `compute_on_chain_aggregate` is
deprecated.

A proposer should prefer aggregates that add target, progress or
pending-finality participation. An attestation for a previous height can still
contribute to a retained finality pair.

##### Attester slashings

Set `block.body.attester_slashings` to valid attester slashing evidence, up to
`MAX_ATTESTER_SLASHINGS_ELECTRA` items.

The evidence must satisfy `process_attester_slashing` against the state at its
position in block processing.

##### Proof

The proposer sets `body.proof` to `stark.MergeProofs(proofs)`, where `proofs`
holds the proofs of the aggregates behind `body.attestations`, ordered as the
attestations are and, within each, by committee index, followed by the proofs of
the aggregates behind `body.head_votes`, ordered as the head votes are. The
merged proof then proves the statements that `process_stark` checks.

##### Voluntary exits

The block body no longer has `voluntary_exits`. To exit, a validator signs its
exit at a reserved leaf and submits it with the signature to the system
contract, which verifies the signature and emits a `VoluntaryExitRequest`
without it. Anyone can submit a signed exit, not only the validator's withdrawal
address.

##### Sync committee

Sync committees are removed in PQ, so the block body no longer has a
`sync_aggregate`.

##### BLS to execution changes

`BLSToExecutionChange` is disabled in PQ, so the block body no longer has
`bls_to_execution_changes`.

##### Payload attestations

The block body no longer has `payload_attestations`, so the proposer does not
aggregate payload attestation messages.

##### Signed execution payload bid

For self-builds, the signature MUST be the empty `XMSSSignature()`, which is all
zero bytes, and the `bid.value` MUST be zero. All other conditions on
`signed_execution_payload_bid` are unchanged.

##### Execution requests

*Note*: The function `get_execution_requests` is modified to no longer parse PQ
registration requests and to parse validator preregistration, builder
preregistration, and voluntary exit requests.

```python
def get_execution_requests(execution_requests_list: Sequence[bytes]) -> ExecutionRequests:
    deposits = DepositRequests()
    withdrawals = WithdrawalRequests()
    consolidations = ConsolidationRequests()
    builder_deposits = BuilderDepositRequests()
    builder_exits = BuilderExitRequests()
    # [New in PQ:EIP8205]
    validator_preregistrations = ValidatorPreregistrationRequests()
    # [New in PQ:EIP8205]
    builder_preregistrations = BuilderPreregistrationRequests()
    # [New in PQ]
    voluntary_exits = VoluntaryExitRequests()

    request_types = [
        DEPOSIT_REQUEST_TYPE,
        WITHDRAWAL_REQUEST_TYPE,
        CONSOLIDATION_REQUEST_TYPE,
        BUILDER_DEPOSIT_REQUEST_TYPE,
        BUILDER_EXIT_REQUEST_TYPE,
        # [Modified in PQ]
        # Removed `VALIDATOR_PQ_REGISTRATION_REQUEST_TYPE`
        # [Modified in PQ]
        # Removed `BUILDER_PQ_REGISTRATION_REQUEST_TYPE`
        # [New in PQ:EIP8205]
        VALIDATOR_PREREGISTRATION_REQUEST_TYPE,
        # [New in PQ:EIP8205]
        BUILDER_PREREGISTRATION_REQUEST_TYPE,
        # [New in PQ]
        VOLUNTARY_EXIT_REQUEST_TYPE,
    ]

    prev_request_type = None
    for request in execution_requests_list:
        request_type, request_data = request[0:1], request[1:]

        # Check that the request type is valid
        assert request_type in request_types
        # Check that the request data is not empty
        assert len(request_data) != 0
        # Check that requests are in strictly ascending order
        # Each successive type must be greater than the last with no duplicates
        assert prev_request_type is None or prev_request_type < request_type
        prev_request_type = request_type

        if request_type == DEPOSIT_REQUEST_TYPE:
            deposits = ssz_deserialize(DepositRequests, request_data)
        elif request_type == WITHDRAWAL_REQUEST_TYPE:
            withdrawals = ssz_deserialize(WithdrawalRequests, request_data)
        elif request_type == CONSOLIDATION_REQUEST_TYPE:
            consolidations = ssz_deserialize(ConsolidationRequests, request_data)
        elif request_type == BUILDER_DEPOSIT_REQUEST_TYPE:
            builder_deposits = ssz_deserialize(BuilderDepositRequests, request_data)
        elif request_type == BUILDER_EXIT_REQUEST_TYPE:
            builder_exits = ssz_deserialize(BuilderExitRequests, request_data)
        # [New in PQ:EIP8205]
        elif request_type == VALIDATOR_PREREGISTRATION_REQUEST_TYPE:
            validator_preregistrations = ssz_deserialize(
                ValidatorPreregistrationRequests, request_data
            )
        # [New in PQ:EIP8205]
        elif request_type == BUILDER_PREREGISTRATION_REQUEST_TYPE:
            builder_preregistrations = ssz_deserialize(BuilderPreregistrationRequests, request_data)
        # [New in PQ]
        elif request_type == VOLUNTARY_EXIT_REQUEST_TYPE:
            voluntary_exits = ssz_deserialize(VoluntaryExitRequests, request_data)

    return ExecutionRequests(
        deposits=deposits,
        withdrawals=withdrawals,
        consolidations=consolidations,
        builder_deposits=builder_deposits,
        builder_exits=builder_exits,
        # [Modified in PQ]
        # Removed `validator_pq_registrations`
        # [Modified in PQ]
        # Removed `builder_pq_registrations`
        # [New in PQ:EIP8205]
        validator_preregistrations=validator_preregistrations,
        # [New in PQ:EIP8205]
        builder_preregistrations=builder_preregistrations,
        # [New in PQ]
        voluntary_exits=voluntary_exits,
    )
```

#### Packaging into a `SignedBeaconBlock`

##### State root

```python
def compute_new_state_root(state: BeaconState, block: BeaconBlock) -> Root:
    temp_state: BeaconState = state.copy()
    # [Modified in PQ]
    signed_block = SignedBeaconBlock(message=block, signature=XMSSSignature())
    state_transition(temp_state, signed_block, validate_result=False)
    return hash_tree_root(temp_state)
```

##### Signature

`signed_block = SignedBeaconBlock(message=block, signature=block_signature)`,
where `block_signature` is obtained from:

```python
def get_block_signature(
    state: BeaconState,
    block: BeaconBlock,
    # [Modified in PQ]
    privkey: Bytes32,
) -> XMSSSignature:
    domain = get_domain(state, DOMAIN_BEACON_PROPOSER, compute_epoch_at_slot(block.slot))
    signing_root = compute_signing_root(block, domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(block.slot, LEAF_OFFSET_BEACON_PROPOSER)
    return xmss.Sign(privkey, leaf_index, signing_root)
```

### Head voting

A validator on the head vote committee of `slot` creates, signs and broadcasts a
`HeadVoteMessage` for that slot.

*Note*: In the Goldilocks schedule, head voting occurs one quarter of the way
through the slot, after unlocking against the previous slot's votes. The
validator must satisfy the fork choice's observation requirement after waking
up.

*TODO*: Specify the head-vote deadline and voting helper.

#### Head vote data

First, the validator constructs `head_vote_data`, a
[`HeadVoteData`](./beacon-chain.md#headvotedata) object:

- Let `head` be the head selected by the AC voting procedure for `slot`.
- Set `head_vote_data.slot = slot`.
- Set `head_vote_data.beacon_block_root = hash_tree_root(head)`.
- Set `head_vote_data.payload_status` to `PAYLOAD_STATUS_PENDING` if
  `head.slot == slot`. Otherwise, set it to the payload status of `head`
  selected by the AC voting procedure, `PAYLOAD_STATUS_FULL` or
  `PAYLOAD_STATUS_EMPTY`.

The AC voting procedure applies view merge, AC locks and FG restrictions using
its voting view.

#### Construct head vote

The validator creates `head_vote_message` as a
[`HeadVoteMessage`](./beacon-chain.md#headvotemessage):

- Set `head_vote_message.validator_index = validator_index`.
- Set `head_vote_message.data = head_vote_data`.
- Set `head_vote_message.signature` to
  `get_head_vote_signature(state, head_vote_data, privkey)`.

```python
def get_head_vote_signature(
    state: BeaconState, data: HeadVoteData, privkey: Bytes32
) -> XMSSSignature:
    domain = get_domain(state, DOMAIN_HEAD_VOTE, compute_epoch_at_slot(data.slot))
    signing_root = compute_signing_root(data, domain)
    leaf_index = compute_xmss_leaf_index(data.slot, LEAF_OFFSET_HEAD_VOTE)
    return xmss.Sign(privkey, leaf_index, signing_root)
```

The validator must record the selected root before signing and must not sign
another head for the same slot.

#### Broadcast head vote

The validator broadcasts `head_vote_message` on the global `head_vote`
[topic](./p2p-interface.md#new-head_vote) and processes it locally.

### Attesting

A validator attempts to create an FG attestation in the slot of its attestation
committee using the rules below. It sends no new attestation if there is no FG
source or if its signing history suppresses the vote.

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
`get_finality_attestation_data(record, target, justified, finalized_height)`. If
it returns `None`, the validator sends no new attestation.

*Note*: The duplicate-vote checks suppress the entire attestation, including any
new finality pair.

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
def record_finality_attestation(record: FinalitySigningRecord, data: AttestationData) -> None:
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
[`SingleAttestation`](./beacon-chain.md#singleattestation) with the following
fields:

- Set `attestation.committee_index` to the assigned committee index.
- Set `attestation.attester_index = validator_index`.
- Set `attestation.data = attestation_data`.
- Set `attestation.round` to the round of the assigned slot.
- Set `attestation.signature` to
  `get_attestation_signature(state, attestation_data, attestation.round, privkey)`.

```python
def get_attestation_signature(
    state: BeaconState,
    attestation_data: AttestationData,
    # [New in PQ:EIP8453]
    round: Round,
    # [Modified in PQ]
    privkey: Bytes32,
) -> XMSSSignature:
    # [Modified in PQ:EIP8453]
    domain = get_domain(state, DOMAIN_FINALITY_ATTESTER, compute_epoch_at_round(round))
    signing_root = compute_signing_root(attestation_data, domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_attestation_leaf_index(round)
    return xmss.Sign(privkey, leaf_index, signing_root)
```

The signature covers `attestation.data`, but not `attestation.round` or
`attestation.committee_index`. It is signed at the leaf of `attestation.round`,
so a validator MUST NOT sign two different attestations in the same round.

#### Broadcast attestation

The validator broadcasts `attestation` on the `attestation_{subnet_id}`
[topic](./p2p-interface.md#new-attestation_subnet_id) and processes it locally,
where `subnet_id = compute_subnet_for_attestation(attestation.committee_index)`.

```python
def compute_subnet_for_attestation(
    # [Modified in PQ:EIP8453]
    # Removed `committees_per_slot`
    # [Modified in PQ:EIP8453]
    # Removed `slot`
    committee_index: CommitteeIndex,
) -> SubnetID:
    """
    Return the subnet of the attestation committee at ``committee_index``.
    """
    # [Modified in PQ:EIP8453]
    return SubnetID(committee_index % ATTESTATION_SUBNET_COUNT_PQ)
```

### Attestation aggregation

Validators aggregate head votes and FG attestations separately. The messages
passed to the helpers below must have valid signatures under the same domain and
leaf, and valid committee assignments for `state`.

*Note*: The helpers aggregate individual messages, and prove their signatures
with an `AttestationProof` in place of an aggregate signature.

#### Aggregation selection

*TODO*: Specify aggregator selection for head votes and FG attestations.
`get_slot_signature` and `is_aggregator` are deprecated.

#### Construct aggregate

##### Head votes

Construct `aggregate_vote` using `get_aggregate_head_vote` with head vote
messages for the same slot, block root and payload status. A validator holding
several seats in the committee is listed and signs once, and its vote counts for
each of its seats.

```python
def get_aggregate_head_vote(state: BeaconState, messages: Sequence[HeadVoteMessage]) -> HeadVote:
    """
    Aggregate head vote messages with identical data and distinct signers.
    """
    assert len(messages) > 0
    data = messages[0].data
    assert all(message.data == data for message in messages)
    voter_indices = sorted({message.validator_index for message in messages})
    assert len(voter_indices) == len(messages)

    for validator_index in voter_indices:
        assert validator_index in get_head_vote_committee(state, data.slot)

    return HeadVote(voter_indices=HeadVoteCommitteeIndices(data=voter_indices), data=data)
```

The aggregator proves the signatures of the messages it aggregates, in the order
of the aggregate's `voter_indices`:

*TODO*: Revisit once the proof of head vote signatures is specified.

```python
def get_aggregate_head_vote_stark(
    state: BeaconState, aggregate_vote: HeadVote, signatures: Sequence[XMSSSignature]
) -> AttestationProof:
    statement = get_head_vote_statement(state, aggregate_vote)
    return AttestationProof(data=stark.ProveAggregates([statement], [signatures]))
```

##### FG attestations

Construct `aggregate_attestation` using `get_aggregate_attestation` with
individual attestations for the same data and round.

*TODO*: Specify how attestations cast in different rounds are aggregated. Their
signers sign at different XMSS leaves, so they cannot share an aggregate.

```python
def get_aggregate_attestation(
    state: BeaconState, attestations: Sequence[SingleAttestation]
) -> Attestation:
    """
    Aggregate attestations with identical data and round, and distinct signers.
    """
    assert len(attestations) > 0
    data = attestations[0].data
    round = attestations[0].round
    assert all(a.data == data and a.round == round for a in attestations)
    participants = {a.attester_index for a in attestations}
    assert len(participants) == len(attestations)

    committee_bits = AttestationCommitteeBits()
    for attestation in attestations:
        assert attestation.committee_index < ATTESTATION_COMMITTEES_PER_ROUND
        committee_bits[attestation.committee_index] = Boolean(True)

    epoch = compute_epoch_at_round(round)
    aggregation_bits = get_attestation_aggregation_bits(state, epoch, committee_bits, participants)
    return Attestation(
        aggregation_bits=aggregation_bits,
        data=data,
        committee_bits=committee_bits,
        round=round,
    )
```

The aggregator proves the signatures of the attestations it aggregates. It
passes, for each committee of the aggregate in order, the signatures of that
committee's attesters in the order of the committee:

```python
def get_aggregate_stark(
    state: BeaconState, aggregate: Attestation, signatures: Sequence[Sequence[XMSSSignature]]
) -> AttestationProof:
    statements = get_attestation_statements(state, aggregate)
    return AttestationProof(data=stark.ProveAggregates(statements, signatures))
```

##### Aggregation bits

`get_attestation_aggregation_bits` encodes signers in committee-index order,
matching `get_aggregate_participants` in the beacon-chain specification. The
size bound applies to all members of the represented committees, not only the
signers. Split messages into separate aggregates when the bound would be
exceeded.

```python
def get_attestation_aggregation_bits(
    state: BeaconState,
    epoch: Epoch,
    committee_bits: AttestationCommitteeBits,
    participants: set[ValidatorIndex],
) -> AggregationBits:
    """
    Encode participants in the concatenation of the selected attestation
    committees.
    """
    aggregation_bits = AggregationBits()
    represented_participants: set[ValidatorIndex] = set()
    for committee_index in get_committee_indices(committee_bits):
        committee = get_attestation_committee(state, epoch, committee_index)
        assert len(aggregation_bits) + len(committee) <= MAX_VALIDATORS_PER_AGGREGATE
        for validator_index in committee:
            is_participant = validator_index in participants
            aggregation_bits.append(Boolean(is_participant))
            if is_participant:
                represented_participants.add(validator_index)
    assert represented_participants == participants
    return aggregation_bits
```

#### Broadcast aggregate

The validator broadcasts the aggregate and its proof for block inclusion.

*TODO*: Specify aggregate gossip messages, their proof wrappers and broadcast
deadlines. Gossip deduplication must use the data and signers.

*Note*: An FG aggregate's round must be no later than
`get_current_round(state)`, and its epoch no earlier than
`compute_epoch_at_slot(state.finalized_slot)`, when included in a block. Its
data must also remain valid against the inclusion state.

### Sync committees

Sync committees are removed in PQ, so validators have no sync committee duties.

### Payload timeliness attestation

#### Constructing the `PayloadAttestationMessage`

```python
def get_payload_attestation_message_signature(
    state: BeaconState,
    attestation: PayloadAttestationMessage,
    # [Modified in PQ]
    privkey: Bytes32,
) -> XMSSSignature:
    domain = get_domain(state, DOMAIN_PTC_ATTESTER, compute_epoch_at_slot(attestation.data.slot))
    signing_root = compute_signing_root(attestation.data, domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(attestation.data.slot, LEAF_OFFSET_PTC_ATTESTER)
    return xmss.Sign(privkey, leaf_index, signing_root)
```

## Protection best practices

An XMSS key MUST NOT sign two different messages at the same leaf, because that
exposes the leaf and lets others forge signatures at it. A validator client
SHOULD therefore extend its slashing protection to every message it signs. It
keeps a local record of the signing root signed at each leaf, refuses to sign a
different signing root at a recorded leaf, and records each new signing root
before signing it. Like the slashing protection database, this record must
survive restarts and move with the key.

An attestation is signed at the leaf of its round, and a head vote at a leaf of
its slot. The finality signing record and the selected head must be persisted
before signing, so that an interrupted duty is not signed again with different
data.

A message without a leaf of its own, such as a voluntary exit, is signed at a
reserved leaf, one of the first `XMSS_RESERVED_LEAVES` leaves. The signer MUST
use each reserved leaf at most once, for example by allocating them in
increasing order. The record must include the leaf of the key's preregistration,
which is signed before the validator exists.
