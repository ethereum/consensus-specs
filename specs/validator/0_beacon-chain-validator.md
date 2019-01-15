# Ethereum 2.0 Phase 0 -- Honest Validator

__NOTICE__: This document is a work-in-progress for researchers and implementers. This is an accompanying document to [Ethereum 2.0 Phase 0 -- The Beacon Chain](https://github.com/ethereum/eth2.0-specs/blob/master/specs/core/0_beacon-chain.md) that describes the expected actions of a "validator" participating in the Ethereum 2.0 protocol.

## Table of Contents

## Introduction

This document represents the expected behavior of an "honest validator" with respect to Phase 0 of the Ethereum 2.0 protocol. This document does not distinguish between a "node" and a "validator client". The separation of concerns between these (potentially) two pieces of software is left as a design decision that is outside of scope.

A validator is an entity that participates in the consensus of the Ethereum 2.0 protocol. This is an optional role for users in which they can post ETH as collateral to seek financial returns in exchange for building and securing the protocol. This is similar to proof of work networks in which a miner provides collateral in the form of hardware/hash-power to seek returns in exchange for building and securing the protocol.

## Prerequisites

All terminology, constants, functions, and protocol mechanics defined in the [Phase 0 -- The Beacon Chain](https://github.com/ethereum/eth2.0-specs/blob/master/specs/core/0_beacon-chain.md) doc are requisite for this document and used throughout. Please see the Phase 0 doc before continuing and use as a reference throughout.

## Becoming a validator

### Initialization

A validator must initial many parameters locally before submitting a deposit and joining the validator registry.

#### BLS public key

Validator public keys are [G1 points](https://github.com/ethereum/eth2.0-specs/blob/master/specs/bls_signature.md#g1-points) on the [BLS12-381 curve](https://z.cash/blog/new-snark-curve). A private key, `privkey`, must be securely generated along with the resultant `pubkey`. This `privkey` must be "hot", that is, constantly available to sign data throughout the lifetime of the validator.

#### BLS withdrawal key

A secondary withdrawal private key, `withdrawal_privkey`, must also be securely generated along with the resultant `withdrawal_pubkey`. This `withdrawal_privkey` does not have to be available for signing during the normal lifetime of a validator and can live in "cold storage".

The validator constructs their `withdrawal_credentials` through the following:
* Set `withdrawal_credentials[:1] == BLS_WITHDRAWAL_PREFIX_BYTE`.
* Set `withdrawal_credentials[1:] == hash(withdrawal_pubkey)[1:]`.

#### RANDAO commitment

A validator's RANDAO commitment is the outermost layer of a 32-byte hash-onion. To create this commitment, perform the following steps:

* Randomly generate a 32-byte `randao_seed`.
* Store this `randao_seed` in a secure location.
* Calculate `randao_commitment = repeat_hash(randao_seed, n)` where `n` is large enough such that within the lifetime of the validator, the validator will not propose more than `n` beacon chain blocks.

Assuming `>= 100k validators`, on average a validator will have an opportunity to reveal once every `>= 600k seconds`, so `<= 50 times per year`. At this estimate, `n == 5000` would last a century. To be conservative, we recommend `n >= 100k`.

_Note_: A validator must be able to reveal the next layer deep from their current commitment at any time. There are many strategies that trade off space and computation to be able to provide this reveal. At one end of this trade-off, a validator might only store their `randao_seed` and repeat the `repeat_hash` calculation on the fly to re-calculate the layer `n-1` for the reveal. On the other end of this trade-off, a validator might store _all_ layers of the hash-onion and not have to perform any calculations to retrieve the layer `n-1`. A more sensible strategy might be to store every `m`th layer as cached references to recalculate the intermittent layers as needed.

#### Custody commitment

A validator's custody commitment is the outermost layer of a 32-byte hash-onion. To create this commitment, perform the following steps:

* Randomly generate a 32-byte `custody_seed`.
* Store this `custody_seed` in a secutre location.
* Calculate `custody_commitment = repeat_hash(custody_seed, n)` where `n` is large enough such that within the lifetime of the validator, the validator will not attest to more than `n` beacon chain blocks.

Assuming a validator changes their `custody_seed` with frequency `>= 1 week`, the validator changes their seed approximately `<= 50 times per year`. At this estimate, `n == 5000` would last a century. To be conservative, we recommend `n >= 100k`.

See above note on hash-onion caching strategies in [RANDAO commitment]().

_Note_: although this commitment is being committed to and stored in phase 0, it will not be used until phase 1.

### Deposit

In phase 0, all incoming validator deposits originate from the Ethereum 1.0 PoW chain. Deposits are made to the [deposit contract](https://github.com/ethereum/eth2.0-specs/blob/master/specs/core/0_beacon-chain.md#ethereum-10-deposit-contract) located at `DEPOSIT_CONTRACT_ADDRESS`. 

To submit a deposit:

* Pack the validator's [initialization parameters]() into `deposit_input`, a [`DepositInput`](https://github.com/ethereum/eth2.0-specs/blob/master/specs/core/0_beacon-chain.md#depositinput) object.
* Set `deposit_input.proof_of_possession = EMPTY_SIGNATURE`.
* Let `proof_of_possession` be the result of `bls_sign` of the `hash_tree_root(deposit_input)` with `domain=DOMAIN_DEPOSIT`.
* Set `deposit_input.proof_of_possession = proof_of_possession`.
* Send a transaction on the Ethereum 1.0 chain to `DEPOSIT_CONTRACT_ADDRESS` executing `deposit` along with `deposit_input` as the singular `bytes` input along with a deposit `amount` in ETH.

### Validator index

Once a validator has been added to the state's `validator_registry`, the validator's `validator_index` is defined by the index into the registry at which the [`ValidatorRecord`]() contains the `pubkey` specified in the validator's deposit. This `validator_index` is used throughout the specification to dictate validator roles and responsibilities at any point and should be stored locally.

### Activation

A validator is activated some amount of slots after being added to the registry. There is a maximum validator churn per finalized epoch so the delay until activation is variable depending upon finality, total active validator balance, and the number of validators in the queue to be activated.

The function [`is_active_validator`](https://github.com/ethereum/eth2.0-specs/blob/master/specs/core/0_beacon-chain.md#is_active_validator) can be used to check if a validator is active at a given slot. Usage is as follows:

```python
validator = state.validator_registry[validator_index]
is_active_validator(validator, slot)
```

Once a validator is active, the validator is assigned [responsibilities]() until exited.

## Beacon chain responsibilities

A validator has two primary responsibilities to the beacon chain -- [proposing blocks]() and [creating attestations](). Proposals happen infrequently, whereas attestations should be created once per epoch.

### Block proposal

A validator is expected to propose a [`BeaconBlock`](https://github.com/ethereum/eth2.0-specs/blob/master/specs/core/0_beacon-chain.md#beaconblock) at the beginning of any slot during which `get_beacon_proposer_index(state, slot)` returns the validator's `validator_index`. To propose, the validator selects the `BeaconBlock`, `parent`, that in their view of the fork choice is the head of the chain during `slot`. The validator is to create, sign, and broadcast a `block` that is a child of `parent` that creates a valid [beacon chain state transition](https://github.com/ethereum/eth2.0-specs/blob/master/specs/core/0_beacon-chain.md#beacon-chain-state-transition-function).

#### Block header

##### Slot

Set `block.slot = slot` where `slot` is the current slot at which the validator has been selected to propose. The `parent` selected must satisfy that `parent.slot < block.slot`.

_Note:_ there might be "skipped" slots between the `parent` and `block`. These skipped slots are processed in the state transition function without per-block processing.

##### Parent root

Set `block.parent_root = hash_tree_root(parent)`.

##### State root

Set `block.state_root = hash_tree_root(state)` of the resulting `state` of the `parent -> block` state transition.

_Note_: To calculate `state_root`, the validator should first run the state transition function on an unsigned `block` containing a stub for the `state_root`. It is useful to be able to run a state transition function that does _not_ validate signatures for this purpose.

##### Randao reveal

Set `block.randao_reveal` to the `n`th layer deep reveal from the validator's current `randao_commitment` where `n = validator.randao_layers + 1`. `block.randao_reveal` should satisfy `repeat_hash(block.randao_reveal, validator.randao_layers + 1) == validator.randao_commitment`.

##### Deposit root

##### Signature

Set `block.signature = signed_proposal_data` where `signed_proposal_data` is defined as:

```python
proposal_data = ProposalSignedData(
    slot=slot,
    shard=BEACON_CHAIN_SHARD_NUMBER,
    block_root=hash_tree_root(block),  # where `block.sigature == EMPTY_SIGNATURE
)
proposal_root = hash_tree_root(proposal_data)

signed_proposal_data = bls_sign(
    privkey=validator.privkey,  # privkey store locally, not in state
    message=proposal_root,
    domain=get_domain(
        state.fork_data,  # `state` is the resulting state of `block` transition
        state.slot,
        DOMAIN_PROPOSAL,
    )
)
```

#### Block body

##### Proposer slashings

##### Casper slashings

##### Attestations

Up to `MAX_ATTESTATIONS` aggregate attestations can be added to the `block`. The attestations added must satify the verification conditions found in [attestation processing](https://github.com/ethereum/eth2.0-specs/blob/master/specs/core/0_beacon-chain.md#attestations-1). To maximize profit, the validator should attempt to add aggregate attestations that include the most available that have not previously been added on chain.

##### Deposits

##### Exits

### Attestations

A validator is expected to create, sign, and broadcast an attestion during each epoch. The slot during which the validator performs this roal is any slot at which `get_shard_committees_at_slot(state, slot)` contains a committee that contains `validator_index`.

A validator should create and broadcast the attestation halfway through the `slot` during which the validator is assigned -- that is `SLOT_DURATION * 0.5` seconds after the start of `slot`.

#### Attestation data

First the validator should construct `attestation_data`, an [`AttestationData`](https://github.com/ethereum/eth2.0-specs/blob/master/specs/core/0_beacon-chain.md#attestationdata) object based upon the state at the assigned slot.

##### Slot

Set `attestation_data.slot = slot` where `slot` is the current slot of which the validator is a member of a committee.

##### Shard

Set `attestation_data.shard = shard` where `shard` is the shard associated with the validator's committee defined by `get_shard_committees_at_slot`.

##### Beacon block root

Set `attestation_data.beacon_block_root = hash_tree_root(head)` where `head` is the validator's view of the `head` block of the beacon chain during `slot`.

##### Epoch boundary root

Set `attestation_data.epoch_boundary_root = hash_tree_root(epoch_boundary)` where `epoch_boundary` is the block at the most recent epoch boundary in the chain defined by `head` -- i.e. the `BeaconBlock` with `slot == head.slot - head.slot % EPOCH_LENGTH`.

_Note:_ This can be looked up in the state using `get_block_root(state, head.slot - head.slot % EPOCH_LENGTH)`.

##### Shard block root

Set `attestation_data.shard_block_root = ZERO_HASH`.

_Note:_ This is a stub for phase 0.

##### Latest crosslink root

Set `attestation_data.latest_crosslink_root = state.latest_crosslinks[shard].shard_block_root` where `state` is the beacon state at `head` and `shard` is the validator's assigned shard.

##### Justified slot

Set `attestation_data.justified_slot = state.justified_slot` where `state` is the beacon state at `head`.

##### Justified block root

Set `attestation_data.justified_block_root = hash_tree_root(justified_block)` where `justified_block` is the block at `state.justified_slot` in the chain defined by `head`.

_Note:_ This can be looked up in the state using `get_block_root(state, justified_slot)`.

#### Construct attestation

Next the validator creates `attestation`, an [`Attestation`](https://github.com/ethereum/eth2.0-specs/blob/master/specs/core/0_beacon-chain.md#attestation) object.

##### Data

Set `attestation.data = attestation_data` where `attestation_data` is the `AttestationData` object defined in the [previous section]().

##### Participation bitfield

* Let `participation_bitfield` be a byte array filled with zeros of length `(len(committee) + 7) // 8`.
* Let `index_into_committee` be the index into the validator's `committee` at which `validator_index` is located.
* Set `participation_bitfield[index_into_committee // 8] |= 2 ** (index_into_committee % 8)`.
* Set `attestation.participation_bitfield = participation_bitfield`.

_Note_: Calling `get_attestation_participants(state, attestation.data, attestation.participation_bitfield)` should return `[validator_index]`.

##### Custody bitfield

* Let `custody_bitfield` be a byte array filled with zeros of length `(len(committee) + 7) // 8`.
* Set `attestation.custody_bitfield = custody_bitfield`.

_Note:_ This is a stub for phase 0.

##### Aggregate signature

Set `attestation.aggregate_signature = signed_attestation_data` where `signed_attestation_data` is defined as:

```python
attestation_data_and_custody_bit = AttestationDataAndCustodyBit(
    attestation.data,
    False,
)
attestation_message_to_sign = hash_tree_root(attestation_data_and_custody_bit)

signed_attestation_data = bls_sign(
    privkey=validator.privkey,  # privkey store locally, not in state
    message=attestation_message_to_sign,
    domain=get_domain(
        state.fork_data,  # `state` is the state at `head`
        state.slot,
        DOMAIN_ATTESTATION,
    )
)
```

## How to avoid slashing

"Slashing" is the burning of some amount of validator funds and immediate ejection from the active validator set. In Phase 0, there are two ways in which funds can be slashed -- [proposal slashing]() and [attestation slashing](). Although being slashed has serious repercussions, it is simple enough to avoid being slashed all together by remaining _consistent_ with respect to the messages you have previously signed.

_Note_: signed data must be within the same `ForkData` context to conflict. Messages cannot be slashed across forks.

### Proposal slashing

To avoid "proposal slashings", a validator must not sign two conflicting [`ProposalSignedData`]() (suggest renaming `ProposalData`) where conflicting is defined as having the same `slot` and `shard` but a different `block_root`.

The following helper can be run to check if two proposal messages conflict:

```python
def proposal_data_is_slashable(proposal_data_1: ProposalSignedData,
                               proposal_data_2: ProposalSignedData) -> bool:
    if (proposal_data_1.slot != proposal_data_2.slot):
        return False
    if (proposal_data_1.shard != proposal_data_2.shard):
        return False
        
    return proposal_data_1.block_root != proposal_data_2.block_root
```

### Casper slashing

To avoid "Casper slashings", a validator must not sign two conflicting [`AttestationData`]() objects where conflicting is defined as a set of two attestations that satisfy either [`is_double_vote`]() or [`is_surround_vote`]().
