# EIP-8184 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Domains](#domains)
  - [Signature schemes](#signature-schemes)
- [Preset](#preset)
  - [Sealed transaction parameters](#sealed-transaction-parameters)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`CiphertextEnvelope`](#ciphertextenvelope)
    - [`SealedTransaction`](#sealedtransaction)
    - [`SealedBundle`](#sealedbundle)
    - [`SealedTransactionCommitment`](#sealedtransactioncommitment)
    - [`DecryptedTransaction`](#decryptedtransaction)
    - [`RevealCommitmentPreimage`](#revealcommitmentpreimage)
    - [`SealedTransactionKeyMessage`](#sealedtransactionkeymessage)
    - [`SealedTransactionKeyTimelinessVote`](#sealedtransactionkeytimelinessvote)
    - [`SignedSealedTransactionKeyTimelinessVote`](#signedsealedtransactionkeytimelinessvote)
  - [Modified containers](#modified-containers)
    - [`InclusionList`](#inclusionlist)
    - [`ExecutionPayloadBid`](#executionpayloadbid)
    - [`ExecutionPayload`](#executionpayload)
- [Helpers](#helpers)
  - [Misc](#misc)
    - [New `compute_top_of_block_gas_limit`](#new-compute_top_of_block_gas_limit)
    - [New `compute_top_of_block_gas_limit_per_inclusion_list_member`](#new-compute_top_of_block_gas_limit_per_inclusion_list_member)
    - [New `compute_bundle_root`](#new-compute_bundle_root)
    - [New `compute_commitment_key`](#new-compute_commitment_key)
    - [New `compute_aead_nonce`](#new-compute_aead_nonce)
  - [Predicates](#predicates)
    - [New `is_valid_sealed_transaction_commitment_ordering`](#new-is_valid_sealed_transaction_commitment_ordering)
    - [New `is_valid_key_publisher_signature`](#new-is_valid_key_publisher_signature)
    - [New `is_valid_sealed_transaction_key_message`](#new-is_valid_sealed_transaction_key_message)
    - [New `is_valid_sealed_transaction_key_timeliness_vote_signature`](#new-is_valid_sealed_transaction_key_timeliness_vote_signature)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Execution payload bid](#execution-payload-bid)
      - [New `process_sealed_transaction_commitments`](#new-process_sealed_transaction_commitments)

<!-- mdformat-toc end -->

## Introduction

This document specifies the consensus-layer changes required to support
[EIP-8184](https://eips.ethereum.org/EIPS/eip-8184) (encrypted mempool).

The encrypted mempool extends the public inclusion pipeline with *sealed
transactions*, encrypted transactions that are propagated and committed
to before their plaintext contents are revealed. Builders commit to
sealed transactions in the execution payload bid via
`SealedTransactionCommitment` entries. After the scheduling decision is
fixed, key publishers release ChaCha20-Poly1305 decryption keys
(`SealedTransactionKeyMessage`) that allow the sealed transactions to be
decrypted and executed in the following slot. The payload timeliness
committee (PTC) casts a per-commitment
`SealedTransactionKeyTimelinessVote` indicating which keys were observed
before its deadline.

*Note*: This specification is built upon
[Heze](../../heze/beacon-chain.md).

## Constants

### Domains

| Name                                       | Value                                |
| ------------------------------------------ | ------------------------------------ |
| `DOMAIN_SEALED_TRANSACTION_KEY_TIMELINESS` | `DomainType('0x11000000')` **(TBD)** |

### Signature schemes

| Name          | Value          | Description                          |
| ------------- | -------------- | ------------------------------------ |
| `ECDSA_TYPE`  | `uint8(0x01)`  | secp256k1 ECDSA signature identifier |

## Preset

### Sealed transaction parameters

| Name                                                  | Value                            | Description                                                                                |
| ----------------------------------------------------- | -------------------------------- | ------------------------------------------------------------------------------------------ |
| `TOP_OF_BLOCK_GAS_FRACTION_DENOMINATOR`               | `uint64(2**3)` (= 8)             | Denominator for the top-of-block gas budget (`top_of_block_gas_limit = gas_limit // 8`)    |
| `TOP_OF_BLOCK_FEE_FRACTION`                           | `uint64(2**7)` (= 128)           | Denominator for the unrevealed top-of-block fee burn fraction                              |
| `MAX_SIGNATURE_SIZE`                                  | `uint64(2**16)` (= 65,536)       | Upper bound on the byte length of a sealed-transaction ticket or key publisher signature   |
| `MAX_BYTES_PER_SEALED_TRANSACTION`                    | `uint64(2**24 // 64)` (= 262,144)| Maximum byte length of a single sealed transaction payload (bounded by EIP-7825)           |
| `MAX_SEALED_TRANSACTION_COMMITMENTS_PER_INCLUSION_LIST` | `uint64(2**1)` (= 2)           | Maximum number of sealed-transaction commitments per inclusion list committee member       |
| `MAX_SEALED_TRANSACTIONS_PER_BUNDLE`                  | `uint64(2**6)` (= 64)            | Maximum number of sealed transactions in a single bundle                                   |
| `MAX_SEALED_TRANSACTION_COMMITMENTS`                  | `MAX_SEALED_TRANSACTION_COMMITMENTS_PER_INCLUSION_LIST * INCLUSION_LIST_COMMITTEE_SIZE` | Maximum total sealed-transaction commitments across all inclusion list members in one block |
| `MAX_SEALED_TRANSACTION_TICKETS`                      | `MAX_SEALED_TRANSACTION_COMMITMENTS * MAX_SEALED_TRANSACTIONS_PER_BUNDLE` | Maximum total sealed-transaction tickets that may be executed in one block |

## Containers

### New containers

#### `CiphertextEnvelope`

*Note*: The AEAD nonce is not carried in the envelope. It is derived
from `(chain_id, ticket_from, ticket_nonce)` via
[`compute_aead_nonce`](#new-compute_aead_nonce).

```python
class CiphertextEnvelope(Container):
    header: ByteList[2**16 - 1]
    ciphertext: ByteList[MAX_BYTES_PER_SEALED_TRANSACTION]
```

#### `SealedTransaction`

```python
class SealedTransaction(Container):
    ticket: Transaction
    ciphertext_envelope: ByteList[MAX_BYTES_PER_SEALED_TRANSACTION]
```

#### `SealedBundle`

*Note*: All sealed transactions in a bundle MUST share the same
`key_publisher` address (recovered from the bundle signature). The
bundle signature recovers `key_publisher` from
`(chain_id, compute_bundle_root(sealed_transactions))`.

```python
class SealedBundle(Container):
    sealed_transactions: List[SealedTransaction, MAX_SEALED_TRANSACTIONS_PER_BUNDLE]
    key_publisher_signature_id: uint8
    key_publisher_signature: ByteList[MAX_SIGNATURE_SIZE]
```

#### `SealedTransactionCommitment`

*Note*: `executable` is an empty bitlist for non-bundle (single
sealed-transaction) commitments. For bundle commitments, `executable[i]`
is set to `1` if and only if the `i`-th member of the committed bundle
can pay its ticket fee and passes the nonce check at the position
determined by the sealed-transaction commitment ordering rule.

```python
class SealedTransactionCommitment(Container):
    commitment_root: Bytes32
    commitment_key: Bytes32
    gas_obligation: uint64
    executable: Bitlist[MAX_SEALED_TRANSACTIONS_PER_BUNDLE]
```

#### `DecryptedTransaction`

```python
class DecryptedTransaction(Container):
    plaintext_tx: Transaction
```

#### `RevealCommitmentPreimage`

*Note*: `hash_tree_root(RevealCommitmentPreimage(...))` is the
`reveal_commitment` field of a sealed-transaction ticket. It binds the
revealed plaintext payload to a specific ticket.

```python
class RevealCommitmentPreimage(Container):
    chain_id: uint256
    ticket_from: ExecutionAddress
    ticket_nonce: uint64
    plaintext_tx: Transaction
```

#### `SealedTransactionKeyMessage`

```python
class SealedTransactionKeyMessage(Container):
    chain_id: uint256
    scheduling_beacon_block_root: Bytes32
    scheduling_slot: uint64
    commit_index: uint8
    decryption_keys: List[Bytes32, MAX_SEALED_TRANSACTIONS_PER_BUNDLE]
```

#### `SealedTransactionKeyTimelinessVote`

*Note*: Cast by PTC members of the slot following the scheduling slot.
`keys_observed[j]` is set to `1` if and only if the voter observed a
valid `SealedTransactionKeyMessage` for
`(scheduling_beacon_block_root, scheduling_slot, commit_index=j)` by
the key observation deadline of the PTC.

```python
class SealedTransactionKeyTimelinessVote(Container):
    chain_id: uint256
    voting_slot: uint64
    validator_index: ValidatorIndex
    scheduling_beacon_block_root: Bytes32
    scheduling_slot: uint64
    keys_observed: Bitlist[MAX_SEALED_TRANSACTION_COMMITMENTS]
```

#### `SignedSealedTransactionKeyTimelinessVote`

```python
class SignedSealedTransactionKeyTimelinessVote(Container):
    message: SealedTransactionKeyTimelinessVote
    signature: BLSSignature
```

### Modified containers

#### `InclusionList`

*Note*: An inclusion list MUST satisfy
`len(sealed_transactions) + len(sealed_bundles) <= MAX_SEALED_TRANSACTION_COMMITMENTS_PER_INCLUSION_LIST`.

```python
class InclusionList(Container):
    slot: Slot
    validator_index: ValidatorIndex
    inclusion_list_committee_root: Root
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]
    # [New in EIP8184]
    sealed_transactions: List[SealedTransaction, MAX_SEALED_TRANSACTION_COMMITMENTS_PER_INCLUSION_LIST]
    # [New in EIP8184]
    sealed_bundles: List[SealedBundle, MAX_SEALED_TRANSACTION_COMMITMENTS_PER_INCLUSION_LIST]
```

#### `ExecutionPayloadBid`

*Note*: `sealed_transaction_commitments` MUST be ordered by descending
`commitment_top_of_block_fee`, then descending `gas_obligation`, then
ascending `commitment_root` — see
[`is_valid_sealed_transaction_commitment_ordering`](#new-is_valid_sealed_transaction_commitment_ordering).
`inclusion_list_roots` is the list of inclusion list roots the builder
asserts it adhered to.

```python
class ExecutionPayloadBid(Container):
    parent_block_hash: Hash32
    parent_block_root: Root
    block_hash: Hash32
    prev_randao: Bytes32
    fee_recipient: ExecutionAddress
    gas_limit: uint64
    builder_index: BuilderIndex
    slot: Slot
    value: Gwei
    execution_payment: Gwei
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    execution_requests_root: Root
    # [New in EIP8184]
    sealed_transaction_commitments: List[SealedTransactionCommitment, MAX_SEALED_TRANSACTION_COMMITMENTS]
    # [New in EIP8184]
    inclusion_list_roots: List[Bytes32, INCLUSION_LIST_COMMITTEE_SIZE]
```

#### `ExecutionPayload`

*Note*: `sealed_transaction_tickets` carries the sealed-transaction
tickets whose commitments are in the current slot's bid.
`decrypted_transactions` carries the decryptions of commitments
scheduled in the *parent* slot's bid. Under recovery from a rejected
payload, `decrypted_transactions` may carry decryptions from both the
grandparent and parent scheduling blocks; entries from the earlier
scheduling block precede those from the later one. Although these fields
appear at the end of the SSZ container for index stability, both are
*executed* at the top of the block; execution-order semantics are
governed by the execution-layer specification, not by SSZ field order.

```python
class ExecutionPayload(Container):
    parent_hash: Hash32
    fee_recipient: ExecutionAddress
    state_root: Bytes32
    receipts_root: Bytes32
    logs_bloom: ByteVector[BYTES_PER_LOGS_BLOOM]
    prev_randao: Bytes32
    block_number: uint64
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    extra_data: ByteList[MAX_EXTRA_DATA_BYTES]
    base_fee_per_gas: uint256
    block_hash: Hash32
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]
    withdrawals: List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD]
    blob_gas_used: uint64
    excess_blob_gas: uint64
    block_access_list: BlockAccessList
    slot_number: uint64
    # [New in EIP8184]
    sealed_transaction_tickets: List[Transaction, MAX_SEALED_TRANSACTION_TICKETS]
    # [New in EIP8184]
    decrypted_transactions: List[DecryptedTransaction, 2 * MAX_SEALED_TRANSACTION_TICKETS]
```

## Helpers

### Misc

#### New `compute_top_of_block_gas_limit`

```python
def compute_top_of_block_gas_limit(block_gas_limit: uint64) -> uint64:
    """
    Return the aggregate top-of-block gas budget for sealed transactions
    in a block with the given ``block_gas_limit``.
    """
    return block_gas_limit // TOP_OF_BLOCK_GAS_FRACTION_DENOMINATOR
```

#### New `compute_top_of_block_gas_limit_per_inclusion_list_member`

```python
def compute_top_of_block_gas_limit_per_inclusion_list_member(
    block_gas_limit: uint64,
) -> uint64:
    """
    Return the per-inclusion-list-member top-of-block gas budget for
    sealed transactions.
    """
    return (
        compute_top_of_block_gas_limit(block_gas_limit)
        // INCLUSION_LIST_COMMITTEE_SIZE
    )
```

#### New `compute_bundle_root`

*Note*: Mirrors the execution-layer definition: the bundle root is the
keccak256 of the concatenation of each ticket's keccak256 hash, in
bundle order. Used both to authenticate the bundle (via the key
publisher's signature) and to derive its commitment root.

```python
def compute_bundle_root(
    sealed_transactions: Sequence[SealedTransaction],
) -> Bytes32:
    """
    Return the bundle root over the ticket hashes of
    ``sealed_transactions``.
    """
    return Bytes32(keccak(b"".join(
        keccak(ssz_serialize(st.ticket)) for st in sealed_transactions
    )))
```

#### New `compute_commitment_key`

*Note*: For a non-bundle commitment, `commitment_key` is the ticket's
`key_commitment` (`keccak256(decryption_key)`). For a bundle, it is the
keccak256 of the concatenated `key_commitment` values of every
executable member, in bundle order.

```python
def compute_commitment_key(
    key_commitments: Sequence[Bytes32],
) -> Bytes32:
    """
    Return the commitment key for a sequence of executable
    ``key_commitments``.
    """
    if len(key_commitments) == 1:
        return key_commitments[0]
    return Bytes32(keccak(b"".join(key_commitments)))
```

#### New `compute_aead_nonce`

*Note*: The 12-byte ChaCha20-Poly1305 nonce is protocol-defined, not
chosen by the encryptor. Binding the nonce to
`(chain_id, ticket_from, ticket_nonce)` ensures uniqueness of every
`(decryption_key, nonce)` pair given that each decryption key is bound
to a single ticket via `key_commitment`.

```python
def compute_aead_nonce(
    chain_id: uint256,
    ticket_from: ExecutionAddress,
    ticket_nonce: uint64,
) -> Bytes12:
    """
    Return the deterministic AEAD nonce for a sealed transaction.
    """
    return Bytes12(keccak(
        ssz_serialize(chain_id)
        + ticket_from
        + ssz_serialize(ticket_nonce)
    )[:12])
```

### Predicates

#### New `is_valid_sealed_transaction_commitment_ordering`

```python
def is_valid_sealed_transaction_commitment_ordering(
    sealed_transaction_commitments: Sequence[SealedTransactionCommitment],
    commitment_top_of_block_fees: Sequence[uint64],
) -> bool:
    """
    Return whether ``sealed_transaction_commitments`` is ordered as
    required by the encrypted mempool: descending
    ``commitment_top_of_block_fee``, then descending ``gas_obligation``,
    then ascending ``commitment_root``.
    """
    assert len(sealed_transaction_commitments) == len(commitment_top_of_block_fees)
    for i in range(len(sealed_transaction_commitments) - 1):
        a, b = sealed_transaction_commitments[i], sealed_transaction_commitments[i + 1]
        fee_a, fee_b = commitment_top_of_block_fees[i], commitment_top_of_block_fees[i + 1]
        if fee_a > fee_b:
            continue
        if fee_a < fee_b:
            return False
        if a.gas_obligation > b.gas_obligation:
            continue
        if a.gas_obligation < b.gas_obligation:
            return False
        if a.commitment_root < b.commitment_root:
            continue
        return False
    return True
```

#### New `is_valid_key_publisher_signature`

*Note*: The signature recovers a 20-byte execution-layer address — the
`key_publisher`. The signature scheme is determined by
`key_publisher_signature_id`; only `ECDSA_TYPE` is currently defined.

```python
def is_valid_key_publisher_signature(
    chain_id: uint256,
    bundle: SealedBundle,
    expected_key_publisher: ExecutionAddress,
) -> bool:
    """
    Return whether ``bundle.key_publisher_signature`` recovers
    ``expected_key_publisher`` over ``(chain_id, bundle_root)``.
    """
    if bundle.key_publisher_signature_id != ECDSA_TYPE:
        return False
    bundle_root = compute_bundle_root(bundle.sealed_transactions)
    signing_message = ssz_serialize(chain_id) + bundle_root
    recovered = ecdsa_recover_address(
        signing_message, bundle.key_publisher_signature
    )
    return recovered == expected_key_publisher
```

#### New `is_valid_sealed_transaction_key_message`

```python
def is_valid_sealed_transaction_key_message(
    state: BeaconState,
    key_message: SealedTransactionKeyMessage,
    commitment: SealedTransactionCommitment,
) -> bool:
    """
    Return whether ``key_message`` is a valid reveal for ``commitment``.
    """
    if key_message.chain_id != state.fork.current_version.chain_id:
        return False

    expected_len = max(1, sum(commitment.executable))
    if len(key_message.decryption_keys) != expected_len:
        return False

    key_commitments = [Bytes32(keccak(k)) for k in key_message.decryption_keys]
    if compute_commitment_key(key_commitments) != commitment.commitment_key:
        return False

    return True
```

#### New `is_valid_sealed_transaction_key_timeliness_vote_signature`

```python
def is_valid_sealed_transaction_key_timeliness_vote_signature(
    state: BeaconState,
    signed_vote: SignedSealedTransactionKeyTimelinessVote,
) -> bool:
    """
    Return whether ``signed_vote`` has a valid BLS signature over its
    ``SealedTransactionKeyTimelinessVote`` message.
    """
    message = signed_vote.message
    pubkey = state.validators[message.validator_index].pubkey
    domain = get_domain(
        state,
        DOMAIN_SEALED_TRANSACTION_KEY_TIMELINESS,
        compute_epoch_at_slot(Slot(message.voting_slot)),
    )
    signing_root = compute_signing_root(message, domain)
    return bls.Verify(pubkey, signing_root, signed_vote.signature)
```

## Beacon chain state transition function

### Block processing

#### Execution payload bid

##### New `process_sealed_transaction_commitments`

*Note*: This function validates the structural well-formedness of the
sealed-transaction commitments carried in the execution payload bid.
Fee headroom and `executable` correctness are validated by the
execution engine; this function checks only the consensus-layer
invariants.

```python
def process_sealed_transaction_commitments(
    state: BeaconState, bid: ExecutionPayloadBid
) -> None:
    """
    Validate the sealed-transaction commitments carried in ``bid``.

    Raises ``AssertionError`` if any consensus-layer invariant fails.
    """
    # Aggregate gas obligation must fit within the top-of-block gas budget.
    top_of_block_gas_limit = compute_top_of_block_gas_limit(bid.gas_limit)
    aggregate_gas_obligation = sum(
        c.gas_obligation for c in bid.sealed_transaction_commitments
    )
    assert aggregate_gas_obligation <= top_of_block_gas_limit

    # inclusion_list_roots length must not exceed the inclusion list committee.
    assert len(bid.inclusion_list_roots) <= INCLUSION_LIST_COMMITTEE_SIZE

    # Per-commitment well-formedness: bundle commitments carry a non-empty
    # executable bitlist whose length equals the bundle size; non-bundle
    # commitments carry an empty executable bitlist.
    for commitment in bid.sealed_transaction_commitments:
        assert len(commitment.executable) <= MAX_SEALED_TRANSACTIONS_PER_BUNDLE
        if len(commitment.executable) > 0:
            assert sum(commitment.executable) > 0
```
