# EIP-8321 -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Registering a RANDAO commitment](#registering-a-randao-commitment)
  - [Generating the hash chain](#generating-the-hash-chain)
  - [Constructing and broadcasting the registration](#constructing-and-broadcasting-the-registration)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block and sidecar proposal](#block-and-sidecar-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [Modified randao reveal](#modified-randao-reveal)
      - [New hash chain reveal](#new-hash-chain-reveal)
      - [New RANDAO commitment registrations](#new-randao-commitment-registrations)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
validator" to implement EIP-8321.

## Prerequisites

This document is an extension of the
[Heze -- Honest Validator](../../heze/validator.md) guide. All behaviors and
definitions defined in this document, and documents it extends, carry over
unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the
updated [beacon-chain specifications of EIP-8321](./beacon-chain.md) are
requisite for this document and used throughout. Please see related beacon-chain
specifications before continuing and use them as a reference throughout.

## Registering a RANDAO commitment

A validator reveals from a hash chain only once it has registered a commitment.
Until then it stays on the legacy BLS reveal path, so registration is optional
and can be performed at any time after the EIP-8321 fork.

*Warning*: A commitment can be registered once and can never be updated in
place. A validator that loses its chain secret, or registers a commitment whose
chain it does not hold, can no longer propose on the hash-chain path and must
exit and re-enter to obtain a fresh chain. The chain secret should be guarded
with the same custody standards as the signing key, and should not be derived
from it: a hash chain eventually reveals its seed, whereas a signing key must
never be revealed.

### Generating the hash chain

The validator draws a uniformly random 32-byte chain secret and generates a
chain of `length` links from it. Reveals are consumed in reverse order, one per
block proposed, so the chain must be long enough to outlast the validator; a
`length` of at least `2**16` is recommended. The protocol never learns `length`,
and generating and storing a chain is cheap, so a generous value costs nothing.

```python
def compute_hash_chain(chain_secret: Bytes32, length: Uint64) -> Sequence[Bytes32]:
    """
    Return the hash chain ``[c_0, ..., c_length]`` generated from
    ``chain_secret``, where ``c_0`` is the secret itself.
    """
    chain = [chain_secret]
    for _ in range(length):
        chain.append(blake3(HASH_CHAIN_RANDAO_DST + chain[-1]))
    # A zero link marks an unregistered validator and cannot be revealed, so
    # the chain must be regenerated from a fresh secret if one occurs
    assert all(value != Bytes32() for value in chain)
    return chain
```

The validator commits to the tip of the chain, `chain[length]`, and stores the
chain locally (or the chain secret plus periodic checkpoints, if the chain is
large). It should verify the commitment by walking the full chain before
registering.

### Constructing and broadcasting the registration

The validator assembles a `RandaoCommitmentRegistration` holding its own
`validator_index` and the chain tip as `commitment`, signs it with its **signing
key**, and broadcasts the resulting `SignedRandaoCommitmentRegistration` on the
`randao_commitment_registration` global topic.

```python
def get_randao_commitment_registration_signature(
    state: BeaconState, registration: RandaoCommitmentRegistration, privkey: int
) -> BLSSignature:
    domain = compute_domain(
        DOMAIN_RANDAO_COMMITMENT_REGISTRATION,
        genesis_validators_root=state.genesis_validators_root,
    )
    signing_root = compute_signing_root(registration, domain)
    return bls.Sign(privkey, signing_root)
```

The registration is queued when it is included in a block and takes effect
`COMMITMENT_REGISTRATION_DELAY` epochs later. Activation is a property of the
canonical state, not of the validator's broadcast history: if the including
block is orphaned, the pending entry never enters the canonical queue. The
message stays valid in that case and remains includable, so it should be
retained in the operation pool.

*Note*: A validator **MUST** keep producing legacy BLS reveals until
`state.randao_commitments[validator_index]` is non-zero in the state it proposes
against, even if it has observed its registration included in some block.

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below.

### Block and sidecar proposal

#### Constructing the `BeaconBlockBody`

##### Modified randao reveal

*Note*: The function `get_epoch_signature` is modified to return the point at
infinity once the proposer has an active commitment, since the hash-chain reveal
replaces the signature.

```python
def get_epoch_signature(state: BeaconState, block: BeaconBlock, privkey: int) -> BLSSignature:
    # [New in EIP8321]
    if state.randao_commitments[block.proposer_index] != Bytes32():
        return G2_POINT_AT_INFINITY
    domain = get_domain(state, DOMAIN_RANDAO, compute_epoch_at_slot(block.slot))
    signing_root = compute_signing_root(compute_epoch_at_slot(block.slot), domain)
    return bls.Sign(privkey, signing_root)
```

##### New hash chain reveal

Set `block.body.hash_chain_reveal = hash_chain_reveal` where `hash_chain_reveal`
is obtained from:

```python
def get_hash_chain_reveal(
    state: BeaconState, block: BeaconBlock, chain: Sequence[Bytes32]
) -> Bytes32:
    """
    Return the next hash-chain reveal for the proposer of ``block``, where
    ``chain`` is the proposer's locally stored hash chain.

    The reveal is the preimage of the commitment currently stored in the state,
    and is empty while the proposer has no commitment registered.
    """
    commitment = state.randao_commitments[block.proposer_index]
    if commitment == Bytes32():
        return Bytes32()

    index = chain.index(commitment)
    # The chain is exhausted once its commitment reaches the chain secret, whose
    # preimage the validator does not hold
    assert index > 0
    return chain[index - 1]
```

##### New RANDAO commitment registrations

Up to `MAX_RANDAO_COMMITMENT_REGISTRATIONS`,
[`SignedRandaoCommitmentRegistration`](./beacon-chain.md#signedrandaocommitmentregistration)
objects can be included in the `block`. The registrations must satisfy the
verification conditions found in
[RANDAO commitment registration processing](./beacon-chain.md#new-process_randao_commitment_registration).

*Note*: A node *should* prioritize locally received
`SignedRandaoCommitmentRegistration` operations to ensure these registrations
make it on-chain through self published blocks even if the rest of the network
censors.
