# Report: `process_withdrawals` Input/Output Space

*Note*: This report is AI-generated and is not an authoritative source of truth.

## Function Signature

```python
def process_withdrawals(state: BeaconState) -> None: ...
```

Location:
[specs/gloas/beacon-chain.md](../../../../../../../specs/gloas/beacon-chain.md)

______________________________________________________________________

## Input Space (State Fields Read)

| Field                                                    | Type                                                                | Value Space                                                                                                                                                          | Purpose                                 |
| -------------------------------------------------------- | ------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| `state.slot`                                             | `Slot`                                                              | `uint64` in [0, 2^64-1]. Derives `epoch = slot // SLOTS_PER_EPOCH`. Compared against `withdrawable_epoch` fields.                                                    | Compute current epoch                   |
| `state.latest_execution_payload_bid.block_hash`          | `Hash32`                                                            | `Bytes32`. **Bound to** `latest_block_hash`: must equal for function to execute (early exit if not equal).                                                           | Check if parent block was full          |
| `state.latest_block_hash`                                | `Hash32`                                                            | `Bytes32`. **Bound to** `latest_execution_payload_bid.block_hash` for `is_parent_block_full()` check.                                                                | Compare with committed bid              |
| `state.next_withdrawal_index`                            | `WithdrawalIndex`                                                   | `uint64` in [0, 2^64-1]. Monotonically increasing. Assigned to each withdrawal created.                                                                              | Starting withdrawal index               |
| `state.next_withdrawal_validator_index`                  | `ValidatorIndex`                                                    | `uint64` in \[0, `len(validators)`-1\]. **Bound to** `len(validators)`: wraps via modulo.                                                                            | Starting validator sweep position       |
| `state.next_withdrawal_builder_index`                    | `BuilderIndex`                                                      | `uint64` in \[0, `len(builders)`-1\]. **Bound to** `len(builders)`: wraps via modulo.                                                                                | Starting builder sweep position         |
| `state.builders`                                         | `List[Builder, BUILDER_REGISTRY_LIMIT]`                             | Length in [0, 2^40]. Separate non-validating staked actors.                                                                                                          | Builder registry                        |
| (in `builders`) `.pubkey`                                | `BLSPubkey`                                                         | `Bytes48`. Builder's public key.                                                                                                                                     | Builder identification                  |
| (in `builders`) `.execution_address`                     | `ExecutionAddress`                                                  | `Bytes20`. Withdrawal destination for builder sweep withdrawals.                                                                                                     | Sweep withdrawal destination            |
| (in `builders`) `.balance`                               | `Gwei`                                                              | `uint64`. Builder's staked balance. Decreased by withdrawal amounts.                                                                                                 | Builder balance for withdrawals         |
| (in `builders`) `.withdrawable_epoch`                    | `Epoch`                                                             | `uint64`. **Bound to** `state.slot`: builder sweep withdrawal ready when `<= current_epoch`.                                                                         | Check if builder sweep eligible         |
| `state.builder_pending_withdrawals`                      | `List[BuilderPendingWithdrawal, BUILDER_PENDING_WITHDRAWALS_LIMIT]` | Length in [0, 2^20]. Processed first. Max `MAX_WITHDRAWALS_PER_PAYLOAD - 1` can produce withdrawals.                                                                 | Iterate for builder pending withdrawals |
| (in `builder_pending_withdrawals`) `.builder_index`      | `BuilderIndex`                                                      | `uint64` in \[0, `len(builders)`-1\]. **Index into** `builders[]`.                                                                                                   | Identify builder in registry            |
| (in `builder_pending_withdrawals`) `.fee_recipient`      | `ExecutionAddress`                                                  | `Bytes20`. Withdrawal destination. Independent of builder's own `execution_address`.                                                                                 | Withdrawal destination                  |
| (in `builder_pending_withdrawals`) `.amount`             | `Gwei`                                                              | `uint64`. Requested amount. Actual = `min(amount, builder.balance)`.                                                                                                 | Withdrawal amount                       |
| `state.pending_partial_withdrawals`                      | `List[PendingPartialWithdrawal, PENDING_PARTIAL_WITHDRAWALS_LIMIT]` | Length in [0, 2^27]. Processed second. Max `MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP` (8) processed per block.                                                     | Iterate for partial withdrawals         |
| (in `pending_partial_withdrawals`) `.withdrawable_epoch` | `Epoch`                                                             | `uint64`. **Bound to** `state.slot`: ready when `<= current_epoch`. If `>`, breaks processing loop.                                                                  | Check if withdrawal is ready            |
| (in `pending_partial_withdrawals`) `.validator_index`    | `ValidatorIndex`                                                    | `uint64` in \[0, `len(validators)`-1\]. **Index into** `validators[]` and `balances[]`.                                                                              | Identify validator                      |
| (in `pending_partial_withdrawals`) `.amount`             | `Gwei`                                                              | `uint64`. Requested amount. Actual = `min(balance - MIN_ACTIVATION_BALANCE, amount)`.                                                                                | Withdrawal amount                       |
| `state.balances[*]`                                      | `Gwei`                                                              | `uint64` in [0, 2^64-1]. **Same length as** `validators[]`. Must have excess over `MIN_ACTIVATION_BALANCE` (32 ETH) for partial withdrawals.                         | Check available balance                 |
| `state.validators`                                       | `List[Validator, VALIDATOR_REGISTRY_LIMIT]`                         | Length in [0, 2^40]. **Same length as** `balances[]`. All index references must be < len.                                                                            | Validator data                          |
| (in `validators`) `[*].effective_balance`                | `Gwei`                                                              | `uint64` in [0, 2048 ETH]. **Constraint**: partial withdrawals require `>= MIN_ACTIVATION_BALANCE` (32 ETH).                                                         | Check sufficient balance                |
| (in `validators`) `[*].exit_epoch`                       | `Epoch`                                                             | `uint64`. **Constraint**: partial withdrawals require `== FAR_FUTURE_EPOCH`. If set, validator is exiting and ineligible.                                            | Check if validator exiting              |
| (in `validators`) `[*].withdrawable_epoch`               | `Epoch`                                                             | `uint64`. **Bound to** `state.slot` for full withdrawal eligibility. Typically `FAR_FUTURE_EPOCH` if not exiting.                                                    | For full withdrawal check               |
| (in `validators`) `[*].withdrawal_credentials`           | `Bytes32`                                                           | `Bytes32`. **Prefix byte**: `0x01`=ETH1, `0x02`=compounding. **Bytes [12:32]** = execution address. Validators need `0x01`/`0x02` prefix for withdrawal eligibility. | Extract withdrawal address              |

______________________________________________________________________

## Output Space (State Fields Modified)

| Field                                   | Type                                                                | Value Space                                                                                                                             | Modification                                  |
| --------------------------------------- | ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| `state.payload_expected_withdrawals`    | `List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD]`                     | Length in \[0, `MAX_WITHDRAWALS_PER_PAYLOAD`\]. **Derived from** input `next_withdrawal_index` (sequential), pending lists, and sweeps. | **Set** to computed withdrawals list          |
| `state.balances[*]`                     | `Gwei`                                                              | `uint64`. **Decreased by** withdrawal amounts for each validator withdrawal.                                                            | **Decreased** by validator withdrawal amounts |
| `state.builders[*].balance`             | `Gwei`                                                              | `uint64`. **Decreased by** withdrawal amounts for each builder withdrawal. New value = old - min(withdrawal.amount, balance).           | **Decreased** by builder withdrawal amounts   |
| `state.builder_pending_withdrawals`     | `List[BuilderPendingWithdrawal, BUILDER_PENDING_WITHDRAWALS_LIMIT]` | New length = old length - `processed_builder_withdrawals_count`. **Sliced** to remove processed items.                                  | **Sliced** - removes first N processed items  |
| `state.pending_partial_withdrawals`     | `List[PendingPartialWithdrawal, PENDING_PARTIAL_WITHDRAWALS_LIMIT]` | New length = old length - `processed_partial_withdrawals_count`.                                                                        | **Sliced** - removes first N processed items  |
| `state.next_withdrawal_index`           | `WithdrawalIndex`                                                   | New value = `payload_expected_withdrawals[-1].index + 1` if any withdrawals, else unchanged.                                            | **Incremented** by number of withdrawals      |
| `state.next_withdrawal_builder_index`   | `BuilderIndex`                                                      | **Bound to** `len(builders)` (wraps via modulo). Updated based on builder sweep progress.                                               | **Updated** based on builder sweep progress   |
| `state.next_withdrawal_validator_index` | `ValidatorIndex`                                                    | **Bound to** `len(validators)` (wraps via modulo). Updated based on validator sweep progress.                                           | **Updated** based on validator sweep progress |

______________________________________________________________________

## Early Exit Condition

If `is_parent_block_full(state)` returns `False` (i.e.,
`latest_execution_payload_bid.block_hash != latest_block_hash`), the function
returns immediately with **no state modifications**.

______________________________________________________________________

## Key Constants

| Constant                                     | Value                 | Description                           |
| -------------------------------------------- | --------------------- | ------------------------------------- |
| `MAX_WITHDRAWALS_PER_PAYLOAD`                | 16                    | Max withdrawals per execution payload |
| `MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP`       | 16,384                | Max validators checked per sweep      |
| `MAX_BUILDERS_PER_WITHDRAWALS_SWEEP`         | 16,384                | Max builders checked per sweep        |
| `MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP` | 8                     | Max partial withdrawals processed     |
| `VALIDATOR_REGISTRY_LIMIT`                   | 2^40                  | Max validators in registry            |
| `BUILDER_REGISTRY_LIMIT`                     | 2^40                  | Max builders in registry              |
| `BUILDER_PENDING_WITHDRAWALS_LIMIT`          | 2^20 (1,048,576)      | Max pending builder withdrawals       |
| `PENDING_PARTIAL_WITHDRAWALS_LIMIT`          | 2^27 (134,217,728)    | Max pending partial withdrawals       |
| `MIN_ACTIVATION_BALANCE`                     | 32 ETH (32x10^9 Gwei) | Minimum balance for active validator  |
| `FAR_FUTURE_EPOCH`                           | 2^64-1                | Sentinel for "not set" epoch          |

______________________________________________________________________

## Key Cross-Field Constraints

1. **Index Alignment**:

   - `len(validators) == len(balances)` always
   - All validator indices must be `< len(validators)`
   - All builder indices must be `< len(builders)`

2. **Epoch Gating**: All `withdrawable_epoch` fields are compared against
   `current_epoch = compute_epoch_at_slot(state.slot)`.

3. **Balance Thresholds by Withdrawal Type**:

   - **Builder pending**:
     `actual_amount = min(requested_amount, builder.balance)` (builder balance
     can go to zero)
   - **Builder sweep**: requires `builder.withdrawable_epoch <= epoch` AND
     `builder.balance > 0`; withdraws full `builder.balance`
   - **Partial**: requires `effective_balance >= MIN_ACTIVATION_BALANCE` AND
     `balance > MIN_ACTIVATION_BALANCE` AND `exit_epoch == FAR_FUTURE_EPOCH`
   - **Full**: requires `has_execution_withdrawal_credential` AND
     `withdrawable_epoch <= epoch` AND `balance > 0`

4. **Processing Order & Caps** (combined constraint on output):

   - Builder pending withdrawals: processed first, up to
     `MAX_WITHDRAWALS_PER_PAYLOAD - 1` (one slot reserved for validator sweep)
   - Partial withdrawals: processed second, capped by
     `MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP`, must leave at least one slot
   - Builder sweep: processed third, up to
     `MAX_WITHDRAWALS_PER_PAYLOAD - 1` (one slot reserved for validator sweep)
   - Validator sweep: processed last, at least one slot reserved, capped by
     `MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP`
   - Total output: `MAX_WITHDRAWALS_PER_PAYLOAD`

5. **Early Exit Binding**: Function executes only when
   `latest_execution_payload_bid.block_hash == latest_block_hash`.

______________________________________________________________________

## Builder Model (PR #4788)

Builders are **separate non-validating staked actors** stored in
`state.builders[]`. They are NOT validators with special credentials.

**Key differences from validators**:

- Builders have their own registry (`state.builders`) separate from
  `state.validators`
- Builder balances are in `Builder.balance`, not `state.balances[]`
- Builders cannot be slashed
- Builders use `BuilderIndex` type, which is converted to/from `ValidatorIndex`
  using `convert_builder_index_to_validator_index()` and
  `convert_validator_index_to_builder_index()`
- In `Withdrawal` output, builder withdrawals use a converted validator index
  (with `BUILDER_INDEX_FLAG` bit set)

**Builder withdrawal types**:

1. **Builder Pending Withdrawals**: Pending builder withdrawals stored in
   `state.builder_pending_withdrawals`. Uses `fee_recipient` as destination.
2. **Builder Sweep Withdrawals**: Automatic withdrawals when
   `builder.withdrawable_epoch <= current_epoch`. Uses
   `builder.execution_address` as destination and withdraws full balance.

______________________________________________________________________

## Functions Called

Call stack for `process_withdrawals`. Sources: gloas functions are defined in
[gloas/beacon-chain.md](../../../../../../../specs/gloas/beacon-chain.md);
inherited functions are from earlier forks (capella, electra, phase0).

- `process_withdrawals(state)` — gloas
  - `is_parent_block_full(state)` — gloas
  - `get_expected_withdrawals(state)` — gloas
    - `get_builder_withdrawals(state, ...)` — gloas
      - `convert_builder_index_to_validator_index(index)` — gloas
    - `get_pending_partial_withdrawals(state, ...)` — electra
    - `get_builders_sweep_withdrawals(state, ...)` — gloas
      - `get_current_epoch(state)` — phase0
      - `convert_builder_index_to_validator_index(index)` — gloas
    - `get_validators_sweep_withdrawals(state, ...)` — electra
  - `apply_withdrawals(state, withdrawals)` — gloas
    - `is_builder_index(validator_index)` — gloas
    - `convert_validator_index_to_builder_index(index)` — gloas
    - `decrease_balance(state, index, amount)` — phase0
  - `update_next_withdrawal_index(state, withdrawals)` — capella
  - `update_payload_expected_withdrawals(state, withdrawals)` — gloas
  - `update_builder_pending_withdrawals(state, count)` — gloas
  - `update_pending_partial_withdrawals(state, count)` — electra
  - `update_next_withdrawal_builder_index(state, count)` — gloas
  - `update_next_withdrawal_validator_index(state, withdrawals)` — capella

______________________________________________________________________

## Summary Diagram

```text
                    +-----------------------------------------------------------+
                    |                    INPUT (Read)                           |
                    +-----------------------------------------------------------+
                    | latest_execution_payload_bid.block_hash : Bytes32         |
                    | latest_block_hash                       : Bytes32         |
                    | slot                                    : uint64          |
                    | next_withdrawal_index                   : uint64          |
                    | next_withdrawal_validator_index         : uint64          |
                    | next_withdrawal_builder_index           : uint64          |
                    | builders[0..2^40]                       : Container[]     |
                    |   .balance, .execution_address, .withdrawable_epoch       |
                    | builder_pending_withdrawals[0..2^20]    : Container[]     |
                    |   .builder_index, .fee_recipient, .amount                 |
                    | pending_partial_withdrawals[0..2^27]    : Container[]     |
                    |   .withdrawable_epoch, .validator_index, .amount          |
                    | balances[0..2^40]                       : uint64[]        |
                    | validators[0..2^40]                     : Container[]     |
                    |   .effective_balance, .exit_epoch, .withdrawable_epoch,   |
                    |   .withdrawal_credentials                                 |
                    +---------------------------+-------------------------------+
                                                |
                                                v
                    +-----------------------------------------------------------+
                    |                process_withdrawals()                      |
                    |                                                           |
                    | 1. Builder pending withdrawals (from fee_recipient)       |
                    | 2. Partial validator withdrawals                          |
                    | 3. Builder sweep withdrawals (from execution_address)     |
                    | 4. Validator sweep withdrawals                            |
                    +---------------------------+-------------------------------+
                                                |
                                                v
                    +-----------------------------------------------------------+
                    |                   OUTPUT (Modified)                       |
                    +-----------------------------------------------------------+
                    | payload_expected_withdrawals[0..16]     : Container[]     |
                    |   .index, .validator_index, .address, .amount             |
                    | builders[*].balance                     : uint64          |
                    | balances[*]                             : uint64          |
                    | builder_pending_withdrawals             : Container[]     |
                    | pending_partial_withdrawals             : Container[]     |
                    | next_withdrawal_index                   : uint64          |
                    | next_withdrawal_builder_index           : uint64          |
                    | next_withdrawal_validator_index         : uint64          |
                    +-----------------------------------------------------------+
```
