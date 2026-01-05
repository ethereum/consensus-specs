# Report: `process_withdrawals` Input/Output Space

Note: This is AI generated from the specs, and it is not the authoritative
source of truth.

## Function Signature

```python
def process_withdrawals(state: BeaconState) -> None
```

Location:
[specs/gloas/beacon-chain.md:884-933](../../../../../../../specs/gloas/beacon-chain.md#L884-L933)

______________________________________________________________________

## Input Space (State Fields Read)

| Field                                           | Type                                                                | Value Space                                                                                                                                                                                      | Purpose                                    |
| ----------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------ |
| `state.slot`                                    | `Slot`                                                              | `uint64` ∈ [0, 2⁶⁴-1]. Derives `epoch = slot // SLOTS_PER_EPOCH`. Compared against all `withdrawable_epoch` fields.                                                                              | Compute current epoch                      |
| `state.latest_execution_payload_bid.block_hash` | `Hash32`                                                            | `Bytes32`. **Bound to** `latest_block_hash`: must equal for function to execute (early exit if ≠).                                                                                               | Check if parent block was full             |
| `state.latest_block_hash`                       | `Hash32`                                                            | `Bytes32`. **Bound to** `latest_execution_payload_bid.block_hash` for `is_parent_block_full()` check.                                                                                            | Compare with committed bid                 |
| `state.next_withdrawal_index`                   | `WithdrawalIndex`                                                   | `uint64` ∈ [0, 2⁶⁴-1]. Monotonically increasing. Assigned to each withdrawal created.                                                                                                            | Starting withdrawal index                  |
| `state.next_withdrawal_validator_index`         | `ValidatorIndex`                                                    | `uint64` ∈ \[0, `len(validators)`-1\]. **Bound to** `len(validators)`: wraps via modulo.                                                                                                         | Starting validator sweep position          |
| `state.builder_pending_withdrawals`             | `List[BuilderPendingWithdrawal, BUILDER_PENDING_WITHDRAWALS_LIMIT]` | Length ∈ [0, 2²⁰]. Processed first. Max `MAX_WITHDRAWALS_PER_PAYLOAD - 1` can produce withdrawals.                                                                                               | Iterate and filter for builder withdrawals |
| ↳ `.withdrawable_epoch`                         | `Epoch`                                                             | `uint64`. **Bound to** `state.slot`: withdrawal ready when `<= current_epoch`. If `>`, breaks processing loop.                                                                                   | Check if withdrawal is ready               |
| ↳ `.builder_index`                              | `ValidatorIndex`                                                    | `uint64` ∈ \[0, `len(validators)`-1\]. **Index into** `validators[]` and `balances[]`. Must reference validator with `0x03` prefix.                                                              | Identify builder validator                 |
| ↳ `.fee_recipient`                              | `ExecutionAddress`                                                  | `Bytes20`. Withdrawal destination. Independent of builder's own `withdrawal_credentials[12:]`.                                                                                                   | Withdrawal destination                     |
| ↳ `.amount`                                     | `Gwei`                                                              | `uint64`. Requested amount. Actual = `min(amount, available_balance)` where available depends on slashed status.                                                                                 | Withdrawal amount                          |
| `state.pending_partial_withdrawals`             | `List[PendingPartialWithdrawal, PENDING_PARTIAL_WITHDRAWALS_LIMIT]` | Length ∈ [0, 2²⁷]. Processed second. Max `MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP` (8) processed per block.                                                                                   | Iterate for partial withdrawals            |
| ↳ `.withdrawable_epoch`                         | `Epoch`                                                             | `uint64`. **Bound to** `state.slot`: ready when `<= current_epoch`. If `>`, breaks processing loop.                                                                                              | Check if withdrawal is ready               |
| ↳ `.validator_index`                            | `ValidatorIndex`                                                    | `uint64` ∈ \[0, `len(validators)`-1\]. **Index into** `validators[]` and `balances[]`.                                                                                                           | Identify validator                         |
| ↳ `.amount`                                     | `Gwei`                                                              | `uint64`. Requested amount. Actual = `min(balance - MIN_ACTIVATION_BALANCE, amount)`.                                                                                                            | Withdrawal amount                          |
| `state.balances[*]`                             | `Gwei`                                                              | `uint64` ∈ [0, 2⁶⁴-1]. **Same length as** `validators[]`. Must have excess over `MIN_ACTIVATION_BALANCE` (32 ETH) for non-slashed withdrawals.                                                   | Check available balance                    |
| `state.validators`                              | `List[Validator, VALIDATOR_REGISTRY_LIMIT]`                         | Length ∈ [0, 2⁴⁰]. **Same length as** `balances[]`. All index references must be < len.                                                                                                          | Validator data                             |
| ↳ `[*].slashed`                                 | `boolean`                                                           | `{True, False}`. **Affects** builder withdrawal: if `True`, payment requires `current_epoch >= withdrawable_epoch`; can withdraw full balance. If `False`, must retain `MIN_ACTIVATION_BALANCE`. | Affects withdrawal logic                   |
| ↳ `[*].withdrawable_epoch`                      | `Epoch`                                                             | `uint64`. **Bound to** `state.slot` for: (1) slashed builder payment eligibility, (2) full withdrawal eligibility. Typically `FAR_FUTURE_EPOCH` if not exiting.                                  | For slashed builder check                  |
| ↳ `[*].effective_balance`                       | `Gwei`                                                              | `uint64` ∈ [0, 2048 ETH]. **Constraint**: partial withdrawals require `>= MIN_ACTIVATION_BALANCE` (32 ETH).                                                                                      | Check sufficient balance                   |
| ↳ `[*].exit_epoch`                              | `Epoch`                                                             | `uint64`. **Constraint**: partial withdrawals require `== FAR_FUTURE_EPOCH`. If set, validator is exiting and ineligible.                                                                        | Check if validator exiting                 |
| ↳ `[*].withdrawal_credentials`                  | `Bytes32`                                                           | `Bytes32`. **Prefix byte**: `0x01`=ETH1, `0x02`=compounding, `0x03`=builder. **Bytes [12:32]** = execution address. Validators need `0x01`/`0x02`/`0x03` prefix for withdrawal eligibility.      | Extract withdrawal address (bytes [12:32]) |

______________________________________________________________________

## Output Space (State Fields Modified)

| Field                                   | Type                                                                | Value Space                                                                                                                                                                                                                                       | Modification                                        |
| --------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| `state.payload_expected_withdrawals`    | `List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD]`                     | Length ∈ \[0, `MAX_WITHDRAWALS_PER_PAYLOAD`\]. **Derived from** input `next_withdrawal_index` (sequential), pending lists, and validator sweep. Each `Withdrawal.amount` **bounded by** corresponding `balances[]` entry.                         | **Set** to computed withdrawals list                |
| `state.balances[*]`                     | `Gwei`                                                              | `uint64`. **Decreased by** `payload_expected_withdrawals[*].amount` for each withdrawal's `validator_index`. New value = old value - withdrawal amount.                                                                                           | **Decreased** by withdrawal amounts                 |
| `state.builder_pending_withdrawals`     | `List[BuilderPendingWithdrawal, BUILDER_PENDING_WITHDRAWALS_LIMIT]` | New length ≤ old length. **Bound to** input list: retains items where `is_builder_payment_withdrawable()` returned `False` from first N processed, plus all unprocessed items.                                                                    | **Filtered** - removes processed withdrawable items |
| `state.pending_partial_withdrawals`     | `List[PendingPartialWithdrawal, PENDING_PARTIAL_WITHDRAWALS_LIMIT]` | New length = old length - `processed_partial_withdrawals_count`. **Bound to** input list: simple slice `[processed_count:]`.                                                                                                                      | **Sliced** - removes first N processed items        |
| `state.next_withdrawal_index`           | `WithdrawalIndex`                                                   | New value = `payload_expected_withdrawals[-1].index + 1` if any withdrawals, else unchanged. **Bound to** `len(payload_expected_withdrawals)`.                                                                                                    | **Incremented** by number of withdrawals            |
| `state.next_withdrawal_validator_index` | `ValidatorIndex`                                                    | **Bound to** `len(validators)` (wraps via modulo). If `len(withdrawals) == MAX_WITHDRAWALS_PER_PAYLOAD`: `(last_withdrawal.validator_index + 1) % len(validators)`. Else: `(old_value + MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP) % len(validators)`. | **Updated** based on sweep progress                 |

______________________________________________________________________

## Early Exit Condition

If `is_parent_block_full(state)` returns `False` (i.e.,
`latest_execution_payload_bid.block_hash ≠ latest_block_hash`), the function
returns immediately with **no state modifications**.

______________________________________________________________________

## Key Constants

| Constant                                     | Value                | Description                           |
| -------------------------------------------- | -------------------- | ------------------------------------- |
| `MAX_WITHDRAWALS_PER_PAYLOAD`                | 16                   | Max withdrawals per execution payload |
| `MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP`       | 16,384               | Max validators checked per sweep      |
| `MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP` | 8                    | Max partial withdrawals processed     |
| `VALIDATOR_REGISTRY_LIMIT`                   | 2⁴⁰ (≈1.1 trillion)  | Max validators in registry            |
| `BUILDER_PENDING_WITHDRAWALS_LIMIT`          | 2²⁰ (1,048,576)      | Max pending builder withdrawals       |
| `PENDING_PARTIAL_WITHDRAWALS_LIMIT`          | 2²⁷ (134,217,728)    | Max pending partial withdrawals       |
| `MIN_ACTIVATION_BALANCE`                     | 32 ETH (32×10⁹ Gwei) | Minimum balance for active validator  |
| `FAR_FUTURE_EPOCH`                           | 2⁶⁴-1                | Sentinel for "not set" epoch          |

______________________________________________________________________

## Key Cross-Field Constraints

1. **Index Alignment**: `len(validators) == len(balances)` always. All validator
   indices (`builder_index`, `validator_index`,
   `next_withdrawal_validator_index`) must be `< len(validators)`.

2. **Epoch Gating**: All `withdrawable_epoch` fields are compared against
   `current_epoch = compute_epoch_at_slot(state.slot)`.

3. **Balance Thresholds by Withdrawal Type**:

   - **Builder (non-slashed)**:
     `withdrawable_balance = min(balance - MIN_ACTIVATION_BALANCE, amount)` only
     if `balance > MIN_ACTIVATION_BALANCE`
   - **Builder (slashed)**: `withdrawable_balance = min(balance, amount)` (can
     withdraw full balance)
   - **Partial**: requires `effective_balance >= MIN_ACTIVATION_BALANCE` AND
     `balance > MIN_ACTIVATION_BALANCE` AND `exit_epoch == FAR_FUTURE_EPOCH`
   - **Full**: requires `has_execution_withdrawal_credential` AND
     `withdrawable_epoch <= epoch` AND `balance > 0`

4. **Processing Order & Caps** (combined constraint on output):

   - Builder withdrawals: processed first, up to
     `MAX_WITHDRAWALS_PER_PAYLOAD - 1`
   - Partial withdrawals: processed second, capped by
     `MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP`
   - Validator sweep: processed last, capped by
     `MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP`
   - Total output: `MAX_WITHDRAWALS_PER_PAYLOAD`

5. **Early Exit Binding**: Function executes only when
   `latest_execution_payload_bid.block_hash == latest_block_hash`.

______________________________________________________________________

## Functions Called

| Function                                    | Location                                                                              |
| ------------------------------------------- | ------------------------------------------------------------------------------------- |
| `is_parent_block_full(state)`               | [beacon-chain.md:406-407](../../../../../../../specs/gloas/beacon-chain.md#L406-L407) |
| `get_expected_withdrawals(state)`           | [beacon-chain.md:763-871](../../../../../../../specs/gloas/beacon-chain.md#L763-L871) |
| `decrease_balance(state, index, amount)`    | Base spec                                                                             |
| `is_builder_payment_withdrawable(state, w)` | [beacon-chain.md:749-757](../../../../../../../specs/gloas/beacon-chain.md#L749-L757) |

______________________________________________________________________

## Summary Diagram

```
                    ┌───────────────────────────────────────────────────────┐
                    │                    INPUT (Read)                       │
                    ├───────────────────────────────────────────────────────┤
                    │ latest_execution_payload_bid.block_hash : Bytes32     │
                    │ latest_block_hash                       : Bytes32     │
                    │ slot                                    : uint64      │
                    │ next_withdrawal_index                   : uint64      │
                    │ next_withdrawal_validator_index         : uint64      │
                    │ builder_pending_withdrawals[0..2²⁰]     : Container[] │
                    │ pending_partial_withdrawals[0..2²⁷]     : Container[] │
                    │ balances[0..2⁴⁰]                        : uint64[]    │
                    │ validators[0..2⁴⁰]                      : Container[] │
                    └─────────────────────────┬─────────────────────────────┘
                                              │
                                              ▼
                    ┌───────────────────────────────────────────────────────┐
                    │                process_withdrawals()                  │
                    └─────────────────────────┬─────────────────────────────┘
                                              │
                                              ▼
                    ┌───────────────────────────────────────────────────────┐
                    │                   OUTPUT (Modified)                   │
                    ├───────────────────────────────────────────────────────┤
                    │ payload_expected_withdrawals[0..16]     : Container[] │
                    │ balances[*]                             : uint64      │
                    │ builder_pending_withdrawals             : Container[] │
                    │ pending_partial_withdrawals             : Container[] │
                    │ next_withdrawal_index                   : uint64      │
                    │ next_withdrawal_validator_index         : uint64      │
                    └───────────────────────────────────────────────────────┘
```
