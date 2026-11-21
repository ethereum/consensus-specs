# EIP-8025 -- Guest Program

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Guest inputs](#guest-inputs)
  - [New `PrivateInput`](#new-privateinput)
- [Guest processing](#guest-processing)
  - [New `verify_execution_transition`](#new-verify_execution_transition)
- [Execution engine](#execution-engine)
- [Binding by comparison](#binding-by-comparison)

<!-- mdformat-toc end -->

## Introduction

This document defines the private input and the processing logic of the guest
program. Each run proves one execution payload and commits to the
`NewPayloadRequestCommitment` of the payload it validated. The public input it
commits to is the `PublicInput` defined in [beacon-chain.md](./beacon-chain.md).

The guest reads no beacon state. It commits the payload fields the consensus
layer verifies, and the consensus layer derives the same commitment from the
`ExecutionPayloadBid` the beacon block committed to.

## Guest inputs

The guest inputs are implementation-level dataclasses, not consensus SSZ
containers.

### New `PrivateInput`

```python
@dataclass
class PrivateInput:
    new_payload_request: NewPayloadRequest
    execution_witness: Any
```

- `new_payload_request` is the payload request the guest validates.
- `execution_witness` has the execution-specs type `ExecutionWitness`. The
  execution engine running in the guest is bound to it.

## Guest processing

### New `verify_execution_transition`

```python
def verify_execution_transition(
    execution_engine: ExecutionEngine,
    private_input: PrivateInput,
) -> PublicInput:
    new_payload_request = private_input.new_payload_request
    payload = new_payload_request.execution_payload

    # Gloas enforces these limits only in payload envelope gossip. The gossip
    # helper raises ``GossipReject``, which fails the proof like an assertion.
    verify_execution_requests_limits(new_payload_request.execution_requests)
    assert len(payload.withdrawals) <= MAX_WITHDRAWALS_PER_PAYLOAD

    # Validate the payload statelessly
    assert execution_engine.verify_and_notify_new_payload(new_payload_request)

    return PublicInput(
        new_payload_request=NewPayloadRequestCommitment(
            execution_payload=ExecutionPayloadCommitment(
                parent_hash=payload.parent_hash,
                prev_randao=payload.prev_randao,
                gas_limit=payload.gas_limit,
                timestamp=payload.timestamp,
                block_hash=payload.block_hash,
                withdrawals=payload.withdrawals,
                slot_number=payload.slot_number,
            ),
            versioned_hashes=new_payload_request.versioned_hashes,
            parent_beacon_block_root=new_payload_request.parent_beacon_block_root,
            execution_requests_root=hash_tree_root(new_payload_request.execution_requests),
        ),
        successful_validation=Boolean(True),
        chain_id=DEPOSIT_CHAIN_ID,
        schema_id=STATELESS_INPUT_SCHEMA_ID,
    )
```

Any failed assertion or raised exception fails the proof.

## Execution engine

Inside the guest, the execution engine has no execution state. Its
`verify_and_notify_new_payload` validates the payload statelessly against the
execution witness, with the guarantees the `ExecutionEngine` specification
requires of that function. It MUST validate the payload under the chain ID
`DEPOSIT_CHAIN_ID` and the fork rules the guest implements, and MUST reject a
payload whose timestamp falls outside that fork. The guest MUST NOT take the
chain ID or the fork schedule from its private input.

Validation MUST be equivalent to the execution-specs
`verify_stateless_new_payload` applied to a `StatelessInput` built from the
request, the execution witness and `DEPOSIT_CHAIN_ID`.

## Binding by comparison

The guest asserts nothing about the beacon chain. Each field of the commitment
is compared against the bid and the beacon state by the verifier, through the
public input the proof engine reconstructs in `get_execution_proof`:

| Commitment field           | Verified against                                     |
| -------------------------- | ---------------------------------------------------- |
| `parent_hash`              | `bid.parent_block_hash`                              |
| `prev_randao`              | `bid.prev_randao`                                    |
| `gas_limit`                | `bid.gas_limit`                                      |
| `timestamp`                | `compute_time_at_slot(state.genesis_time, bid.slot)` |
| `block_hash`               | `bid.block_hash`                                     |
| `withdrawals`              | `state.payload_expected_withdrawals`                 |
| `slot_number`              | `bid.slot`                                           |
| `versioned_hashes`         | `bid.blob_kzg_commitments`                           |
| `parent_beacon_block_root` | `state.latest_block_header.parent_root`              |
| `execution_requests_root`  | `bid.execution_requests_root`                        |

A proof whose commitment differs in any field does not verify. The payload's
remaining fields are bound through `block_hash`, which the execution engine
recomputes from the payload.

The guest does not prove data availability, and a proof does not imply that the
payload was revealed.
