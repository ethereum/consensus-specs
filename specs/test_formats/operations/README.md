# Operations tests

The different kinds of operations ("transactions") are tested individually with test handlers.

## Test case format

```yaml
description: string                    -- description of test case, purely for debugging purposes
bls_required: bool                     -- optional, true if the test validity is strictly dependent on BLS being ON. False otherwise.
bls_ignored: bool                      -- optional, true if the test validity is strictly dependent on BLS being OFF. False otherwise.
pre: BeaconState                       -- state before applying the deposit
<operation-name>: <operation-object>   -- the YAML encoded operation, e.g. a "ProposerSlashing", or "Deposit".
post: BeaconState                      -- state after applying the deposit. No value if deposit processing is aborted.
```

Note: if both `bls_required` and `bls_ignored` are false (or simply not included),
 then the test consumer can freely choose to run with BLS ON or OFF.
One may choose for OFF for performance reasons during repeated testing. Otherwise it is recommended to run with BLS ON.

## Condition

A handler of the `operations` should process these cases, 
 calling the corresponding processing implementation.

Operations:

| *`operation-name`*      | *`operation-object`* | *`input name`*       | *`processing call`*                                    |
|-------------------------|----------------------|----------------------|--------------------------------------------------------|
| `attestation`           | `Attestation`        | `attestation`        | `process_deposit(state, attestation)`                  |
| `attester_slashing`     | `AttesterSlashing`   | `attester_slashing`  | `process_deposit(state, attester_slashing)`            |
| `block_header`          | `Block`              | `block`              | `process_block_header(state, block)`                   |
| `deposit`               | `Deposit`            | `deposit`            | `process_deposit(state, deposit)`                      |
| `proposer_slashing`     | `ProposerSlashing`   | `proposer_slashing`  | `process_proposer_slashing(state, proposer_slashing)`  |
| `transfer`              | `Transfer`           | `transfer`           | `process_transfer(state, transfer)`                    |
| `voluntary_exit`        | `VoluntaryExit`      | `voluntary_exit`     | `process_voluntary_exit(state, voluntary_exit)`        |

Note that `block_header` is not strictly an operation (and is a full `Block`), but processed in the same manner, and hence included here. 

The resulting state should match the expected `post` state, or if the `post` state is left blank,
 the handler should reject the input operation as invalid.
