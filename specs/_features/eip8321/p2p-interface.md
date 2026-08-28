# EIP-8321 -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [Modified `Seen`](#modified-seen)
  - [Modified `compute_fork_version`](#modified-compute_fork_version)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)
    - [Global topics](#global-topics)
      - [Modified `beacon_block`](#modified-beacon_block)
      - [New `randao_commitment_registration`](#new-randao_commitment_registration)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for
EIP-8321.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

## Helpers

### Modified `Seen`

```python
@dataclass
class Seen:
    proposer_slots: Set[Tuple[Slot, ValidatorIndex]]
    aggregator_epochs: Set[Tuple[Epoch, ValidatorIndex]]
    aggregate_data_roots: Dict[Tuple[Root, CommitteeIndex], Set[Tuple[bool, ...]]]
    voluntary_exit_indices: Set[ValidatorIndex]
    proposer_slashing_indices: Set[ValidatorIndex]
    attester_slashing_indices: Set[ValidatorIndex]
    attestation_validator_epochs: Set[Tuple[Epoch, ValidatorIndex]]
    sync_contribution_aggregator_slots: Set[Tuple[Slot, ValidatorIndex, Uint64]]
    sync_contribution_data: Dict[Tuple[Slot, Root, Uint64], Set[Tuple[bool, ...]]]
    sync_message_validator_slots: Set[Tuple[Slot, ValidatorIndex, Uint64]]
    bls_to_execution_change_indices: Set[ValidatorIndex]
    data_column_sidecar_tuples: Set[Tuple[Root, ColumnIndex]]
    execution_payloads: Dict[Hash32, ExecutionPayload]
    execution_payload_envelopes: Set[Tuple[Root, BuilderIndex]]
    payload_attestation_validators: Set[Tuple[Slot, ValidatorIndex]]
    execution_payload_bids: Set[Tuple[Slot, Hash32, Root, BuilderIndex]]
    best_execution_payload_bid: Dict[Tuple[Slot, Hash32, Root], Gwei]
    proposer_preferences: Dict[Tuple[Slot, Root], ProposerPreferences]
    # [New in EIP8321]
    randao_commitment_registration_indices: Set[ValidatorIndex]
```

### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= EIP8321_FORK_EPOCH:
        return EIP8321_FORK_VERSION
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

## The gossip domain: gossipsub

### Topics and messages

Topics follow the same specification as in prior upgrades. All existing topics
remain stable except the beacon block topic, which is updated with the modified
type.

The new topic along with the type of the `data` field of a gossipsub message is
given in this table:

| Name                             | Message Type                         |
| -------------------------------- | ------------------------------------ |
| `beacon_block`                   | `SignedBeaconBlock` (modified)       |
| `randao_commitment_registration` | `SignedRandaoCommitmentRegistration` |

#### Global topics

EIP-8321 changes the type of the global beacon block topic and adds one global
topic to propagate RANDAO commitment registrations to all potential proposers of
beacon blocks.

##### Modified `beacon_block`

The *type* of the payload of this topic changes to the (modified)
`SignedBeaconBlock` found in EIP-8321. Specifically, this type changes with the
addition of `hash_chain_reveal` and `randao_commitment_registrations` to the
inner `BeaconBlockBody`. See the EIP-8321
[state transition document](./beacon-chain.md#beaconblockbody) for further
details.

##### New `randao_commitment_registration`

The `randao_commitment_registration` topic is used solely for propagating signed
RANDAO commitment registrations on the network. Signed messages are sent in
their entirety.

```python
def validate_randao_commitment_registration_gossip(
    seen: Seen,
    store: Store,
    signed_registration: SignedRandaoCommitmentRegistration,
) -> None:
    """
    Validate a SignedRandaoCommitmentRegistration for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    registration = signed_registration.message
    index = registration.validator_index
    state = store.block_states[get_head(store).root]

    # [IGNORE] The head state has upgraded to EIP-8321
    if state.fork.current_version < EIP8321_FORK_VERSION:
        raise GossipIgnore("head state is pre-eip8321")

    # [REJECT] The validator index is valid
    if index >= len(state.validators):
        raise GossipReject("validator index out of range")

    # [IGNORE] This is the first valid registration received for the validator
    if index in seen.randao_commitment_registration_indices:
        raise GossipIgnore("already seen RANDAO commitment registration for this validator")

    # [REJECT] The commitment is non-zero
    if registration.commitment == UNSET_RANDAO_COMMITMENT:
        raise GossipReject("commitment is zero")

    # [IGNORE] The validator is not registered yet
    if state.randao_commitments[index] != UNSET_RANDAO_COMMITMENT:
        raise GossipIgnore("validator is already registered")

    # [IGNORE] The validator has no registration pending in the node's view
    if any(pending.validator_index == index for pending in state.pending_randao_commitments):
        raise GossipIgnore("RANDAO commitment registration is already pending for this validator")

    # [REJECT] The signature is valid
    domain = compute_domain(
        DOMAIN_RANDAO_COMMITMENT_REGISTRATION,
        genesis_validators_root=state.genesis_validators_root,
    )
    signing_root = compute_signing_root(registration, domain)
    if not bls.Verify(state.validators[index].pubkey, signing_root, signed_registration.signature):
        raise GossipReject("invalid RANDAO commitment registration signature")

    # Mark this registration as seen
    seen.randao_commitment_registration_indices.add(index)
```
