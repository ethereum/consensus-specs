# `process_deposit_request` compliance tests (aspect-based)

Aspect-based coverage for the gloas `process_deposit_request` handler.

## Modified in gloas

gloas **removes the Electra start-index logic**: `process_deposit_request`
unconditionally appends a `PendingDeposit` (copied from the request, with
`slot = state.slot`) and touches nothing else — no gates, no branches, no
signature check. So there is a **single outcome** (`APPENDED`); the coverage
dimensions are pure input/output-shape:

| aspect | dims | role |
|---|---|---|
| `deposit_amount` | `amount_nonzero` | copied into the PendingDeposit (shared with builder_deposit_request) |
| `deposit_pubkey` | `pubkey_is_existing_validator` | copied verbatim; no control-flow effect |
| `outcome` | `outcome` (single value `APPENDED`) | — |

## Validation is output-focused

With no predicates to re-derive, `validation.py`'s substantive checks are on the
output: the appended `PendingDeposit` equals `PendingDeposit(pubkey,
withdrawal_credentials, amount, signature, slot=pre.slot)`, the queue grew by
exactly one, **`deposit_requests_start_index` is unchanged** (the gloas
modification), and `post == spec re-execution`.

## Coverage profiles (`coverage.py`)

| profile | cases |
|---|---|
| `onewise` | 2 |
| `pairwise` / `standard` | 4 |

## Usage

```bash
uv run python -m tests.generators.compliance_runners.state_transition.run deposit_request                    # standard + validate
uv run python -m ...deposit_request.coverage               # profile summary
```
