# EIP-8450 -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Registering post-quantum keys](#registering-post-quantum-keys)
  - [Generating the keys](#generating-the-keys)
  - [Leaf index rules](#leaf-index-rules)
  - [Constructing the registration](#constructing-the-registration)
  - [Replacing keys](#replacing-keys)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block and sidecar proposal](#block-and-sidecar-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [Post-quantum key registrations](#post-quantum-key-registrations)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
validator" to implement EIP-8450.

## Prerequisites

This document is an extension of the
[Heze -- Honest Validator](../../heze/validator.md) guide. All behaviors and
definitions defined in this document, and documents it extends, carry over
unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the
updated [beacon-chain specifications of EIP-8450](./beacon-chain.md) are
requisite for this document and used throughout. Please see related beacon-chain
specifications before continuing and use them as a reference throughout.

## Registering post-quantum keys

Registration is optional in this upgrade: the registered keys are dormant, and
every duty is still authenticated with BLS. A validator registers its keys at
any time after the EIP-8450 fork, once its deposit has been processed and it has
a validator index.

### Generating the keys

The validator generates a leanXMSS key and a VRF tree. The leanXMSS secret key
is a 32-byte seed. Key derivation and signing use the following functions, which
are not consensus-critical:

- `def xmss.SkToPk(secret_key: Bytes32) -> XMSSPublicKey`: derive the public key
  of `secret_key`.
- `def xmss.Sign(secret_key: Bytes32, message: Bytes32, index: Uint32) -> XMSSSignature`:
  sign `message` at leaf index `index`.

The leanXMSS seed and the VRF leaf secrets should not be derived from the
validator's BLS key. A validator should check its VRF tree before registering
its root, since the root is not checked at registration.

### Leaf index rules

A signer must never sign twice at the same leaf index of a key, and chooses how
it allocates leaf indices to messages. Signing is not assumed to be
deterministic, so signing the same message twice at one leaf index is also a
reuse. Leaf index `PQ_POSSESSION_XMSS_INDEX` is reserved for the proof of
possession: a signer must not sign at it anything other than the
`PQKeyPossession` of its key for the BLS public key of its validator or builder.
A signer must use each leanXMSS key in at most one registration, for one
validator or builder, and must not register a key that it has registered before.
Its proof is therefore signed once. Consensus does not record earlier keys, so
returning to an earlier key, or registering a key that another validator or
builder has released, is valid on chain. Returning to an earlier key needs
either a second proof at leaf `PQ_POSSESSION_XMSS_INDEX` or the stored first
one. Taking a key that another registrant released needs a proof of a different
message at that leaf, unless the two registrants share a BLS public key, in
which case the released key's stored proof applies. A validator and a builder
may share a BLS public key, since they enter through different deposit paths.
Uniqueness only keeps them from holding one leanXMSS key at once, and the signer
rules forbid all of these, so a signer never has to keep old proofs.

### Constructing the registration

The validator assembles a `PQKeyRegistration` holding its own validator index as
`index`, its keys, and its current entry of
`state.post_quantum_key_change_epochs` as `previous_change_epoch`. It attaches
its proof of possession of the leanXMSS key, signs the registration with its
**signing key**, and broadcasts the resulting `SignedPQKeyRegistration` on the
`pq_key_registration` global topic.

Consensus rejects a leanXMSS key that a validator or builder currently holds,
including the validator itself, so a change of the VRF root alone also needs a
new leanXMSS key. The proof is produced once per key with the function below. A
registration that is not included, for example because its block is orphaned,
stays in the operation pools and is included later with the same bytes. It is
never signed again.

```python
def get_pq_possession_proof(
    state: BeaconState, pubkey: BLSPubkey, xmss_secret_key: Bytes32
) -> XMSSSignature:
    xmss_public_key = xmss.SkToPk(xmss_secret_key)
    possession = PQKeyPossession(pubkey=pubkey, xmss_public_key=xmss_public_key)
    domain = compute_domain(
        DOMAIN_PQ_KEY_POSSESSION,
        GENESIS_FORK_VERSION,
        state.genesis_validators_root,
    )
    signing_root = compute_signing_root(possession, domain)
    return xmss.Sign(xmss_secret_key, signing_root, PQ_POSSESSION_XMSS_INDEX)
```

```python
def get_pq_key_registration_signature(
    state: BeaconState, registration: PQKeyRegistration, privkey: int
) -> BLSSignature:
    domain = compute_domain(
        DOMAIN_PQ_KEY_REGISTRATION,
        GENESIS_FORK_VERSION,
        state.genesis_validators_root,
    )
    signing_root = compute_signing_root(registration, domain)
    return bls.Sign(privkey, signing_root)
```

A registration names the validator's last change, so it becomes invalid once any
other registration for the validator is included. A validator that changes its
keys again must wait `MIN_PQ_KEY_CHANGE_DELAY` epochs after the last change, and
build a new registration against the updated `previous_change_epoch`.

### Replacing keys

A validator that loses its leanXMSS seed, its signer state, or its VRF secrets,
or finds a fault in its keys, registers new keys through the same operation. It
does not need to exit.

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below.

### Block and sidecar proposal

#### Constructing the `BeaconBlockBody`

##### Post-quantum key registrations

Up to `MAX_PQ_KEY_REGISTRATIONS`,
[`SignedPQKeyRegistration`](./beacon-chain.md#signedpqkeyregistration) objects
can be included in the `block`. The registrations must satisfy the verification
conditions found in
[post-quantum key registration processing](./beacon-chain.md#new-process_pq_key_registration).

*Note*: Registrations are processed after every other operation of the block, so
the proposer checks them against the state that results from the other
operations, including the parent's execution requests.
