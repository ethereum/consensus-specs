# EIP-8450 -- Honest Builder

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Registering post-quantum keys](#registering-post-quantum-keys)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
builder" to implement EIP-8450.

## Registering post-quantum keys

Registration is optional in this upgrade: the registered key is dormant, and
every bid and envelope is still signed with BLS. A builder registers a leanXMSS
key once it is active, through the same operation, message, proof of possession,
and gossip topic as validators. Key generation, signing, and the leaf index
rules of the [validator guide](./validator.md#leaf-index-rules) apply unchanged,
with the builder's BLS public key in place of the validator's.

The builder assembles a `PQKeyRegistration` with:

- `index` set to `convert_builder_index_to_validator_index(builder_index)`.
- `key_material.xmss_public_key` set to a leanXMSS key that it has never
  registered before, and `key_material.vrf_root` set to `VRFRoot()`, since
  builders make no selection proofs.
- `previous_change_epoch` set to its current entry of
  `state.builder_post_quantum_key_change_epochs`, which is its deposit epoch
  until its first registration.

It attaches `get_pq_possession_proof(state, builder.pubkey, xmss_secret_key)`,
signs the registration with its BLS key using
`get_pq_key_registration_signature`, and broadcasts the resulting
`SignedPQKeyRegistration` on the `pq_key_registration` global topic.

*Note*: A builder index is reused once its builder has withdrawn, and the new
builder's entry starts at its own deposit epoch. Since
`MIN_BUILDER_WITHDRAWABILITY_DELAY` must be at least `1`, a registration signed
for an earlier builder at the same index names an earlier epoch and never
applies, even if the new builder has the same BLS key. A builder that re-enters
registers a new leanXMSS key.
