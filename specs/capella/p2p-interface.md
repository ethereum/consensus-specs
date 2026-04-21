# Capella -- Networking

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modifications in Capella](#modifications-in-capella)
  - [Helpers](#helpers)
    - [Modified `Seen`](#modified-seen)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [`beacon_block`](#beacon_block)
        - [`bls_to_execution_change`](#bls_to_execution_change)
    - [Transitioning the gossip](#transitioning-the-gossip)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [BeaconBlocksByRange v2](#beaconblocksbyrange-v2)
      - [BeaconBlocksByRoot v2](#beaconblocksbyroot-v2)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for
Capella.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

## Modifications in Capella

### Helpers

#### Modified `Seen`

```python
@dataclass
class Seen(object):
    proposer_slots: Set[Tuple[ValidatorIndex, Slot]]
    aggregator_epochs: Set[Tuple[ValidatorIndex, Epoch]]
    aggregate_data_roots: Dict[Root, Set[Tuple[boolean, ...]]]
    voluntary_exit_indices: Set[ValidatorIndex]
    proposer_slashing_indices: Set[ValidatorIndex]
    attester_slashing_indices: Set[ValidatorIndex]
    attestation_validator_epochs: Set[Tuple[ValidatorIndex, Epoch]]
    sync_contribution_aggregator_slots: Set[Tuple[ValidatorIndex, Slot, uint64]]
    sync_contribution_data: Dict[Tuple[Slot, Root, uint64], Set[Tuple[boolean, ...]]]
    sync_message_validator_slots: Set[Tuple[Slot, ValidatorIndex, uint64]]
    # [New in Capella]
    bls_to_execution_change_indices: Set[ValidatorIndex]
```

#### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= CAPELLA_FORK_EPOCH:
        return CAPELLA_FORK_VERSION
    if epoch >= BELLATRIX_FORK_EPOCH:
        return BELLATRIX_FORK_VERSION
    if epoch >= ALTAIR_FORK_EPOCH:
        return ALTAIR_FORK_VERSION
    return GENESIS_FORK_VERSION
```

### The gossip domain: gossipsub

A new topic is added to support the gossip of withdrawal credential change
messages. And an existing topic is upgraded for updated types in Capella.

#### Topics and messages

Topics follow the same specification as in prior upgrades. All existing topics
remain stable except the beacon block topic which is updated with the modified
type.

The new topics along with the type of the `data` field of a gossipsub message
are given in this table:

| Name                      | Message Type                   |
| ------------------------- | ------------------------------ |
| `beacon_block`            | `SignedBeaconBlock` (modified) |
| `bls_to_execution_change` | `SignedBLSToExecutionChange`   |

Note that the `ForkDigestValue` path segment of the topic separates the old and
the new `beacon_block` topics.

##### Global topics

Capella changes the type of the global beacon block topic and adds one global
topic to propagate withdrawal credential change messages to all potential
proposers of beacon blocks.

###### `beacon_block`

The *type* of the payload of this topic changes to the (modified)
`SignedBeaconBlock` found in Capella. Specifically, this type changes with the
addition of `bls_to_execution_changes` to the inner `BeaconBlockBody`. See
Capella [state transition document](./beacon-chain.md#beaconblockbody) for
further details.

###### `bls_to_execution_change`

The `bls_to_execution_change` topic is used solely for propagating signed BLS to
execution change (BTEC) messages on the network. Signed BTEC messages are sent
in their entirety. The `state` parameter is the head state.

```python
def validate_bls_to_execution_change_gossip(
    seen: Seen,
    state: BeaconState,
    signed_bls_to_execution_change: SignedBLSToExecutionChange,
    current_time_ms: uint64,
) -> None:
    """
    Validate a SignedBLSToExecutionChange for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    btec = signed_bls_to_execution_change.message
    validator_index = btec.validator_index

    # [IGNORE] The current epoch is at or after the Capella fork epoch
    # (where current_epoch is defined by the current wall-clock time)
    time_since_genesis_ms = current_time_ms - state.genesis_time * 1000
    current_slot = Slot(time_since_genesis_ms // SLOT_DURATION_MS)
    current_epoch = compute_epoch_at_slot(current_slot)
    if current_epoch < CAPELLA_FORK_EPOCH:
        raise GossipIgnore("current epoch is pre-capella")

    # [IGNORE] This is the first valid BTEC received for the validator
    if validator_index in seen.bls_to_execution_change_indices:
        raise GossipIgnore("already seen BLS to execution change for this validator")

    # [REJECT] The validator index is valid
    if validator_index >= len(state.validators):
        raise GossipReject("validator index out of range")

    validator = state.validators[validator_index]

    # [REJECT] The validator has BLS withdrawal credentials
    if validator.withdrawal_credentials[:1] != BLS_WITHDRAWAL_PREFIX:
        raise GossipReject("validator does not have BLS withdrawal credentials")

    # [REJECT] The BTEC is for the validator's withdrawal pubkey
    if validator.withdrawal_credentials[1:] != hash(btec.from_bls_pubkey)[1:]:
        raise GossipReject("pubkey does not match validator withdrawal credentials")

    # [REJECT] The signature is valid
    domain = compute_domain(
        DOMAIN_BLS_TO_EXECUTION_CHANGE, genesis_validators_root=state.genesis_validators_root
    )
    signing_root = compute_signing_root(btec, domain)
    if not bls.Verify(
        btec.from_bls_pubkey,
        signing_root,
        signed_bls_to_execution_change.signature,
    ):
        raise GossipReject("invalid BLS to execution change signature")

    # Mark this BTEC as seen
    seen.bls_to_execution_change_indices.add(validator_index)
```

#### Transitioning the gossip

See gossip transition details found in the
[Altair document](../altair/p2p-interface.md#transitioning-the-gossip) for
details on how to handle transitioning gossip topics for Capella.

### The Req/Resp domain

#### Messages

##### BeaconBlocksByRange v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/2/`

The Capella fork-digest is introduced to the `context` enum to specify Capella
block type.

<!-- eth_consensus_specs: skip -->

| `fork_version`           | Chunk SSZ type                |
| ------------------------ | ----------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock`   |

##### BeaconBlocksByRoot v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_root/2/`

The Capella fork-digest is introduced to the `context` enum to specify Capella
block type.

<!-- eth_consensus_specs: skip -->

| `fork_version`           | Chunk SSZ type                |
| ------------------------ | ----------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock`   |
