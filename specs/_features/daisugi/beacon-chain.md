# Daisugi -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers. It
extracts the consensus-layer changes of the experimental Daisugi fork as
implemented by the Lighthouse `eip8288-lean` patch series (asanso/AA-PQ
`4b0a11e`, applied to Lighthouse v8.2.2 `e423a667`) and run on
`daisugi-devnet-0`. Daisugi is not a scheduled mainnet fork.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
  - [New `RecursiveStarkProof`](#new-recursivestarkproof)
- [Constants](#constants)
  - [Execution](#execution)
- [Containers](#containers)
  - [Modified containers](#modified-containers)
    - [`ExecutionPayload`](#executionpayload)
    - [`ExecutionPayloadHeader`](#executionpayloadheader)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Execution engine](#execution-engine)
    - [Engine APIs](#engine-apis)
      - [Modified `is_valid_block_hash`](#modified-is_valid_block_hash)
      - [Modified `is_valid_versioned_hashes`](#modified-is_valid_versioned_hashes)
  - [Block processing](#block-processing)
    - [Execution payload](#execution-payload)
      - [Modified `process_execution_payload`](#modified-process_execution_payload)

<!-- mdformat-toc end -->

## Introduction

Daisugi is an experimental fork built directly on **Electra**. It does not
include Fulu or Gloas. It adds
[EIP-8288](https://eips.ethereum.org/EIPS/eip-8288): every execution payload
carries a recursive STARK proof of the post-quantum signatures that the block's
[EIP-8141](https://eips.ethereum.org/EIPS/eip-8141) frame transactions depend
on, and the execution block header commits to that proof.

The consensus-layer changes are:

- `ExecutionPayload` gains `recursive_stark_proof` as its last field.
- `ExecutionPayloadHeader` gains `recursive_stark_proof_root` as its last field.
- The execution block hash of a Daisugi payload commits to
  `keccak256(recursive_stark_proof)` and to a dependency hash derived from the
  payload's frame transactions. Consensus clients recompute it locally.

`BeaconBlockBody`, `BeaconBlock`, `SignedBeaconBlock`, `BeaconState` and the
light client containers keep their Electra field layout; they change only
through the new `ExecutionPayload` and `ExecutionPayloadHeader` types. A block
without post-quantum dependencies carries an empty proof.

## Types

### New `RecursiveStarkProof`

```python
# [New in Daisugi:EIP8288]
class RecursiveStarkProof(ByteList):
    """
    The EIP-8288 recursive STARK proof of the post-quantum signature
    dependencies of the transactions in an execution payload.
    """

    LIMIT = MAX_RECURSIVE_STARK_PROOF_BYTES
```

## Constants

### Execution

| Name                              | Value                         | Description                                          |
| --------------------------------- | ----------------------------- | ---------------------------------------------------- |
| `MAX_RECURSIVE_STARK_PROOF_BYTES` | `Uint64(2**23)` (= 8,388,608) | Transport bound of the recursive STARK proof (8 MiB) |

*Note*: `MAX_RECURSIVE_STARK_PROOF_BYTES` is a transport bound only. The
execution layer enforces the tighter EIP-8288 proof size limit
(`maxStarkProofBytes` is `1,310,720` in the Daisugi source lock).

## Containers

### Modified containers

#### `ExecutionPayload`

```python
class ExecutionPayload(Container):
    parent_hash: Hash32
    fee_recipient: ExecutionAddress
    state_root: Bytes32
    receipts_root: Bytes32
    logs_bloom: LogsBloom
    prev_randao: Bytes32
    block_number: Uint64
    gas_limit: Uint64
    gas_used: Uint64
    timestamp: Uint64
    extra_data: ExtraData
    base_fee_per_gas: Uint256
    block_hash: Hash32
    transactions: Transactions
    withdrawals: Withdrawals
    blob_gas_used: Uint64
    excess_blob_gas: Uint64
    # [New in Daisugi:EIP8288]
    recursive_stark_proof: RecursiveStarkProof
```

#### `ExecutionPayloadHeader`

```python
class ExecutionPayloadHeader(Container):
    parent_hash: Hash32
    fee_recipient: ExecutionAddress
    state_root: Bytes32
    receipts_root: Bytes32
    logs_bloom: LogsBloom
    prev_randao: Bytes32
    block_number: Uint64
    gas_limit: Uint64
    gas_used: Uint64
    timestamp: Uint64
    extra_data: ExtraData
    base_fee_per_gas: Uint256
    block_hash: Hash32
    transactions_root: Root
    withdrawals_root: Root
    blob_gas_used: Uint64
    excess_blob_gas: Uint64
    # [New in Daisugi:EIP8288]
    recursive_stark_proof_root: Root
```

## Beacon chain state transition function

### Execution engine

The Electra Engine API methods stay in use after the fork:
`engine_newPayloadV4`, `engine_getPayloadV4` and `engine_forkchoiceUpdatedV3`.
From the Daisugi fork on, the JSON `ExecutionPayload` carries the proof as
`starkProof` (hex bytes), and `engine_getPayloadBodiesByHash/ByRange` responses
carry it too. The execution layer derives the header commitments
(`keccak256(stark_proof)` and the block dependency hash) itself; they are not
part of the Engine API payload.

#### Engine APIs

##### Modified `is_valid_block_hash`

*Note*: The function signature is unchanged. In Daisugi, the execution block
header commits to the recursive STARK proof and to the block's post-quantum
signature dependencies, so a consensus client recomputes both from the payload
when it checks `execution_payload.block_hash`. Lighthouse runs this check
locally on every Daisugi block it imports (gossip, lookup, range sync, local
publish), and rejects the block on a mismatch whatever the execution layer
answers. Backfill and checkpoint sync keep the trusted-anchor model: those
payloads are bound by the block root chain and are not recomputed.

```python
def is_valid_block_hash(
    self: ExecutionEngine,
    execution_payload: ExecutionPayload,
    parent_beacon_block_root: Root,
    execution_requests_list: Sequence[bytes],
) -> bool:
    """
    Return ``True`` if and only if ``execution_payload.block_hash`` is computed correctly.

    [Modified in Daisugi:EIP8288]
    The RLP execution block header is the Prague header followed by four fields:
    an empty block access list hash placeholder (``0x80``), an empty slot
    number placeholder (``0x80``), ``keccak256(execution_payload.recursive_stark_proof)``
    and ``get_block_deps_hash(execution_payload.transactions)``. A frame transaction
    that does not decode makes the block hash invalid.
    """
```

The block dependency hash follows the Nethermind prototype
(`FrameDependency.ForBlock` and `ComputeDepsHash`). It is not executable in this
specification because it decodes RLP:

```text
get_block_deps_hash(transactions) -> Bytes32:
    dependencies = []
    for tx in transactions:
        if tx[0] != 0x06:  # EIP-8141 frame transaction type
            continue
        # RLP fields: [chain_id, nonce_keys?, nonce, sender, frames, signatures, fees, blob_hashes]
        fields = rlp_list(tx[1:])
        frames = fields[len(fields) - 4]
        for frame in frames:
            # [mode, flags, target, [execution_gas, state_gas], value, data]
            if len(frame) != 6 or frame.mode != DEP_VERIFY (= 4):
                continue
            for entry in 96-byte chunks of frame.data:   # a trailing partial chunk is ignored
                scheme    = entry[31]
                data_hash = entry[32:64]
                key       = entry[64:96]
                if data_hash == Bytes32():
                    data_hash = frame_signature_hash(tx)
                dependencies.append((scheme, data_hash, key))

    dependencies = sorted(set(dependencies))   # lexicographic over (scheme, data_hash, key)

    sphincs = keccak256(concat(data_hash || key for entries with scheme == 0x10))
    if every entry has scheme == 0x10 (including no entries):
        return sphincs
    other = keccak256(concat(data_hash || key for entries with scheme != 0x10))
    return keccak256(sphincs || other || b"eip8288/leanstark-deps" zero-padded to 32 bytes)

frame_signature_hash(tx) -> Bytes32:
    # EIP-8141 canonical signature hash with ethereum/EIPs#12502:
    # every signature entry [scheme, signer, msg, signature] whose msg is empty has its
    # signature bytes replaced by the RLP integer of their length.
    return keccak256(0x06 || rlp(tx with the signatures rewritten as above))
```

- Scheme `0x10` is leanSPHINCS. Every other scheme, including the generic
  leanSTARK scheme `0x11`, goes into the second list under the
  `eip8288/leanstark-deps` domain. Accepting `0x11` deviates from EIP-8288.
- `DEPS_HASH` is Keccak-256. EIP-8288 leaves the hash function open.
- Frame transactions encoded before ethereum/EIPs#12502 (signature bytes elided,
  three fee items) are refused.

##### Modified `is_valid_versioned_hashes`

*Note*: The function signature is unchanged. In Daisugi, the versioned hashes of
a payload also include the `blob_hashes` of its EIP-8141 frame transactions
(type `0x06`). Their RLP envelope is
`[chain_id, nonce_keys?, nonce, sender, frames, signatures, fees, blob_hashes, references?]`,
where `nonce_keys` is present for keyed-nonce (EIP-8250) transactions and `fees`
is exactly `[max_fee, max_priority_fee_per_gas]`.

```python
def is_valid_versioned_hashes(
    self: ExecutionEngine, new_payload_request: NewPayloadRequest
) -> bool:
    """
    Return ``True`` if and only if the version hashes computed by the blob transactions of
    ``new_payload_request.execution_payload`` matches ``new_payload_request.versioned_hashes``.

    [Modified in Daisugi:EIP8141]
    The blob hashes of frame transactions are included.
    """
```

### Block processing

#### Execution payload

##### Modified `process_execution_payload`

*Note*: The function `process_execution_payload` is modified to cache
`recursive_stark_proof_root` in the execution payload header.

```python
def process_execution_payload(
    state: BeaconState, body: BeaconBlockBody, execution_engine: ExecutionEngine
) -> None:
    payload = body.execution_payload

    # Verify consistency of the parent hash with respect to the previous execution payload header
    assert payload.parent_hash == state.latest_execution_payload_header.block_hash
    # Verify prev_randao
    assert payload.prev_randao == get_randao_mix(state, get_current_epoch(state))
    # Verify timestamp
    assert payload.timestamp == compute_time_at_slot(state.genesis_time, state.slot)
    # Verify commitments are under limit
    assert len(body.blob_kzg_commitments) <= MAX_BLOBS_PER_BLOCK_ELECTRA

    # Compute versioned hashes
    versioned_hashes = VersionedHashes()
    for commitment in body.blob_kzg_commitments:
        versioned_hashes.append(kzg_commitment_to_versioned_hash(commitment))

    # Verify the execution payload is valid
    assert execution_engine.verify_and_notify_new_payload(
        NewPayloadRequest(
            execution_payload=payload,
            versioned_hashes=versioned_hashes,
            parent_beacon_block_root=state.latest_block_header.parent_root,
            execution_requests=body.execution_requests,
        )
    )

    # Cache execution payload header
    state.latest_execution_payload_header = ExecutionPayloadHeader(
        parent_hash=payload.parent_hash,
        fee_recipient=payload.fee_recipient,
        state_root=payload.state_root,
        receipts_root=payload.receipts_root,
        logs_bloom=payload.logs_bloom,
        prev_randao=payload.prev_randao,
        block_number=payload.block_number,
        gas_limit=payload.gas_limit,
        gas_used=payload.gas_used,
        timestamp=payload.timestamp,
        extra_data=payload.extra_data,
        base_fee_per_gas=payload.base_fee_per_gas,
        block_hash=payload.block_hash,
        transactions_root=hash_tree_root(payload.transactions),
        withdrawals_root=hash_tree_root(payload.withdrawals),
        blob_gas_used=payload.blob_gas_used,
        excess_blob_gas=payload.excess_blob_gas,
        # [New in Daisugi:EIP8288]
        recursive_stark_proof_root=hash_tree_root(payload.recursive_stark_proof),
    )
```
