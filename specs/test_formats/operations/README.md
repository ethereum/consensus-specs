# Operations tests

The different kinds of operations ("transactions") are tested individually with test handlers.

## Test case format

```yaml
description: string                    -- description of test case, purely for debugging purposes
bls_setting: int                       -- see general test-format spec.
pre: BeaconState                       -- state before applying the operation
<operation-name>: <operation-object>   -- the YAML encoded operation, e.g. a "ProposerSlashing", or "Deposit".
post: BeaconState                      -- state after applying the operation. No value if operation processing is aborted.
```

## Condition

A handler of the `operations` test-runner should process these cases, 
 calling the corresponding processing implementation.

Operations:

| *`operation-name`*      | *`operation-object`* | *`input name`*       | *`processing call`*                                    |
|-------------------------|----------------------|----------------------|--------------------------------------------------------|
| `attestation`           | `Attestation`        | `attestation`        | `process_attestation(state, attestation)`              |
| `attester_slashing`     | `AttesterSlashing`   | `attester_slashing`  | `process_attester_slashing(state, attester_slashing)`  |
| `block_header`          | `Block`              | `block`              | `process_block_header(state, block)`                   |
| `deposit`               | `Deposit`            | `deposit`            | `process_deposit(state, deposit)`                      |
| `proposer_slashing`     | `ProposerSlashing`   | `proposer_slashing`  | `process_proposer_slashing(state, proposer_slashing)`  |
| `transfer`              | `Transfer`           | `transfer`           | `process_transfer(state, transfer)`                    |
| `voluntary_exit`        | `VoluntaryExit`      | `voluntary_exit`     | `process_voluntary_exit(state, voluntary_exit)`        |

Note that `block_header` is not strictly an operation (and is a full `Block`), but processed in the same manner, and hence included here. 

The resulting state should match the expected `post` state, or if the `post` state is left blank,
 the handler should reject the input operation as invalid.
