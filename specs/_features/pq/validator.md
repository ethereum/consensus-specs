# PQ -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Containers](#containers)
  - [Modified containers](#modified-containers)
    - [`AggregateAndProof`](#aggregateandproof)
    - [`ContributionAndProof`](#contributionandproof)
    - [`SignedAggregateAndProof`](#signedaggregateandproof)
    - [`SignedContributionAndProof`](#signedcontributionandproof)
    - [`SyncCommitteeContribution`](#synccommitteecontribution)
    - [`SyncCommitteeMessage`](#synccommitteemessage)
- [Becoming a validator](#becoming-a-validator)
  - [Initialization](#initialization)
    - [XMSS public key](#xmss-public-key)
  - [Submit deposit](#submit-deposit)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block and sidecar proposal](#block-and-sidecar-proposal)
    - [Broadcasting `SignedProposerPreferences`](#broadcasting-signedproposerpreferences)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [Randao reveal](#randao-reveal)
      - [Attestations](#attestations)
      - [Sync committee](#sync-committee)
      - [Signed execution payload bid](#signed-execution-payload-bid)
      - [Execution requests](#execution-requests)
    - [Packaging into a `SignedBeaconBlock`](#packaging-into-a-signedbeaconblock)
      - [State root](#state-root)
      - [Signature](#signature)
  - [Attesting](#attesting)
    - [Construct attestation](#construct-attestation)
      - [Aggregate signature](#aggregate-signature)
  - [Attestation aggregation](#attestation-aggregation)
    - [Aggregation selection](#aggregation-selection)
    - [Construct aggregate](#construct-aggregate)
      - [Aggregate signature](#aggregate-signature-1)
    - [Broadcast aggregate](#broadcast-aggregate)
  - [Sync committees](#sync-committees)
    - [Sync committee messages](#sync-committee-messages)
      - [Prepare sync committee message](#prepare-sync-committee-message)
    - [Sync committee contributions](#sync-committee-contributions)
      - [Aggregation selection](#aggregation-selection-1)
      - [Construct sync committee contribution](#construct-sync-committee-contribution)
        - [Signature](#signature-1)
      - [Broadcast sync committee contribution](#broadcast-sync-committee-contribution)
  - [Payload timeliness attestation](#payload-timeliness-attestation)
    - [Constructing the `PayloadAttestationMessage`](#constructing-the-payloadattestationmessage)
- [Protection best practices](#protection-best-practices)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
validator" to implement PQ.

Validators sign with leanXMSS instead of BLS. Every message is signed at the
leaf that `compute_xmss_leaf_index` assigns to its slot and type. A validator
that is active before the upgrade keeps validating only if it registered its
XMSS public key with EIP-8483. See [the fork document](./fork.md) for details.

## Containers

### Modified containers

#### `AggregateAndProof`

```python
class AggregateAndProof(Container):
    aggregator_index: ValidatorIndex
    aggregate: Attestation
    # [Modified in PQ]
    selection_proof: XMSSSignature
```

#### `ContributionAndProof`

```python
class ContributionAndProof(Container):
    aggregator_index: ValidatorIndex
    contribution: SyncCommitteeContribution
    # [Modified in PQ]
    selection_proof: XMSSSignature
```

#### `SignedAggregateAndProof`

```python
class SignedAggregateAndProof(Container):
    message: AggregateAndProof
    # [Modified in PQ]
    signature: XMSSSignature
```

#### `SignedContributionAndProof`

```python
class SignedContributionAndProof(Container):
    message: ContributionAndProof
    # [Modified in PQ]
    signature: XMSSSignature
```

#### `SyncCommitteeContribution`

```python
class SyncCommitteeContribution(Container):
    slot: Slot
    beacon_block_root: Root
    subcommittee_index: Uint64
    aggregation_bits: SyncSubcommitteeBits
    # [Modified in PQ]
    signature: XMSSAggregateSignature
```

#### `SyncCommitteeMessage`

```python
class SyncCommitteeMessage(Container):
    slot: Slot
    beacon_block_root: Root
    validator_index: ValidatorIndex
    # [Modified in PQ]
    signature: XMSSSignature
```

## Becoming a validator

### Initialization

#### XMSS public key

Validator public keys are leanXMSS public keys. A private key, `privkey`, is a
32-byte seed from which the key is derived. It must be securely generated along
with the resultant `pubkey`. This `privkey` must be "hot", that is, constantly
available to sign data throughout the lifetime of the validator.

### Submit deposit

Deposits are submitted as described in the
[Phase 0 document](../../phase0/validator.md#submit-deposit), except that
`signature` is the result of `xmss.Sign` of the
`compute_signing_root(deposit_message, domain)` with
`domain=compute_domain(DOMAIN_DEPOSIT)`, at the leaf
`compute_xmss_leaf_index(GENESIS_SLOT, LEAF_OFFSET_DEPOSIT)`.

*Note*: Every deposit is signed at the same leaf, so a key MUST NOT sign two
different deposit messages. The signature of a top-up deposit for an existing
validator is not checked, so a top-up SHOULD carry the empty `XMSSSignature()`
rather than a new signature.

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

Set `block.body.randao_reveal = epoch_signature` where `epoch_signature` is
obtained from:

```python
def get_epoch_signature(
    state: BeaconState,
    block: BeaconBlock,
    # [Modified in PQ]
    privkey: Bytes32,
) -> XMSSSignature:
    domain = get_domain(state, DOMAIN_RANDAO, compute_epoch_at_slot(block.slot))
    signing_root = compute_signing_root(compute_epoch_at_slot(block.slot), domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(block.slot, LEAF_OFFSET_RANDAO)
    return xmss.Sign(privkey, leaf_index, signing_root)
```

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

    # [Modified in PQ]
    signature = XMSSAggregateSignature(
        data=xmss.Aggregate([aggregate.signature for aggregate in aggregates])
    )

    committee_indices = [
        get_committee_indices(aggregate.committee_bits)[0] for aggregate in aggregates
    ]
    committee_flags = [(index in committee_indices) for index in range(MAX_COMMITTEES_PER_SLOT)]
    committee_bits = CommitteeBits(data=committee_flags)

    return Attestation(
        aggregation_bits=AggregationBits(data=aggregation_bits),
        data=data,
        signature=signature,
        committee_bits=CommitteeBits(data=committee_bits),
    )
```

##### Sync committee

Given a collection of the best seen `contributions` (with no repeating
`subcommittee_index` values) and the `BeaconBlock` under construction, the
proposer processes them as follows:

```python
def process_sync_committee_contributions(
    block: BeaconBlock, contributions: set[SyncCommitteeContribution]
) -> None:
    sync_aggregate = SyncAggregate.empty()
    signatures = []
    sync_subcommittee_size = SYNC_COMMITTEE_SIZE // SYNC_COMMITTEE_SUBNET_COUNT

    for contribution in contributions:
        subcommittee_index = contribution.subcommittee_index
        for index, participated in enumerate(contribution.aggregation_bits):
            if participated:
                participant_index = sync_subcommittee_size * subcommittee_index + index
                sync_aggregate.sync_committee_bits[participant_index] = Boolean(True)
        signatures.append(contribution.signature)

    # [Modified in PQ]
    sync_aggregate.sync_committee_signature = XMSSAggregateSignature(
        data=xmss.Aggregate(signatures)
    )

    block.body.sync_aggregate = sync_aggregate
```

##### Signed execution payload bid

For self-builds, the signature MUST be the empty `XMSSSignature()`, which is all
zero bytes, and the `bid.value` MUST be zero. All other conditions on
`signed_execution_payload_bid` are unchanged.

##### Execution requests

*Note*: The function `get_execution_requests` is modified to no longer parse PQ
registration requests.

```python
def get_execution_requests(execution_requests_list: Sequence[bytes]) -> ExecutionRequests:
    deposits = DepositRequests()
    withdrawals = WithdrawalRequests()
    consolidations = ConsolidationRequests()
    builder_deposits = BuilderDepositRequests()
    builder_exits = BuilderExitRequests()

    request_types = [
        DEPOSIT_REQUEST_TYPE,
        WITHDRAWAL_REQUEST_TYPE,
        CONSOLIDATION_REQUEST_TYPE,
        BUILDER_DEPOSIT_REQUEST_TYPE,
        BUILDER_EXIT_REQUEST_TYPE,
        # [Modified in PQ]
        # Removed `PQ_REGISTRATION_REQUEST_TYPE`
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

    return ExecutionRequests(
        deposits=deposits,
        withdrawals=withdrawals,
        consolidations=consolidations,
        builder_deposits=builder_deposits,
        builder_exits=builder_exits,
        # [Modified in PQ]
        # Removed `pq_registrations`
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

##### Aggregate signature

Set `attestation.signature = attestation_signature` where
`attestation_signature` is obtained from:

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
    leaf_index = compute_xmss_leaf_index(attestation_data.slot, LEAF_OFFSET_BEACON_ATTESTER)
    return xmss.Sign(privkey, leaf_index, signing_root)
```

### Attestation aggregation

#### Aggregation selection

*Note*: XMSS signatures are not unique. A validator can grind the randomizer of
its selection proof until `is_aggregator` selects it, which BLS uniqueness used
to prevent. This is an open issue.

```python
def get_slot_signature(
    state: BeaconState,
    slot: Slot,
    # [Modified in PQ]
    privkey: Bytes32,
) -> XMSSSignature:
    domain = get_domain(state, DOMAIN_SELECTION_PROOF, compute_epoch_at_slot(slot))
    signing_root = compute_signing_root(slot, domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(slot, LEAF_OFFSET_SELECTION_PROOF)
    return xmss.Sign(privkey, leaf_index, signing_root)
```

```python
def is_aggregator(
    state: BeaconState,
    slot: Slot,
    index: CommitteeIndex,
    # [Modified in PQ]
    slot_signature: XMSSSignature,
) -> bool:
    committee = get_beacon_committee(state, slot, index)
    modulo = max(1, len(committee) // TARGET_AGGREGATORS_PER_COMMITTEE)
    return bytes_to_uint64(sha256(slot_signature)[0:8]) % modulo == 0
```

#### Construct aggregate

##### Aggregate signature

Set `aggregate_attestation.signature = aggregate_signature` where
`aggregate_signature` is obtained from:

```python
def get_aggregate_signature(attestations: Sequence[Attestation]) -> XMSSAggregateSignature:
    signatures = [attestation.signature for attestation in attestations]
    # [Modified in PQ]
    return XMSSAggregateSignature(data=xmss.Aggregate(signatures))
```

#### Broadcast aggregate

```python
def get_aggregate_and_proof(
    state: BeaconState,
    aggregator_index: ValidatorIndex,
    aggregate: Attestation,
    # [Modified in PQ]
    privkey: Bytes32,
) -> AggregateAndProof:
    return AggregateAndProof(
        aggregator_index=aggregator_index,
        aggregate=aggregate,
        selection_proof=get_slot_signature(state, aggregate.data.slot, privkey),
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

#### Sync committee messages

##### Prepare sync committee message

```python
def get_sync_committee_message(
    state: BeaconState,
    block_root: Root,
    validator_index: ValidatorIndex,
    # [Modified in PQ]
    privkey: Bytes32,
) -> SyncCommitteeMessage:
    epoch = get_current_epoch(state)
    domain = get_domain(state, DOMAIN_SYNC_COMMITTEE, epoch)
    signing_root = compute_signing_root(block_root, domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(state.slot, LEAF_OFFSET_SYNC_COMMITTEE)
    signature = xmss.Sign(privkey, leaf_index, signing_root)

    return SyncCommitteeMessage(
        slot=state.slot,
        beacon_block_root=block_root,
        validator_index=validator_index,
        signature=signature,
    )
```

#### Sync committee contributions

##### Aggregation selection

*Note*: As with `is_aggregator`, a validator can grind its selection proof until
`is_sync_committee_aggregator` selects it. This is an open issue.

```python
def get_sync_committee_selection_proof(
    state: BeaconState,
    slot: Slot,
    subcommittee_index: Uint64,
    # [Modified in PQ]
    privkey: Bytes32,
) -> XMSSSignature:
    domain = get_domain(state, DOMAIN_SYNC_COMMITTEE_SELECTION_PROOF, compute_epoch_at_slot(slot))
    signing_data = SyncAggregatorSelectionData(
        slot=slot,
        subcommittee_index=subcommittee_index,
    )
    signing_root = compute_signing_root(signing_data, domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(
        slot, LEAF_OFFSET_SYNC_COMMITTEE_SELECTION_PROOF + subcommittee_index
    )
    return xmss.Sign(privkey, leaf_index, signing_root)
```

```python
def is_sync_committee_aggregator(
    # [Modified in PQ]
    signature: XMSSSignature,
) -> bool:
    modulo = max(
        1,
        SYNC_COMMITTEE_SIZE
        // SYNC_COMMITTEE_SUBNET_COUNT
        // TARGET_AGGREGATORS_PER_SYNC_SUBCOMMITTEE,
    )
    return bytes_to_uint64(sha256(signature)[0:8]) % modulo == 0
```

##### Construct sync committee contribution

###### Signature

Set `contribution.signature = aggregate_signature` where `aggregate_signature`
is obtained by assembling the appropriate collection of `XMSSSignature`s from
the set of `sync_committee_messages` and wrapping the result of
`xmss.Aggregate()` in an `XMSSAggregateSignature`.

##### Broadcast sync committee contribution

```python
def get_contribution_and_proof(
    state: BeaconState,
    aggregator_index: ValidatorIndex,
    contribution: SyncCommitteeContribution,
    # [Modified in PQ]
    privkey: Bytes32,
) -> ContributionAndProof:
    selection_proof = get_sync_committee_selection_proof(
        state,
        contribution.slot,
        contribution.subcommittee_index,
        privkey,
    )
    return ContributionAndProof(
        aggregator_index=aggregator_index,
        contribution=contribution,
        selection_proof=selection_proof,
    )
```

```python
def get_contribution_and_proof_signature(
    state: BeaconState,
    contribution_and_proof: ContributionAndProof,
    # [Modified in PQ]
    privkey: Bytes32,
) -> XMSSSignature:
    contribution = contribution_and_proof.contribution
    domain = get_domain(
        state, DOMAIN_CONTRIBUTION_AND_PROOF, compute_epoch_at_slot(contribution.slot)
    )
    signing_root = compute_signing_root(contribution_and_proof, domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(
        contribution.slot, LEAF_OFFSET_CONTRIBUTION_AND_PROOF + contribution.subcommittee_index
    )
    return xmss.Sign(privkey, leaf_index, signing_root)
```

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
