# EIP-8184 -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modifications in EIP-8184](#modifications-in-eip-8184)
  - [Configuration](#configuration)
  - [Helpers](#helpers)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [New `sealed_transaction`](#new-sealed_transaction)
        - [New `sealed_bundle`](#new-sealed_bundle)
        - [New `lucid_key_message`](#new-lucid_key_message)
        - [New `lucid_key_timeliness_vote`](#new-lucid_key_timeliness_vote)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [SealedTransactionByCommitment v1](#sealedtransactionbycommitment-v1)
      - [SealedBundleByCommitment v1](#sealedbundlebycommitment-v1)
      - [LucidKeyMessageByCommitment v1](#lucidkeymessagebycommitment-v1)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for
EIP-8184 (LUCID).

The specification of these changes continues in the same format as the
network specifications of previous upgrades, and assumes them as
pre-requisite.

## Modifications in EIP-8184

### Configuration

| Name                              | Value                | Description                                                            |
| --------------------------------- | -------------------- | ---------------------------------------------------------------------- |
| `MAX_REQUEST_SEALED_TRANSACTIONS` | `2**6` (= 64)        | Maximum number of sealed transactions in a single Req/Resp response    |
| `MAX_REQUEST_SEALED_BUNDLES`      | `2**5` (= 32)        | Maximum number of sealed bundles in a single Req/Resp response         |
| `MAX_REQUEST_LUCID_KEY_MESSAGES`  | `2**6` (= 64)        | Maximum number of `LucidKeyMessage`s in a single Req/Resp response     |

### Helpers

#### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= EIP8184_FORK_EPOCH:
        return EIP8184_FORK_VERSION
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

### The gossip domain: gossipsub

#### Topics and messages

The new topics along with the type of the `data` field of a gossipsub
message are given in this table:

| Name                        | Message Type                   |
| --------------------------- | ------------------------------ |
| `sealed_transaction`        | `SealedTransaction`            |
| `sealed_bundle`             | `SealedBundle`                 |
| `lucid_key_message`         | `LucidKeyMessage`              |
| `lucid_key_timeliness_vote` | `SignedLucidKeyTimelinessVote` |

##### Global topics

EIP-8184 introduces four new global topics for sealed transactions,
bundles, decryption key messages, and PTC key-timeliness votes.

###### New `sealed_transaction`

This topic is used to propagate individual sealed transactions in the
public encrypted mempool. The following validations MUST pass before
forwarding the `sealed_transaction` on the network:

- _[REJECT]_ The byte size of `ciphertext_envelope` is within upper bound
  `MAX_BYTES_PER_ST`.
- _[REJECT]_ The ticket's `ciphertext_hash` equals
  `keccak256(ciphertext_envelope)`.
- _[REJECT]_ The ticket's `signature_id` is a recognised signature scheme
  (currently only `EC_DSA_TYPE`).
- _[REJECT]_ The ticket's signature recovers a valid sender address.
- _[IGNORE]_ The `SealedTransaction` has not already been seen.

###### New `sealed_bundle`

This topic is used to propagate sealed bundles. The following validations
MUST pass before forwarding the `sealed_bundle` on the network, assuming
the alias `members = sealed_bundle.sealed_transactions`:

- _[REJECT]_ The number of bundle members is within upper bound
  `MAX_STS_PER_BUNDLE`.
- _[REJECT]_ Each member of `members` independently satisfies the
  `sealed_transaction` validations above.
- _[REJECT]_ All members of `members` share the same `key_publisher`
  address as recovered from `sealed_bundle.key_publisher_signature` via
  [`is_valid_key_publisher_signature`](./beacon-chain.md#new-is_valid_key_publisher_signature).
- _[IGNORE]_ The `SealedBundle` has not already been seen.

###### New `lucid_key_message`

This topic is used to propagate `LucidKeyMessage`s released by key
publishers. The following validations MUST pass before forwarding the
`lucid_key_message` on the network:

- _[IGNORE]_ The `scheduling_slot` is within
  `[current_slot - SLOTS_PER_EPOCH, current_slot]`.
- _[REJECT]_ The `chain_id` matches the local chain.
- _[REJECT]_ A scheduling beacon block with root
  `scheduling_beacon_block_root` is known and contains an `STCommitment`
  at index `commit_index`.
- _[REJECT]_ The `LucidKeyMessage` is valid with respect to that
  commitment per
  [`is_valid_lucid_key_message`](./beacon-chain.md#new-is_valid_lucid_key_message).
- _[IGNORE]_ The `LucidKeyMessage` has not already been seen.

###### New `lucid_key_timeliness_vote`

This topic is used to propagate `SignedLucidKeyTimelinessVote` messages
from PTC members. The following validations MUST pass before forwarding
the `lucid_key_timeliness_vote` on the network, assuming the alias
`message = signed_vote.message`:

- _[IGNORE]_ The `voting_slot` equals the current slot (with a
  `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance).
- _[IGNORE]_ The `message` is either the first or second valid message
  received from the validator with index `message.validator_index` for
  the `(scheduling_beacon_block_root, scheduling_slot)` pair.
- _[REJECT]_ `message.validator_index` is in the PTC for `voting_slot`,
  i.e. `message.validator_index in get_ptc(state, Slot(message.voting_slot))`.
- _[REJECT]_ `message.chain_id` matches the local chain.
- _[REJECT]_ The signature on `signed_vote` is valid per
  [`is_valid_lucid_key_timeliness_vote_signature`](./beacon-chain.md#new-is_valid_lucid_key_timeliness_vote_signature).

### The Req/Resp domain

#### Messages

##### SealedTransactionByCommitment v1

**Protocol ID:** `/eth2/beacon_chain/req/sealed_transaction_by_commitment/1/`

For each successful `response_chunk`, the `ForkDigest` context epoch is
determined by `compute_epoch_at_slot(get_current_slot(store))`.

Per `fork_version = compute_fork_version(epoch)`:

<!-- eth_consensus_specs: skip -->

| `fork_version`         | Chunk SSZ type               |
| ---------------------- | ---------------------------- |
| `EIP8184_FORK_VERSION` | `eip8184.SealedTransaction`  |

Request Content:

```
(
  commitment_roots: List[Bytes32, MAX_REQUEST_SEALED_TRANSACTIONS]
)
```

Response Content:

```
(
  List[SealedTransaction, MAX_REQUEST_SEALED_TRANSACTIONS]
)
```

##### SealedBundleByCommitment v1

**Protocol ID:** `/eth2/beacon_chain/req/sealed_bundle_by_commitment/1/`

Per `fork_version = compute_fork_version(epoch)`:

<!-- eth_consensus_specs: skip -->

| `fork_version`         | Chunk SSZ type          |
| ---------------------- | ----------------------- |
| `EIP8184_FORK_VERSION` | `eip8184.SealedBundle`  |

Request Content:

```
(
  commitment_roots: List[Bytes32, MAX_REQUEST_SEALED_BUNDLES]
)
```

Response Content:

```
(
  List[SealedBundle, MAX_REQUEST_SEALED_BUNDLES]
)
```

##### LucidKeyMessageByCommitment v1

**Protocol ID:** `/eth2/beacon_chain/req/lucid_key_message_by_commitment/1/`

Per `fork_version = compute_fork_version(epoch)`:

<!-- eth_consensus_specs: skip -->

| `fork_version`         | Chunk SSZ type            |
| ---------------------- | ------------------------- |
| `EIP8184_FORK_VERSION` | `eip8184.LucidKeyMessage` |

Request Content:

```
(
  scheduling_beacon_block_root: Bytes32
  commit_indices: Bitlist[MAX_ST_COMMITS]
)
```

Response Content:

```
(
  List[LucidKeyMessage, MAX_REQUEST_LUCID_KEY_MESSAGES]
)
```
