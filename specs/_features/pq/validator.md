# PQ -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Misc](#misc)
- [Containers](#containers)
  - [Modified containers](#modified-containers)
    - [`AggregateAndProof`](#aggregateandproof)
    - [`SignedAggregateAndProof`](#signedaggregateandproof)
- [Becoming a validator](#becoming-a-validator)
  - [Initialization](#initialization)
    - [VRF tree](#vrf-tree)
    - [XMSS public key](#xmss-public-key)
  - [Preregister](#preregister)
  - [Submit deposit](#submit-deposit)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block and sidecar proposal](#block-and-sidecar-proposal)
    - [Broadcasting `SignedProposerPreferences`](#broadcasting-signedproposerpreferences)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [Randao reveal](#randao-reveal)
      - [Attestations](#attestations)
      - [Proof](#proof)
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
`compute_xmss_attestation_leaf_index` assigns to its target epoch. At the
upgrade, each validator that registered an XMSS public key with EIP-8483 takes
it in place of its BLS public key. A validator without a registration becomes
withdrawable at the upgrade, and its balance is withdrawn, unless it has `0x00`
withdrawal credentials, in which case its balance stays locked. See
[the fork document](./fork.md) for details.

## Constants

### Misc

*[New in PQ]*

| Name                                  | Value                |
| ------------------------------------- | -------------------- |
| `TARGET_AGGREGATORS_PER_COMMITTEE_PQ` | `Uint64(2**2)` (= 4) |

*Note*: Aggregates are much larger than with BLS, so fewer validators are
selected to aggregate. `TARGET_AGGREGATORS_PER_COMMITTEE_PQ` replaces
`TARGET_AGGREGATORS_PER_COMMITTEE`.

## Containers

### Modified containers

#### `AggregateAndProof`

```python
class AggregateAndProof(Container):
    aggregator_index: ValidatorIndex
    aggregate: Attestation
    # [Modified in PQ]
    selection_proof: VRFProof
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

A validator builds a Merkle tree of depth `VRF_TREE_DEPTH` whose leaves are
secret random values, one for each slot, and registers the root of the tree as
its VRF root with EIP-8483, as the last 32 bytes of the registration's
`pq_data`. Its VRF proof for a slot is the leaf at index `slot`, followed by the
leaf's Merkle branch. It reveals the proof as its RANDAO reveal when it proposes
and as its selection proof when it aggregates. The tree is fixed at
registration, so a validator cannot grind its proofs, and nobody can predict
them before they are revealed.

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
submits a `PreregistrationRequest` that binds its XMSS public key to its
withdrawal credentials and VRF root. It signs the `ValidatorPreregistration`
under `DOMAIN_PREREGISTRATION`, computed with `compute_domain` and the chain's
`genesis_validators_root`, at `RESERVED_LEAF_PREREGISTRATION`.

The validator waits until its binding is in `state.validator_preregistrations`,
then submits its deposit before the binding's `expiry_slot`. If the binding is
not stored, a deposit for the key may already be pending, so the validator
generates a new key and preregisters that one instead.

A key signs only one binding. To renew an expired binding, the validator
resubmits the same request. To change its binding, it generates a new key.

### Submit deposit

After the upgrade, a deposit carries no signature. Its `pubkey` is
`XMSS_DEPOSIT_PREFIX`, 16 zero bytes, followed by the validator's XMSS public
key, and its `signature` holds the validator's VRF root followed by 64 zero
bytes. A deposit whose XMSS public key is already in `state.validators` tops up
that validator. While the key has an active preregistration, a deposit for it is
discarded unless its withdrawal credentials and VRF root match the binding.

*Note*: A deposit whose `pubkey` does not start with 16 zero bytes is treated as
a legacy deposit, so the validator it creates is exited at once.

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

Set `block.body.randao_reveal` to the proposer's VRF proof for `block.slot`, the
leaf at index `block.slot` of its VRF tree followed by the leaf's Merkle branch.
`get_epoch_signature` is deprecated.

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
    committee_flags = [(index in committee_indices) for index in range(MAX_COMMITTEES_PER_SLOT)]
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
registration requests and to parse preregistration requests.

```python
def get_execution_requests(execution_requests_list: Sequence[bytes]) -> ExecutionRequests:
    deposits = DepositRequests()
    withdrawals = WithdrawalRequests()
    consolidations = ConsolidationRequests()
    builder_deposits = BuilderDepositRequests()
    builder_exits = BuilderExitRequests()
    # [New in EIP8205]
    preregistrations = PreregistrationRequests()

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
        # [New in EIP8205]
        PREREGISTRATION_REQUEST_TYPE,
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
        # [New in EIP8205]
        elif request_type == PREREGISTRATION_REQUEST_TYPE:
            preregistrations = ssz_deserialize(PreregistrationRequests, request_data)

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
        # [New in EIP8205]
        preregistrations=preregistrations,
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

A validator's selection proof for a slot is its VRF proof for that slot.
`get_slot_signature` is deprecated.

`is_aggregator` hashes the leaf with the validator index and the root of the
finalized checkpoint. That root is unknown when the tree is registered, so a
validator cannot fill its tree with leaves that always select it.

```python
def is_aggregator(
    state: BeaconState,
    slot: Slot,
    index: CommitteeIndex,
    # [New in PQ]
    validator_index: ValidatorIndex,
    # [Modified in PQ]
    selection_proof: VRFProof,
) -> bool:
    committee = get_beacon_committee(state, slot, index)
    # [Modified in PQ]
    modulo = max(1, len(committee) // TARGET_AGGREGATORS_PER_COMMITTEE_PQ)
    # [Modified in PQ]
    finalized_root = state.finalized_checkpoint.root
    selection = sha256(
        selection_proof[0]
        + DOMAIN_SELECTION_PROOF
        + uint_to_bytes(validator_index)
        + finalized_root
    )
    return bytes_to_uint64(selection[0:8]) % modulo == 0
```

#### Construct aggregate

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

```python
def get_aggregate_and_proof(
    # [Modified in PQ]
    # Removed `state`
    aggregator_index: ValidatorIndex,
    aggregate: Attestation,
    # [Modified in PQ]
    # Removed `privkey`
    # [New in PQ]
    selection_proof: VRFProof,
    # [New in PQ]
    proof: AttestationProof,
) -> AggregateAndProof:
    return AggregateAndProof(
        aggregator_index=aggregator_index,
        aggregate=aggregate,
        # [Modified in PQ]
        selection_proof=selection_proof,
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

A voluntary exit is signed at `RESERVED_LEAF_VOLUNTARY_EXIT`, a leaf that a key
uses only once, so a validator MUST NOT sign more than one voluntary exit.
