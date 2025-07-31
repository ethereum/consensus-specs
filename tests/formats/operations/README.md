# Operations tests

The different kinds of operations ("transactions") are tested individually with
test handlers.

## Test case format

### `meta.yaml`

```yaml
description: string    -- Optional description of test case, purely for debugging purposes.
                          Tests should use the directory name of the test case as identifier, not the description.
bls_setting: int       -- see general test-format spec.
```

### `pre.ssz_snappy`

An SSZ-snappy encoded `BeaconState`, the state before applying the operation.

### `<input-name>.ssz_snappy`

An SSZ-snappy encoded operation object, e.g. a `ProposerSlashing`, or `Deposit`.

### `post.ssz_snappy`

An SSZ-snappy encoded `BeaconState`, the state after applying the operation. No
value if operation processing is aborted.

## Condition

A handler of the `operations` test-runner should process these cases, calling
the corresponding processing implementation. This excludes the other parts of
the block-transition.

Operations:

| *`operation-name`*        | *`operation-object`*         | *`input name`*          | *`processing call`*                                                            |
| ------------------------- | ---------------------------- | ----------------------- | ------------------------------------------------------------------------------ |
| `attestation`             | `Attestation`                | `attestation`           | `process_attestation(state, attestation)`                                      |
| `attester_slashing`       | `AttesterSlashing`           | `attester_slashing`     | `process_attester_slashing(state, attester_slashing)`                          |
| `block_header`            | `BeaconBlock`                | **`block`**             | `process_block_header(state, block)`                                           |
| `deposit`                 | `Deposit`                    | `deposit`               | `process_deposit(state, deposit)`                                              |
| `proposer_slashing`       | `ProposerSlashing`           | `proposer_slashing`     | `process_proposer_slashing(state, proposer_slashing)`                          |
| `voluntary_exit`          | `SignedVoluntaryExit`        | `voluntary_exit`        | `process_voluntary_exit(state, voluntary_exit)`                                |
| `sync_aggregate`          | `SyncAggregate`              | `sync_aggregate`        | `process_sync_aggregate(state, sync_aggregate)` (new in Altair)                |
| `execution_payload`       | `BeaconBlockBody`            | **`body`**              | `process_execution_payload(state, body)` (new in Bellatrix)                    |
| `withdrawals`             | `ExecutionPayload`           | `execution_payload`     | `process_withdrawals(state, execution_payload)` (new in Capella)               |
| `bls_to_execution_change` | `SignedBLSToExecutionChange` | `address_change`        | `process_bls_to_execution_change(state, address_change)` (new in Capella)      |
| `deposit_request`         | `DepositRequest`             | `deposit_request`       | `process_deposit_request(state, deposit_request)` (new in Electra)             |
| `withdrawal_request`      | `WithdrawalRequest`          | `withdrawal_request`    | `process_withdrawal_request(state, withdrawal_request)` (new in Electra)       |
| `consolidation_request`   | `ConsolidationRequest`       | `consolidation_request` | `process_consolidation_request(state, consolidation_request)` (new in Electra) |
| `payload_attestation`     | `PayloadAttestation`         | `payload_attestation`   | `process_payload_attestation(state, payload_attestation)` (new in EIP7732)     |

Note that `block_header` is not strictly an operation (and is a full `Block`),
but processed in the same manner, and hence included here.

The `execution_payload` processing normally requires a
`verify_execution_state_transition(execution_payload)`, a responsibility of an
(external) execution engine. During testing this execution is mocked, an
`execution.yml` is provided instead: a dict containing an `execution_valid`
boolean field with the verification result.

The resulting state should match the expected `post` state, or if the `post`
state is left blank, the handler should reject the input operation as invalid.
