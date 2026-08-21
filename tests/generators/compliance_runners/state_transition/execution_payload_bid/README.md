# `process_execution_payload_bid` compliance tests (aspect-based)

Aspect-based coverage generation for the `gloas` `process_execution_payload_bid`
handler, following [`../TEST_METHODOLOGY.md`](../TEST_METHODOLOGY.md). Unlike the
smoke-profile sibling runners, this one builds the methodology's full three-layer
model: **realization aspects → handler → coverage**.

## Pipeline

```
models/aspects/*.mzn        realization aspects: coverage↔materialization relations,
        │                   coherence, explicit NA applicability, derived predicates
        ▼
models/handler_execution_payload_bid.mzn
        │                   includes aspects, binds applicability to the entity
        │                   reference, derives outcome / faults / effects / trace
        ▼
models/coverage_*.mzn       a coverage scope (smoke: n_faults <= 1)
        │
        ▼
materializer.py             reduce to obligations (Python), realize each solution
        │                   into pre / SignedExecutionPayloadBid / post + dimensions.yaml
        ▼
validation.py               independently recover every dimension via spec predicates,
                            recompute the outcome, run the handler as an oracle
```

## Realization aspects

Each is a reusable predicate-library (`models/aspects/`); a `drivers/<name>.mzn`
enumerates its own solution space.

| aspect | coverage dimensions | states | spec | shared with |
|---|---|---|---|---|
| `entity_reference` | `builder_ref {SELF_BUILD,EXISTING,NON_EXISTING}` | 3 | builder_index resolution | exit / deposit |
| `builder_lifecycle` | `deposit_to_finalized_epoch`, `withdrawable_epoch_set` | 7 | `is_active_builder` | `builder_exit_request` |
| `builder_version` | `builder_version_valid` | 3 | version check | — |
| `builder_pending_balance` | `has_pending_withdrawal`, `has_pending_payment` | 5 | `get_pending_balance_to_withdraw_for_builder` | `builder_exit_request` |
| `builder_funds` | `balance_to_min_balance`, `available_to_bid` | 7 | `can_builder_cover_bid` | — |
| `signed_message` | `builder_signature_valid`, `self_build_signature_is_infinity` | 9 | `verify_execution_payload_bid_signature` | deposit (analogous) |
| `blob_kzg_capacity` | `bid_kzg_to_max` | 3 | commitments ≤ max | — |
| `slot_epoch` | `bid_slot_to_state`, `state_slot_past_genesis` | 6 | slot / genesis checks | — |
| `block_context` | `parent_block_hash/root/prev_randao _matches` | 12 | parent linkage | — |

`base.mzn` defines `Dim = {LT,EQ,GT,F,T,NA}` with `CMP`/`CMP_NA`/`BOOLV`/`BOOLV_NA`
subdomains, so any guarded dimension can carry an explicit `NA` (not-applicable),
distinct from an applicable-but-unreached value.

## Coverage: combinatorial over aspects

Coverage is **t-wise over a configurable set of aspects**, with `outcome` treated
as just another aspect (`coverage.py`). MiniZinc enumerates the feasible space
once; Python computes the t-wise obligations and greedily covers them (preferring
fewer faults, so representatives stay clean). This one mechanism subsumes the
earlier ad-hoc scopes:

| profile | request | cases |
|---|---|---|
| `onewise` | 1-wise over all aspects (incl. `outcome`) — each aspect value once | 18 |
| `normal` | 2-wise over the 10 input aspects, `outcome == ACCEPT` | 14 |
| `exceptional` | 2-wise over `entity_reference × outcome`, rejections only | 19 |
| `standard` | `normal ∪ exceptional` (rich on accept, each rejection per branch) | 33 |
| `pairwise` | 2-wise over all aspects | 111 |

`t = 1` over a single aspect is exactly what a `drivers/<aspect>.mzn` shows —
except the driver enumerates the aspect's *intrinsic* space (standalone, before
handler binding), whereas `coverage.py` covers *contextual* states (after the
handler binds applicability). Keep the drivers for aspect-authoring inspection;
use `coverage.py` for suite coverage.

The `coverage_smoke.mzn` scope (`n_faults <= 1`) remains as a simple bounded
model that `run.py` reduces by `cover_each((outcome, self_build))` → 21 cases.
The handler's full feasible space is 83,592 solutions across 14 outcomes.

## Usage

```bash
# smoke profile: generate + validate
uv run python -m tests.generators.compliance_runners.state_transition.run execution_payload_bid

# combinatorial-over-aspects coverage: profile summary, or materialize one
uv run python -m ...execution_payload_bid.coverage                       # summary
uv run python -m ...execution_payload_bid.coverage standard --materialize # or: onewise|normal|exceptional|pairwise

# inspect a single aspect's intrinsic solution space (1-wise, standalone)
uv run minizinc --solver gecode --all-solutions models/drivers/builder_lifecycle.mzn
```

## Output

Standard [operations format](../../../../formats/operations/README.md) under
`reftests/minimal/gloas/operations/execution_payload_bid/main/case_XXXX/`:
`pre` / `execution_payload_bid` / `post` (omitted on rejection) `.ssz_snappy`,
`meta.yaml`, `manifest.yaml`, and `dimensions.yaml` (the serialized solution).

## Notes

- **Real BLS.** Signatures are signed with the deterministic builder keys —
  valid, wrong-key (invalid), and `G2_POINT_AT_INFINITY` (self-build).
- **Rejection = no `post`.** This handler `assert`s, so rejected cases omit
  `post`; only `ACCEPT` cases carry it.
- **`parent_block_root` is `NA` at genesis** (`get_block_root_at_slot(state,
  slot-1)` is undefined at slot 0); the `NOT_PAST_GENESIS` cases reflect this.
- **Coherence in aspects.** `builder_funds` and the handler add constraints so
  the shared `bid.value` operand can't yield incoherent funds/amount combos.
