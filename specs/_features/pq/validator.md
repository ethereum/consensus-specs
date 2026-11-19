# PQ -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configs](#configs)
  - [Time parameters](#time-parameters)
- [Containers](#containers)
  - [Modified containers](#modified-containers)
    - [`AggregateAndProof`](#aggregateandproof)
    - [`SignedAggregateAndProof`](#signedaggregateandproof)
- [Becoming a validator](#becoming-a-validator)
  - [Initialization](#initialization)
    - [VRF tree](#vrf-tree)
      - [New `compute_vrf_leaf`](#new-compute_vrf_leaf)
      - [New `compute_vrf_node`](#new-compute_vrf_node)
      - [New `compute_vrf_root`](#new-compute_vrf_root)
      - [New `compute_vrf_proof`](#new-compute_vrf_proof)
    - [XMSS public key](#xmss-public-key)
  - [Preregister](#preregister)
  - [Submit deposit](#submit-deposit)
- [Validator assignments](#validator-assignments)
  - [Modified `get_committee_assignment`](#modified-get_committee_assignment)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block and sidecar proposal](#block-and-sidecar-proposal)
    - [Broadcasting `SignedProposerPreferences`](#broadcasting-signedproposerpreferences)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [Randao reveal](#randao-reveal)
      - [Attestations](#attestations)
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
  - [Attesting](#attesting)
    - [Construct attestation](#construct-attestation)
      - [Signature](#signature-1)
    - [Attestation subnet](#attestation-subnet)
      - [Modified `compute_subnet_for_attestation`](#modified-compute_subnet_for_attestation)
  - [Attestation aggregation](#attestation-aggregation)
    - [Aggregation selection](#aggregation-selection)
    - [Construct aggregate](#construct-aggregate)
      - [Aggregate stark](#aggregate-stark)
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
`compute_xmss_attestation_leaf_index` assigns to its target epoch, and a message
without a leaf of its own, such as a voluntary exit, which is signed at a
reserved leaf, see [Protection best practices](#protection-best-practices).

## Configs

### Time parameters

*[New in PQ]*

| Name                     | Value          | Duration                  |
| ------------------------ | -------------- | ------------------------- |
| `AGGREGATION_CUTOFF_BPS` | `Uint64(4000)` | 40% of `SLOT_DURATION_MS` |
| `AGGREGATE_DUE_BPS_PQ`   | `Uint64(6000)` | 60% of `SLOT_DURATION_MS` |
| `AGGREGATOR_DELAY_BPS`   | `Uint64(500)`  | 5% of `SLOT_DURATION_MS`  |

## Containers

### Modified containers

#### `AggregateAndProof`

```python
class AggregateAndProof(Container):
    aggregator_index: ValidatorIndex
    aggregate: Attestation
    # [Modified in PQ]
    # Removed `selection_proof`
    # [New in PQ]
    proof: AttestationProof
```

#### `SignedAggregateAndProof`

```python
class SignedAggregateAndProof(Container):
    message: AggregateAndProof
    # [Modified in PQ]
    signature: XMSSSignature
```

## Becoming a validator

### Initialization

#### VRF tree

A validator's VRF seed, `vrf_seed`, is a secret 32-byte value from which its VRF
tree is derived. It must be securely generated and kept secret, since anyone who
learns it can compute the validator's future RANDAO reveals.

The VRF seed is independent of the validator's XMSS private key. A validator's
VRF root cannot be changed, so the validator must keep its VRF seed for as long
as it validates and take it along when it moves to another client. A tree
derived from any other seed has a different root, so its proofs fail
verification and the validator's blocks are invalid.

The VRF tree is a Merkle tree of depth `VRF_TREE_DEPTH`, hashed with
`keccak256`, with one leaf for each slot. A validator's VRF root is the root of
its VRF tree, `compute_vrf_root(vrf_seed)`. Its VRF proof for a slot,
`compute_vrf_proof(vrf_seed, slot)`, is the leaf at index `slot` followed by the
leaf's Merkle branch. It reveals the proof as its RANDAO reveal when it
proposes. The tree is fixed in advance, so a validator cannot grind its proofs,
and nobody can predict them before they are revealed.

##### New `compute_vrf_leaf`

```python
def compute_vrf_leaf(vrf_seed: Bytes32, index: Uint64) -> Bytes32:
    """
    Return the leaf at ``index`` of the VRF tree derived from ``vrf_seed``.
    """
    return keccak256(vrf_seed + uint_to_bytes(index))
```

##### New `compute_vrf_node`

```python
def compute_vrf_node(vrf_seed: Bytes32, height: Uint64, index: Uint64) -> Bytes32:
    """
    Return the node at ``index`` among the nodes ``height`` levels above the
    leaves of the VRF tree derived from ``vrf_seed``.
    """
    if height == 0:
        return compute_vrf_leaf(vrf_seed, index)
    left = compute_vrf_node(vrf_seed, height - 1, 2 * index)
    right = compute_vrf_node(vrf_seed, height - 1, 2 * index + 1)
    return keccak256(left + right)
```

##### New `compute_vrf_root`

```python
def compute_vrf_root(vrf_seed: Bytes32) -> Root:
    """
    Return the root of the VRF tree derived from ``vrf_seed``.
    """
    return Root(compute_vrf_node(vrf_seed, VRF_TREE_DEPTH, Uint64(0)))
```

##### New `compute_vrf_proof`

```python
def compute_vrf_proof(vrf_seed: Bytes32, slot: Slot) -> VRFProof:
    """
    Return the leaf at index ``slot`` of the VRF tree derived from
    ``vrf_seed``, followed by the leaf's Merkle branch.
    """
    branch = [
        compute_vrf_node(vrf_seed, Uint64(height), Uint64((slot // 2**height) ^ 1))
        for height in range(VRF_TREE_DEPTH)
    ]
    return VRFProof(data=[compute_vrf_leaf(vrf_seed, Uint64(slot))] + branch)
```

#### XMSS public key

A validator's XMSS private key, `privkey`, is a 32-byte seed from which its
leanXMSS key is derived. It must be securely generated along with the resultant
XMSS public key. This `privkey` must be "hot", that is, constantly available to
sign data throughout the lifetime of the validator.

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

### Modified `get_committee_assignment`

*Note*: The body is unchanged, but each slot now has at most
`MAX_COMMITTEES_PER_SLOT_PQ` committees, so a validator's committee and
committee index may differ.

```python
def get_committee_assignment(
    state: BeaconState, epoch: Epoch, validator_index: ValidatorIndex
) -> tuple[Sequence[ValidatorIndex], CommitteeIndex, Slot] | None:
    """
    Return the committee assignment in the ``epoch`` for ``validator_index``.
    ``assignment`` returned is a tuple of the following form:
        * ``assignment[0]`` is the list of validators in the committee
        * ``assignment[1]`` is the index to which the committee is assigned
        * ``assignment[2]`` is the slot at which the committee is assigned
    Return None if no assignment.
    """
    next_epoch = get_current_epoch(state) + 1
    assert epoch <= next_epoch

    start_slot = compute_start_slot_at_epoch(epoch)
    committee_count_per_slot = get_committee_count_per_slot(state, epoch)
    for slot in range(start_slot, start_slot + SLOTS_PER_EPOCH):
        for index in range(committee_count_per_slot):
            committee = get_beacon_committee(state, Slot(slot), CommitteeIndex(index))
            if validator_index in committee:
                return committee, CommitteeIndex(index), Slot(slot)
    return None
```

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

#### Constructing the `BeaconBlockBody`

##### Randao reveal

Set `block.body.randao_reveal` to `compute_vrf_proof(vrf_seed, block.slot)`, the
proposer's VRF proof for `block.slot`.

##### Attestations

The proposer should run the following function to construct an on chain final
aggregate from a list of network aggregates with equal `AttestationData`:

```python
def compute_on_chain_aggregate(network_aggregates: Sequence[Attestation]) -> Attestation:
    aggregates = sorted(
        network_aggregates, key=lambda a: get_committee_indices(a.committee_bits)[0]
    )

    data = aggregates[0].data
    aggregation_bits = AggregationBits()
    for a in aggregates:
        for b in a.aggregation_bits:
            aggregation_bits.append(b)

    committee_indices = [
        get_committee_indices(aggregate.committee_bits)[0] for aggregate in aggregates
    ]
    # [Modified in PQ]
    committee_flags = [(index in committee_indices) for index in range(MAX_COMMITTEES_PER_SLOT_PQ)]
    committee_bits = CommitteeBits(data=committee_flags)

    return Attestation(
        aggregation_bits=AggregationBits(data=aggregation_bits),
        data=data,
        # [Modified in PQ]
        # Removed `signature`
        committee_bits=CommitteeBits(data=committee_bits),
    )
```

##### Proof

The proposer sets `body.proof` to `stark.MergeProofs(proofs)`, where `proofs`
holds the `proof` of each network aggregate behind `body.attestations`, ordered
as the attestations are and, within each, by committee index. The merged proof
then proves the statements that `process_stark` checks.

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

### Attesting

#### Construct attestation

##### Signature

An attestation carries no signature. The validator broadcasts it as a
`SingleAttestation`, whose `signature` is obtained from:

```python
def get_attestation_signature(
    state: BeaconState,
    attestation_data: AttestationData,
    # [Modified in PQ]
    privkey: Bytes32,
) -> XMSSSignature:
    domain = get_domain(state, DOMAIN_BEACON_ATTESTER, attestation_data.target.epoch)
    signing_root = compute_signing_root(attestation_data, domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_attestation_leaf_index(attestation_data.target.epoch)
    return xmss.Sign(privkey, leaf_index, signing_root)
```

#### Attestation subnet

##### Modified `compute_subnet_for_attestation`

```python
def compute_subnet_for_attestation(
    committees_per_slot: Uint64, slot: Slot, committee_index: CommitteeIndex
) -> SubnetID:
    """
    Compute the correct subnet for an attestation.
    """
    slots_since_epoch_start = Uint64(slot % SLOTS_PER_EPOCH)
    committees_since_epoch_start = committees_per_slot * slots_since_epoch_start

    # [Modified in PQ]
    return SubnetID((committees_since_epoch_start + committee_index) % ATTESTATION_SUBNET_COUNT_PQ)
```

### Attestation aggregation

#### Aggregation selection

`get_slot_signature` is deprecated. A validator aggregates for its committee if
it is in the committee's aggregation committee.

```python
def is_aggregator(
    state: BeaconState,
    slot: Slot,
    index: CommitteeIndex,
    # [New in PQ]
    validator_index: ValidatorIndex,
    # [Modified in PQ]
    # Removed `slot_signature`
) -> bool:
    # [Modified in PQ]
    return validator_index in get_aggregation_committee(state, slot, index)
```

#### Construct aggregate

The aggregators of a committee are staggered in the order of its aggregation
committee, `get_aggregation_committee(state, slot, index)`. Let `position` be
the aggregator's index in it. The aggregator collects attestations until
`get_aggregation_cutoff_ms(position)` milliseconds into the slot, then
constructs its aggregate from them.

For example, with a `SLOT_DURATION_MS` of 12 seconds, attestations are due 3
seconds into the slot. An aggregator has from then until its cutoff to receive
attestations, and from its cutoff until it broadcasts to build its proof. A
block includes attestations from at least `MIN_ATTESTATION_INCLUSION_DELAY_PQ`
slots before it, so the earliest proposer that can include the aggregate has
until the start of its slot, 24 seconds into the attestations' slot, to receive
the aggregate and merge its proof:

| Position | Cutoff at | Broadcasts at | Collects for | Proves for | Until proposal |
| :------: | :-------: | :-----------: | :----------: | :--------: | :------------: |
|    0     |   4.8s    |     7.2s      |     1.8s     |    2.4s    |     16.8s      |
|    1     |   5.4s    |     7.8s      |     2.4s     |    2.4s    |     16.2s      |
|    2     |   6.0s    |     8.4s      |     3.0s     |    2.4s    |     15.6s      |
|    3     |   6.6s    |     9.0s      |     3.6s     |    2.4s    |     15.0s      |

##### Aggregate stark

An attestation carries no signature, so the aggregator proves the signatures of
the attestations it aggregates with an `AttestationProof`, in place of an
aggregate signature. It passes the signatures of the attesters in the order of
their committee:

```python
def get_aggregate_stark(
    state: BeaconState, aggregate: Attestation, signatures: Sequence[XMSSSignature]
) -> AttestationProof:
    statements = get_attestation_statements(state, aggregate)
    return AttestationProof(data=stark.ProveAggregates(statements, [signatures]))
```

#### Broadcast aggregate

The aggregator broadcasts its aggregate `get_aggregate_due_ms(position)`
milliseconds into the slot, but only if no aggregate with the same data and
committee that it has received includes all of its attesters, that is, if
`should_broadcast_aggregate(aggregate, received_aggregates)` returns `True`.
Otherwise, gossip would ignore it, as it does any aggregate whose attesters are
all in an aggregate already seen.

```python
def should_broadcast_aggregate(
    aggregate: Attestation, received_aggregates: Sequence[Attestation]
) -> bool:
    """
    Return whether no aggregate in ``received_aggregates`` with the same data
    and committee as ``aggregate`` includes all of its attesters.
    """
    received_bits: set[tuple[bool, ...]] = set()
    for received in received_aggregates:
        if received.data != aggregate.data:
            continue
        if received.committee_bits != aggregate.committee_bits:
            continue
        received_bits.add(tuple(bool(bit) for bit in received.aggregation_bits))
    aggregate_bits = tuple(bool(bit) for bit in aggregate.aggregation_bits)
    return not is_non_strict_superset(received_bits, aggregate_bits)
```

Each received aggregate is compared on its own, not together with the others. A
proposer can include only one aggregate per committee, so two aggregates that
together cover the aggregator's attesters do not make its aggregate redundant.
For example, here is whether an aggregator in a committee of four broadcasts an
aggregate with attesters 0 and 1 (`1100`), given the aggregates with the same
data and committee that it has received:

| Received          | Broadcast | Why                                       |
| :---------------- | :-------: | :---------------------------------------- |
| Nothing           |    Yes    | There is nothing to compare against       |
| `1000`            |    Yes    | It lacks attester 1                       |
| `1110`            |    No     | It has attesters 0 and 1                  |
| `1100`            |    No     | An identical aggregate counts as superset |
| `1000` and `0100` |    Yes    | Neither has both attesters 0 and 1        |
| `0011`            |    Yes    | It has neither attester 0 nor 1           |

```python
def get_aggregate_and_proof(
    # [Modified in PQ]
    # Removed `state`
    aggregator_index: ValidatorIndex,
    aggregate: Attestation,
    # [Modified in PQ]
    # Removed `privkey`
    # [New in PQ]
    proof: AttestationProof,
) -> AggregateAndProof:
    return AggregateAndProof(
        aggregator_index=aggregator_index,
        aggregate=aggregate,
        # [Modified in PQ]
        # Removed `selection_proof`
        # [New in PQ]
        proof=proof,
    )
```

```python
def get_aggregate_and_proof_signature(
    state: BeaconState,
    aggregate_and_proof: AggregateAndProof,
    # [Modified in PQ]
    privkey: Bytes32,
) -> XMSSSignature:
    aggregate = aggregate_and_proof.aggregate
    domain = get_domain(
        state, DOMAIN_AGGREGATE_AND_PROOF, compute_epoch_at_slot(aggregate.data.slot)
    )
    signing_root = compute_signing_root(aggregate_and_proof, domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(aggregate.data.slot, LEAF_OFFSET_AGGREGATE_AND_PROOF)
    return xmss.Sign(privkey, leaf_index, signing_root)
```

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

A message without a leaf of its own, such as a voluntary exit, is signed at a
reserved leaf, one of the first `XMSS_RESERVED_LEAVES` leaves. The signer MUST
use each reserved leaf at most once, for example by allocating them in
increasing order. The record must include the leaf of the key's preregistration,
which is signed before the validator exists.
