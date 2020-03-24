# Operations tests

The different kinds of operations ("transactions") are tested individually with test handlers.

## Test case format

### `meta.yaml`

```yaml
description: string    -- Optional description of test case, purely for debugging purposes.
                          Tests should use the directory name of the test case as identifier, not the description.
bls_setting: int       -- see general test-format spec.
```

### `pre.yaml`

A YAML-encoded `BeaconState`, the state before applying the operation.

Also available as `pre.ssz`.

### `<input-name>.yaml`

A YAML-encoded operation object, e.g. a `ProposerSlashing`, or `Deposit`.

Also available as `<input-name>.ssz`.

### `post.yaml`

A YAML-encoded `BeaconState`, the state after applying the operation. No value if operation processing is aborted.

Also available as `post.ssz`.


## Condition

A handler of the `operations` test-runner should process these cases,
 calling the corresponding processing implementation.
This excludes the other parts of the block-transition.

Operations:

| *`operation-name`*      | *`operation-object`*  | *`input name`*       | *`processing call`*                                    |
|-------------------------|-----------------------|----------------------|--------------------------------------------------------|
| `attestation`           | `Attestation`         | `attestation`        | `process_attestation(state, attestation)`              |
| `attester_slashing`     | `AttesterSlashing`    | `attester_slashing`  | `process_attester_slashing(state, attester_slashing)`  |
| `block_header`          | `BeaconBlock`         | **`block`**          | `process_block_header(state, block)`                   |
| `deposit`               | `Deposit`             | `deposit`            | `process_deposit(state, deposit)`                      |
| `proposer_slashing`     | `ProposerSlashing`    | `proposer_slashing`  | `process_proposer_slashing(state, proposer_slashing)`  |
| `voluntary_exit`        | `SignedVoluntaryExit` | `voluntary_exit`     | `process_voluntary_exit(state, voluntary_exit)`        |

Note that `block_header` is not strictly an operation (and is a full `Block`), but processed in the same manner, and hence included here.

The resulting state should match the expected `post` state, or if the `post` state is left blank,
 the handler should reject the input operation as invalid.
