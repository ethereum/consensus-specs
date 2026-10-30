# EIP-8450 -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [Modified `Seen`](#modified-seen)
  - [Modified `compute_fork_version`](#modified-compute_fork_version)
  - [Modified `verify_block_body_operation_limits`](#modified-verify_block_body_operation_limits)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)
    - [Global topics](#global-topics)
      - [Modified `beacon_block`](#modified-beacon_block)
      - [New `pq_key_registration`](#new-pq_key_registration)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for
EIP-8450.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

## Helpers

### Modified `Seen`

```python
@dataclass
class Seen:
    proposer_slots: set[tuple[Slot, ValidatorIndex]]
    aggregator_epochs: set[tuple[Epoch, ValidatorIndex]]
    aggregate_data_roots: dict[tuple[Root, CommitteeIndex], set[tuple[bool, ...]]]
    voluntary_exit_indices: set[ValidatorIndex]
    proposer_slashing_indices: set[ValidatorIndex]
    attester_slashing_indices: set[ValidatorIndex]
    attestation_validator_epochs: set[tuple[Epoch, ValidatorIndex]]
    sync_contribution_aggregator_slots: set[tuple[Slot, ValidatorIndex, Uint64]]
    sync_contribution_data: dict[tuple[Slot, Root, Uint64], set[tuple[bool, ...]]]
    sync_message_validator_slots: set[tuple[Slot, ValidatorIndex, Uint64]]
    bls_to_execution_change_indices: set[ValidatorIndex]
    data_column_sidecar_tuples: set[tuple[Root, ColumnIndex]]
    execution_payloads: dict[Hash32, ExecutionPayload]
    execution_payload_envelopes: set[tuple[Root, BuilderIndex]]
    payload_attestation_validators: set[tuple[Slot, ValidatorIndex]]
    execution_payload_bids: set[tuple[Slot, Hash32, Root, BuilderIndex]]
    best_execution_payload_bid: dict[tuple[Slot, Hash32, Root], Gwei]
    proposer_preferences: dict[tuple[Slot, Root], ProposerPreferences]
    inclusion_list_counts: Counter[tuple[Slot, Root, ValidatorIndex]]
    # [New in EIP8450]
    pq_key_registration_tuples: set[tuple[ValidatorIndex, Epoch]]
```

### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= EIP8450_FORK_EPOCH:
        return EIP8450_FORK_VERSION
    if epoch >= HEZE_FORK_EPOCH:
        return HEZE_FORK_VERSION
    if epoch >= GLOAS_FORK_EPOCH:
        return GLOAS_FORK_VERSION
    if epoch >= FULU_FORK_EPOCH:
        return FULU_FORK_VERSION
    if epoch >= ELECTRA_FORK_EPOCH:
        return ELECTRA_FORK_VERSION
    if epoch >= DENEB_FORK_EPOCH:
        return DENEB_FORK_VERSION
    if epoch >= CAPELLA_FORK_EPOCH:
        return CAPELLA_FORK_VERSION
    if epoch >= BELLATRIX_FORK_EPOCH:
        return BELLATRIX_FORK_VERSION
    if epoch >= ALTAIR_FORK_EPOCH:
        return ALTAIR_FORK_VERSION
    return GENESIS_FORK_VERSION
```

### Modified `verify_block_body_operation_limits`

```python
def verify_block_body_operation_limits(body: BeaconBlockBody) -> None:
    """
    Verify that each block body operation count is within its limit.
    Raises GossipReject on validation failure.
    """
    # [REJECT] The proposer slashing count is within the limit
    if len(body.proposer_slashings) > MAX_PROPOSER_SLASHINGS:
        raise GossipReject("too many proposer slashings")

    # [REJECT] The attester slashing count is within the limit
    if len(body.attester_slashings) > MAX_ATTESTER_SLASHINGS_ELECTRA:
        raise GossipReject("too many attester slashings")

    # [REJECT] The attestation count is within the limit
    if len(body.attestations) > MAX_ATTESTATIONS_ELECTRA:
        raise GossipReject("too many attestations")

    # [REJECT] The voluntary exit count is within the limit
    if len(body.voluntary_exits) > MAX_VOLUNTARY_EXITS:
        raise GossipReject("too many voluntary exits")

    # [REJECT] The BLS to execution change count is within the limit
    if len(body.bls_to_execution_changes) > MAX_BLS_TO_EXECUTION_CHANGES:
        raise GossipReject("too many bls to execution changes")

    # [REJECT] The payload attestation count is within the limit
    if len(body.payload_attestations) > MAX_PAYLOAD_ATTESTATIONS:
        raise GossipReject("too many payload attestations")

    # [New in EIP8450]
    # [REJECT] The PQ key registration count is within the limit
    if len(body.pq_key_registrations) > MAX_PQ_KEY_REGISTRATIONS:
        raise GossipReject("too many pq key registrations")
```

## The gossip domain: gossipsub

### Topics and messages

Topics follow the same specification as in prior upgrades. All existing topics
remain stable except the beacon block topic, which is updated with the modified
type.

The new topic along with the type of the `data` field of a gossipsub message is
given in this table:

| Name                  | Message Type                   |
| --------------------- | ------------------------------ |
| `beacon_block`        | `SignedBeaconBlock` (modified) |
| `pq_key_registration` | `SignedPQKeyRegistration`      |

#### Global topics

EIP-8450 changes the type of the global beacon block topic and adds one global
topic to propagate post-quantum key registrations to all potential proposers of
beacon blocks.

##### Modified `beacon_block`

The *type* of the payload of this topic changes to the (modified)
`SignedBeaconBlock` found in EIP-8450. Specifically, this type changes with the
addition of `pq_key_registrations` to the inner `BeaconBlockBody`. See the
EIP-8450 [state transition document](./beacon-chain.md#beaconblockbody) for
further details.

##### New `pq_key_registration`

The `pq_key_registration` topic is used solely for propagating signed
post-quantum key registrations on the network. Signed messages are sent in their
entirety.

*Note*: A registration that was valid when first received can become invalid
before it is included, for example when the same leanXMSS key is registered for
another index first. The stored change epoch then does not change, so the
first-seen record would block every later registration for the pair. Nodes *may*
clear the record for a pair once its first-seen registration is no longer valid
against the finalized state.

*Note*: While the first-seen registration for a pair stays valid but is not
included, a different registration for the same pair, for example one that
corrects a faulty key, is ignored. A registrant that broadcasts a faulty key
replaces it once that registration is included and `MIN_PQ_KEY_CHANGE_DELAY`
epochs have passed.

```python
def validate_pq_key_registration_gossip(
    seen: Seen,
    store: Store,
    signed_registration: SignedPQKeyRegistration,
    current_time_ms: Uint64,
) -> None:
    """
    Validate a SignedPQKeyRegistration for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    registration = signed_registration.message
    index = registration.index
    key_material = registration.key_material

    # [IGNORE] The current epoch is at or after the EIP-8450 fork epoch
    if is_future_epoch(store, EIP8450_FORK_EPOCH, current_time_ms):
        raise GossipIgnore("current epoch is pre-eip8450")

    state = store.block_states[get_head(store).root]

    # [IGNORE] The head state is at or after the EIP-8450 fork, so that it has
    # the registry lists of EIP-8450
    if get_current_epoch(state) < EIP8450_FORK_EPOCH:
        raise GossipIgnore("head state is pre-eip8450")

    if is_builder_index(index):
        builder_index = convert_validator_index_to_builder_index(index)

        # [IGNORE] The builder index exists in the head state. A recently
        # deposited builder may not yet be in every node's head state.
        if builder_index >= len(state.builders):
            raise GossipIgnore("builder index out of range")

        builder = state.builders[builder_index]

        # [REJECT] The builder has not initiated an exit
        if builder.withdrawable_epoch != FAR_FUTURE_EPOCH:
            raise GossipReject("builder has initiated an exit")

        # [IGNORE] The builder's deposit epoch is finalized in the head state,
        # which depends on the node's view of finality
        if not is_active_builder(state, builder_index):
            raise GossipIgnore("builder deposit is not yet finalized")

        # [REJECT] The builder registers a zero VRF root
        if key_material.vrf_root != VRFRoot():
            raise GossipReject("builder VRF root is not zero")

        entry = state.builder_post_quantum_key_material[builder_index]
        last_change_epoch = state.builder_post_quantum_key_change_epochs[builder_index]
        pubkey = builder.pubkey
    else:
        # [IGNORE] The validator index exists in the head state. A recently
        # deposited validator may not yet be in every node's head state.
        if index >= len(state.validators):
            raise GossipIgnore("validator index out of range")

        # [REJECT] The validator has not initiated an exit
        validator = state.validators[index]
        if validator.exit_epoch != FAR_FUTURE_EPOCH:
            raise GossipReject("validator has initiated an exit")

        entry = state.post_quantum_key_material[index]
        last_change_epoch = state.post_quantum_key_change_epochs[index]
        pubkey = validator.pubkey

    # [IGNORE] This is the first valid registration received for the pair
    if (index, registration.previous_change_epoch) in seen.pq_key_registration_tuples:
        raise GossipIgnore("already seen post-quantum key registration for this pair")

    # [IGNORE] The registration applies to the current entry. A head that has not
    # yet seen the last change, or has seen a later one, holds another epoch.
    if registration.previous_change_epoch != last_change_epoch:
        raise GossipIgnore("previous change epoch does not match")

    # [IGNORE] Changes of registered keys are rate-limited
    if entry.xmss_public_key != XMSSPublicKey() and is_future_epoch(
        store, registration.previous_change_epoch + MIN_PQ_KEY_CHANGE_DELAY, current_time_ms
    ):
        raise GossipIgnore("post-quantum key change delay has not passed")

    # [REJECT] The leanXMSS key is not all-zero
    if key_material.xmss_public_key == XMSSPublicKey():
        raise GossipReject("leanXMSS key is all-zero")

    # [IGNORE] The leanXMSS key is not registered for any index. The holder of a
    # key can differ between heads.
    if is_pq_public_key_in_use(state, key_material.xmss_public_key):
        raise GossipIgnore("leanXMSS key is already registered")

    # [REJECT] The signature is valid
    domain = compute_domain(
        DOMAIN_PQ_KEY_REGISTRATION,
        GENESIS_FORK_VERSION,
        state.genesis_validators_root,
    )
    signing_root = compute_signing_root(registration, domain)
    if not bls.Verify(pubkey, signing_root, signed_registration.signature):
        raise GossipReject("invalid post-quantum key registration signature")

    # [REJECT] The proof of possession is valid
    if not is_valid_pq_possession_proof(
        state, pubkey, key_material.xmss_public_key, signed_registration.possession
    ):
        raise GossipReject("invalid proof of possession")

    # Mark this registration as seen
    seen.pq_key_registration_tuples.add((index, registration.previous_change_epoch))
```
