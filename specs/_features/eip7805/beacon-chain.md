# EIP-7805 -- The Beacon Chain

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Domain types](#domain-types)
- [Preset](#preset)
  - [Inclusion List Committee](#inclusion-list-committee)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`InclusionList`](#inclusionlist)
    - [`SignedInclusionList`](#signedinclusionlist)
  - [Predicates](#predicates)
    - [New `is_valid_inclusion_list_signature`](#new-is_valid_inclusion_list_signature)
  - [Beacon State accessors](#beacon-state-accessors)
    - [New `get_inclusion_list_committee`](#new-get_inclusion_list_committee)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Execution engine](#execution-engine)
    - [Request data](#request-data)
      - [Modified `NewPayloadRequest`](#modified-newpayloadrequest)
    - [Engine APIs](#engine-apis)
      - [Modified `is_valid_block_hash`](#modified-is_valid_block_hash)
      - [Modified `notify_new_payload`](#modified-notify_new_payload)
      - [Modified `verify_and_notify_new_payload`](#modified-verify_and_notify_new_payload)
      - [Modified `process_execution_payload`](#modified-process_execution_payload)

<!-- mdformat-toc end -->

## Introduction

This is the beacon chain specification to add EIP-7805 / fork-choice enforced, committee-based inclusion list (FOCIL) mechanism to allow forced transaction inclusion. Refers to the following posts:

- [Fork-Choice enforced Inclusion Lists (FOCIL): A simple committee-based inclusion list proposal](https://ethresear.ch/t/fork-choice-enforced-inclusion-lists-focil-a-simple-committee-based-inclusion-list-proposal/19870/1)
- [FOCIL CL & EL workflow](https://ethresear.ch/t/focil-cl-el-workflow/20526)
  *Note*: This specification is built upon [Electra](../../electra/beacon-chain.md) and is under active development.

## Constants

### Domain types

| Name                              | Value                      |
| --------------------------------- | -------------------------- |
| `DOMAIN_INCLUSION_LIST_COMMITTEE` | `DomainType('0x0C000000')` |

## Preset

### Inclusion List Committee

| Name                            | Value                |
| ------------------------------- | -------------------- |
| `INCLUSION_LIST_COMMITTEE_SIZE` | `uint64(2**4)` (=16) |

## Containers

### New containers

#### `InclusionList`

```python
class InclusionList(Container):
    slot: Slot
    validator_index: ValidatorIndex
    inclusion_list_committee_root: Root
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]
```

#### `SignedInclusionList`

```python
class SignedInclusionList(Container):
    message: InclusionList
    signature: BLSSignature
```

### Predicates

#### New `is_valid_inclusion_list_signature`

```python
def is_valid_inclusion_list_signature(
        state: BeaconState,
        signed_inclusion_list: SignedInclusionList) -> bool:
    """
    Check if ``signed_inclusion_list`` has a valid signature.
    """
    message = signed_inclusion_list.message
    index = message.validator_index
    pubkey = state.validators[index].pubkey
    domain = get_domain(state, DOMAIN_INCLUSION_LIST_COMMITTEE, compute_epoch_at_slot(message.slot))
    signing_root = compute_signing_root(message, domain)
    return bls.Verify(pubkey, signing_root, signed_inclusion_list.signature)
```

### Beacon State accessors

#### New `get_inclusion_list_committee`

```python
def get_inclusion_list_committee(state: BeaconState,
                                 slot: Slot) -> Vector[ValidatorIndex, INCLUSION_LIST_COMMITTEE_SIZE]:
    epoch = compute_epoch_at_slot(slot)
    seed = get_seed(state, epoch, DOMAIN_INCLUSION_LIST_COMMITTEE)
    indices = get_active_validator_indices(state, epoch)
    start = (slot % SLOTS_PER_EPOCH) * INCLUSION_LIST_COMMITTEE_SIZE
    end = start + INCLUSION_LIST_COMMITTEE_SIZE
    return [
        indices[compute_shuffled_index(uint64(i % len(indices)), uint64(len(indices)), seed)]
        for i in range(start, end)
    ]
```

## Beacon chain state transition function

### Execution engine

#### Request data

##### Modified `NewPayloadRequest`

```python
@dataclass
class NewPayloadRequest(object):
    execution_payload: ExecutionPayload
    versioned_hashes: Sequence[VersionedHash]
    parent_beacon_block_root: Root
    execution_requests: ExecutionRequests
    inclusion_list_transactions: Sequence[Transaction]  # [New in EIP-7805]
```

#### Engine APIs

##### Modified `is_valid_block_hash`

*Note*: The function `is_valid_block_hash` is modified to include the additional `inclusion_list_transactions`.

```python
def is_valid_block_hash(self: ExecutionEngine,
                        execution_payload: ExecutionPayload,
                        parent_beacon_block_root: Root,
                        execution_requests_list: Sequence[bytes],
                        inclusion_list_transactions: Sequence[Transaction]) -> bool:
    """
    Return ``True`` if and only if ``execution_payload.block_hash`` is computed correctly.
    """
    ...
```

##### Modified `notify_new_payload`

*Note*: The function `notify_new_payload` is modified to include the additional `inclusion_list_transactions`.

```python
def notify_new_payload(self: ExecutionEngine,
                       execution_payload: ExecutionPayload,
                       parent_beacon_block_root: Root,
                       execution_requests_list: Sequence[bytes],
                       inclusion_list_transactions: Sequence[Transaction]) -> bool:
    """
    Return ``True`` if and only if ``execution_payload`` and ``execution_requests_list``
    are valid with respect to ``self.execution_state``.
    """
    # TODO: move this outside of notify_new_payload.
    # If execution client returns block does not satisfy inclusion list transactions, cache the block
    # store.unsatisfied_inclusion_list_blocks.add(execution_payload.block_root)
    ...
```

##### Modified `verify_and_notify_new_payload`

*Note*: The function `verify_and_notify_new_payload` is modified to pass the additional parameter
`inclusion_list_transactions` when calling `notify_new_payload` in EIP-7805.

```python
def verify_and_notify_new_payload(self: ExecutionEngine,
                                  new_payload_request: NewPayloadRequest) -> bool:
    """
    Return ``True`` if and only if ``new_payload_request`` is valid with respect to ``self.execution_state``.
    """
    execution_payload = new_payload_request.execution_payload
    parent_beacon_block_root = new_payload_request.parent_beacon_block_root
    execution_requests_list = get_execution_requests_list(new_payload_request.execution_requests)
    inclusion_list_transactions = new_payload_request.inclusion_list_transactions # [New in EIP-7805]

    if b'' in execution_payload.transactions:
        return False

    if not self.is_valid_block_hash(
            execution_payload,
            parent_beacon_block_root,
            execution_requests_list):
        return False

    if not self.is_valid_versioned_hashes(new_payload_request):
        return False

    # [Modified in EIP-7805]
    if not self.notify_new_payload(
            execution_payload,
            parent_beacon_block_root,
            execution_requests_list,
            inclusion_list_transactions):
        return False

    return True
```

##### Modified `process_execution_payload`

```python
def process_execution_payload(state: BeaconState, body: BeaconBlockBody, execution_engine: ExecutionEngine) -> None:
    payload = body.execution_payload

    # Verify consistency of the parent hash with respect to the previous execution payload header
    assert payload.parent_hash == state.latest_execution_payload_header.block_hash
    # Verify prev_randao
    assert payload.prev_randao == get_randao_mix(state, get_current_epoch(state))
    # Verify timestamp
    assert payload.timestamp == compute_timestamp_at_slot(state, state.slot)
    # Verify commitments are under limit
    assert len(body.blob_kzg_commitments) <= MAX_BLOBS_PER_BLOCK_ELECTRA
    # Verify the execution payload is valid
    versioned_hashes = [kzg_commitment_to_versioned_hash(commitment) for commitment in body.blob_kzg_commitments]
    # Verify inclusion list transactions
    inclusion_list_transactions: Sequence[Transaction] = []  # TODO: where do we get this?
    # Verify the payload with the execution engine
    assert execution_engine.verify_and_notify_new_payload(
        NewPayloadRequest(
            execution_payload=payload,
            versioned_hashes=versioned_hashes,
            parent_beacon_block_root=state.latest_block_header.parent_root,
            execution_requests=body.execution_requests,
            inclusion_list_transactions=inclusion_list_transactions,
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
    )
```
