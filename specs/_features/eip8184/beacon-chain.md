# EIP-8184 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Domains](#domains)
  - [Signature schemes](#signature-schemes)
- [Preset](#preset)
  - [LUCID parameters](#lucid-parameters)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`CiphertextEnvelope`](#ciphertextenvelope)
    - [`SealedTransaction`](#sealedtransaction)
    - [`SealedBundle`](#sealedbundle)
    - [`STCommitment`](#stcommitment)
    - [`DecryptedTransaction`](#decryptedtransaction)
    - [`RevealCommitmentPreimage`](#revealcommitmentpreimage)
    - [`LucidKeyMessage`](#lucidkeymessage)
    - [`LucidKeyTimelinessVote`](#lucidkeytimelinessvote)
    - [`SignedLucidKeyTimelinessVote`](#signedlucidkeytimelinessvote)
  - [Modified containers](#modified-containers)
    - [`InclusionList`](#inclusionlist)
    - [`ExecutionPayloadBid`](#executionpayloadbid)
    - [`ExecutionPayload`](#executionpayload)
- [Helpers](#helpers)
  - [Misc](#misc)
    - [New `compute_tob_gas_limit`](#new-compute_tob_gas_limit)
    - [New `compute_tob_gas_limit_per_il`](#new-compute_tob_gas_limit_per_il)
    - [New `compute_bundle_root`](#new-compute_bundle_root)
    - [New `compute_commitment_key`](#new-compute_commitment_key)
    - [New `compute_dem_nonce`](#new-compute_dem_nonce)
  - [Predicates](#predicates)
    - [New `is_valid_st_commitment_ordering`](#new-is_valid_st_commitment_ordering)
    - [New `is_valid_key_publisher_signature`](#new-is_valid_key_publisher_signature)
    - [New `is_valid_lucid_key_message`](#new-is_valid_lucid_key_message)
    - [New `is_valid_lucid_key_timeliness_vote_signature`](#new-is_valid_lucid_key_timeliness_vote_signature)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Execution payload bid](#execution-payload-bid)
      - [New `process_st_commitments`](#new-process_st_commitments)

<!-- mdformat-toc end -->

## Introduction

This document specifies the consensus-layer changes required to support
[EIP-8184](https://eips.ethereum.org/EIPS/eip-8184) (LUCID encrypted mempool).

LUCID extends the public inclusion pipeline with *sealed transactions* (STs),
encrypted transactions that are propagated and committed to before their
plaintext contents are revealed. Builders commit to STs in the execution
payload bid via `STCommitment` entries. After the scheduling decision is
fixed, key publishers release ChaCha20-Poly1305 DEM keys (`LucidKeyMessage`)
that allow the STs to be decrypted and executed in the following slot. The
payload timeliness committee (PTC) casts a per-commitment
`LucidKeyTimelinessVote` indicating which keys were observed before its
deadline.

*Note*: This specification is built upon
[Heze](../../heze/beacon-chain.md).

## Constants

### Domains

| Name                          | Value                                |
| ----------------------------- | ------------------------------------ |
| `DOMAIN_LUCID_KEY_TIMELINESS` | `DomainType('0x11000000')` **(TBD)** |

### Signature schemes

| Name             | Value          | Description                          |
| ---------------- | -------------- | ------------------------------------ |
| `EC_DSA_TYPE`    | `uint8(0x01)`  | secp256k1 ECDSA signature identifier |

## Preset

### LUCID parameters

| Name                            | Value                            | Description                                                                         |
| ------------------------------- | -------------------------------- | ----------------------------------------------------------------------------------- |
| `TOB_GAS_FRACTION_DENOMINATOR`  | `uint64(2**3)` (= 8)             | Denominator for the top-of-block gas budget (`tob_gas_limit = gas_limit // 8`)      |
| `TOB_FEE_FRACTION`              | `uint64(2**7)` (= 128)           | Denominator for the unrevealed-tob-fee burn fraction                                |
| `MAX_SIGNATURE_SIZE`            | `uint64(2**16)` (= 65,536)       | Upper bound on the byte length of an ST ticket or key publisher signature           |
| `MAX_BYTES_PER_ST`              | `uint64(2**24 // 64)` (= 262,144)| Maximum byte length of a single sealed transaction payload (bounded by EIP-7825)    |
| `MAX_ST_COMMITS_PER_IL`         | `uint64(2**1)` (= 2)             | Maximum number of ST commitments per inclusion list committee member                |
| `MAX_STS_PER_BUNDLE`            | `uint64(2**6)` (= 64)            | Maximum number of sealed transactions in a single bundle                            |
| `MAX_ST_COMMITS`                | `MAX_ST_COMMITS_PER_IL * INCLUSION_LIST_COMMITTEE_SIZE` | Maximum total ST commitments across all IL members in one block |
| `MAX_ST_TICKETS`                | `MAX_ST_COMMITS * MAX_STS_PER_BUNDLE` | Maximum total sealed tickets that may be executed in one block                |

## Containers

### New containers

#### `CiphertextEnvelope`

*Note*: The DEM nonce is not carried in the envelope. It is derived from
`(chain_id, ticket_from, ticket_nonce)` via
[`compute_dem_nonce`](#new-compute_dem_nonce).

```python
class CiphertextEnvelope(Container):
    header: ByteList[2**16 - 1]
    dem_ciphertext: ByteList[MAX_BYTES_PER_ST]
```

#### `SealedTransaction`

```python
class SealedTransaction(Container):
    ticket: Transaction
    ciphertext_envelope: ByteList[MAX_BYTES_PER_ST]
```

#### `SealedBundle`

*Note*: All sealed transactions in a bundle MUST share the same
`key_publisher` address (recovered from the bundle signature). The bundle
signature recovers `key_publisher` from
`(chain_id, compute_bundle_root(sealed_transactions))`.

```python
class SealedBundle(Container):
    sealed_transactions: List[SealedTransaction, MAX_STS_PER_BUNDLE]
    key_publisher_signature_id: uint8
    key_publisher_signature: ByteList[MAX_SIGNATURE_SIZE]
```

#### `STCommitment`

*Note*: `executable` is an empty bitlist for non-bundle (single-ST)
commitments. For bundle commitments, `executable[i]` is set to `1` if and
only if the `i`-th member of the committed bundle can pay its `ticket_fee`
and passes the nonce check at the position determined by the ST-commitment
ordering rule.

```python
class STCommitment(Container):
    commitment_root: Bytes32
    commitment_key: Bytes32
    gas_obligation: uint64
    executable: Bitlist[MAX_STS_PER_BUNDLE]
```

#### `DecryptedTransaction`

```python
class DecryptedTransaction(Container):
    plaintext_tx: Transaction
```

#### `RevealCommitmentPreimage`

*Note*: `hash_tree_root(RevealCommitmentPreimage(...))` is the
`reveal_commitment` field of a sealed ticket. It binds the revealed
plaintext payload to a specific ticket.

```python
class RevealCommitmentPreimage(Container):
    chain_id: uint256
    ticket_from: ExecutionAddress
    ticket_nonce: uint64
    plaintext_tx: Transaction
```

#### `LucidKeyMessage`

```python
class LucidKeyMessage(Container):
    chain_id: uint256
    scheduling_beacon_block_root: Bytes32
    scheduling_slot: uint64
    commit_index: uint8
    k_dems: List[Bytes32, MAX_STS_PER_BUNDLE]
```

#### `LucidKeyTimelinessVote`

*Note*: Cast by PTC members of the slot following the scheduling slot.
`keys_observed[j]` is set to `1` if and only if the voter observed a valid
`LucidKeyMessage` for `(scheduling_beacon_block_root, scheduling_slot,
commit_index=j)` by the key observation deadline of the PTC.

```python
class LucidKeyTimelinessVote(Container):
    chain_id: uint256
    voting_slot: uint64
    validator_index: ValidatorIndex
    scheduling_beacon_block_root: Bytes32
    scheduling_slot: uint64
    keys_observed: Bitlist[MAX_ST_COMMITS]
```

#### `SignedLucidKeyTimelinessVote`

```python
class SignedLucidKeyTimelinessVote(Container):
    message: LucidKeyTimelinessVote
    signature: BLSSignature
```

### Modified containers

#### `InclusionList`

*Note*: An IL MUST satisfy
`len(sealed_transactions) + len(sealed_bundles) <= MAX_ST_COMMITS_PER_IL`.

```python
class InclusionList(Container):
    slot: Slot
    validator_index: ValidatorIndex
    inclusion_list_committee_root: Root
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]
    # [New in EIP8184]
    sealed_transactions: List[SealedTransaction, MAX_ST_COMMITS_PER_IL]
    # [New in EIP8184]
    sealed_bundles: List[SealedBundle, MAX_ST_COMMITS_PER_IL]
```

#### `ExecutionPayloadBid`

*Note*: `st_commitments` MUST be ordered by descending
`commitment_tob_fee`, then descending `gas_obligation`, then ascending
`commitment_root` — see [`is_valid_st_commitment_ordering`](#new-is_valid_st_commitment_ordering).
`IL_roots` is the list of inclusion list roots the builder asserts it
adhered to.

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
    st_commitments: List[STCommitment, MAX_ST_COMMITS]
    # [New in EIP8184]
    IL_roots: List[Bytes32, INCLUSION_LIST_COMMITTEE_SIZE]
```

#### `ExecutionPayload`

*Note*: `st_tickets` carries the ST tickets whose commitments are in the
current slot's bid. `decrypted_transactions` carries the decryptions of
commitments scheduled in the *parent* slot's bid. Under recovery from a
rejected payload, `decrypted_transactions` may carry decryptions from both
the grandparent and parent scheduling blocks; entries from the earlier
scheduling block precede those from the later one.

```python
class ExecutionPayload(Container):
    # [New in EIP8184]
    st_tickets: List[Transaction, MAX_ST_TICKETS]
    # [New in EIP8184]
    decrypted_transactions: List[DecryptedTransaction, 2 * MAX_ST_TICKETS]
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
```

## Helpers

### Misc

#### New `compute_tob_gas_limit`

```python
def compute_tob_gas_limit(block_gas_limit: uint64) -> uint64:
    """
    Return the aggregate top-of-block gas budget for sealed transactions
    in a block with the given ``block_gas_limit``.
    """
    return block_gas_limit // TOB_GAS_FRACTION_DENOMINATOR
```

#### New `compute_tob_gas_limit_per_il`

```python
def compute_tob_gas_limit_per_il(block_gas_limit: uint64) -> uint64:
    """
    Return the per-IL-member top-of-block gas budget for sealed
    transactions.
    """
    return compute_tob_gas_limit(block_gas_limit) // INCLUSION_LIST_COMMITTEE_SIZE
```

#### New `compute_bundle_root`

*Note*: Mirrors the execution-layer definition: the bundle root is the
keccak256 of the concatenation of each ticket's keccak256 hash, in bundle
order. Used both to authenticate the bundle (via the key publisher's
signature) and to derive its commitment root.

```python
def compute_bundle_root(
    sealed_transactions: Sequence[SealedTransaction],
) -> Bytes32:
    """
    Return the bundle root over the ticket hashes of ``sealed_transactions``.
    """
    return Bytes32(keccak(b"".join(
        keccak(ssz_serialize(st.ticket)) for st in sealed_transactions
    )))
```

#### New `compute_commitment_key`

*Note*: For a non-bundle commitment, `commitment_key` is the ticket's
`key_commitment` (`keccak256(k_dem)`). For a bundle, it is the keccak256
of the concatenated `key_commitment` values of every executable member,
in bundle order.

```python
def compute_commitment_key(
    key_commitments: Sequence[Bytes32],
) -> Bytes32:
    """
    Return the commitment key for a sequence of executable ``key_commitments``.
    """
    if len(key_commitments) == 1:
        return key_commitments[0]
    return Bytes32(keccak(b"".join(key_commitments)))
```

#### New `compute_dem_nonce`

*Note*: The 12-byte ChaCha20-Poly1305 nonce is protocol-defined, not
chosen by the encryptor. Binding the nonce to
`(chain_id, ticket_from, ticket_nonce)` ensures uniqueness of every
`(k_dem, nonce)` pair given that each `k_dem` is bound to a single ticket
via `key_commitment`.

```python
def compute_dem_nonce(
    chain_id: uint256,
    ticket_from: ExecutionAddress,
    ticket_nonce: uint64,
) -> Bytes12:
    """
    Return the deterministic DEM nonce for a sealed transaction.
    """
    return Bytes12(keccak(
        ssz_serialize(chain_id)
        + ticket_from
        + ssz_serialize(ticket_nonce)
    )[:12])
```

### Predicates

#### New `is_valid_st_commitment_ordering`

```python
def is_valid_st_commitment_ordering(
    st_commitments: Sequence[STCommitment],
    commitment_tob_fees: Sequence[uint64],
) -> bool:
    """
    Return whether ``st_commitments`` is ordered as required by LUCID:
    descending ``commitment_tob_fee``, then descending ``gas_obligation``,
    then ascending ``commitment_root``.
    """
    assert len(st_commitments) == len(commitment_tob_fees)
    for i in range(len(st_commitments) - 1):
        a, b = st_commitments[i], st_commitments[i + 1]
        fee_a, fee_b = commitment_tob_fees[i], commitment_tob_fees[i + 1]
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
`key_publisher_signature_id`; only `EC_DSA_TYPE` is currently defined.

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
    if bundle.key_publisher_signature_id != EC_DSA_TYPE:
        return False
    bundle_root = compute_bundle_root(bundle.sealed_transactions)
    signing_message = ssz_serialize(chain_id) + bundle_root
    recovered = ecdsa_recover_address(
        signing_message, bundle.key_publisher_signature
    )
    return recovered == expected_key_publisher
```

#### New `is_valid_lucid_key_message`

```python
def is_valid_lucid_key_message(
    state: BeaconState,
    key_message: LucidKeyMessage,
    commitment: STCommitment,
) -> bool:
    """
    Return whether ``key_message`` is a valid reveal for ``commitment``.
    """
    if key_message.chain_id != state.fork.current_version.chain_id:
        return False

    expected_len = max(1, sum(commitment.executable))
    if len(key_message.k_dems) != expected_len:
        return False

    key_commitments = [Bytes32(keccak(k)) for k in key_message.k_dems]
    if compute_commitment_key(key_commitments) != commitment.commitment_key:
        return False

    return True
```

#### New `is_valid_lucid_key_timeliness_vote_signature`

```python
def is_valid_lucid_key_timeliness_vote_signature(
    state: BeaconState,
    signed_vote: SignedLucidKeyTimelinessVote,
) -> bool:
    """
    Return whether ``signed_vote`` has a valid BLS signature over its
    ``LucidKeyTimelinessVote`` message.
    """
    message = signed_vote.message
    pubkey = state.validators[message.validator_index].pubkey
    domain = get_domain(
        state,
        DOMAIN_LUCID_KEY_TIMELINESS,
        compute_epoch_at_slot(Slot(message.voting_slot)),
    )
    signing_root = compute_signing_root(message, domain)
    return bls.Verify(pubkey, signing_root, signed_vote.signature)
```

## Beacon chain state transition function

### Block processing

#### Execution payload bid

##### New `process_st_commitments`

*Note*: This function validates the structural well-formedness of the ST
commitments carried in the execution payload bid. Fee headroom and
`executable` correctness are validated by the execution engine; this
function checks only the consensus-layer invariants.

```python
def process_st_commitments(
    state: BeaconState, bid: ExecutionPayloadBid
) -> None:
    """
    Validate the ST commitments carried in ``bid``.

    Raises ``AssertionError`` if any consensus-layer invariant fails.
    """
    # Aggregate gas obligation must fit within the top-of-block gas budget.
    tob_gas_limit = compute_tob_gas_limit(bid.gas_limit)
    aggregate_gas_obligation = sum(c.gas_obligation for c in bid.st_commitments)
    assert aggregate_gas_obligation <= tob_gas_limit

    # IL_roots length must not exceed the inclusion list committee.
    assert len(bid.IL_roots) <= INCLUSION_LIST_COMMITTEE_SIZE

    # Per-commitment well-formedness: bundle commitments carry a non-empty
    # executable bitlist whose length equals the bundle size; non-bundle
    # commitments carry an empty executable bitlist.
    for commitment in bid.st_commitments:
        assert len(commitment.executable) <= MAX_STS_PER_BUNDLE
        if len(commitment.executable) > 0:
            assert sum(commitment.executable) > 0
```
