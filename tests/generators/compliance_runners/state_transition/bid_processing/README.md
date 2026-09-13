# `process_execution_payload_bid` compliance tests (bid_processing aspect model)

Aspect-based coverage generation for the `gloas` `process_execution_payload_bid`
handler, following [`../TEST_METHODOLOGY.md`](../TEST_METHODOLOGY.md). Uses the
aggregate `bid_processing` aspect model (aspects/bid_processing/) rather than
the flat-aspect sibling in
[`../execution_payload_bid/`](../execution_payload_bid/).

## Pipeline

```
aspects/bid_processing/*.mzn   aggregate realization aspect: builder record +
        │                      bid-processing dimensions, coherence, explicit NA,
        │                      no_more_than_several_of fault bound
        ▼
models/handler_bid_processing.mzn  flat dimension vars + handler-local dimensions,
        │                      derives outcome / faults / effects / trace
        ▼
models/coverage_smoke.mzn      coverage scope (n_faults <= 1)
        │
        ▼
materializer.py                solve, realize each solution into pre /
        │                      SignedExecutionPayloadBid / post + dimensions.yaml
        ▼
validation.py                  independently recover every dimension via spec predicates,
                                recompute the outcome, run the handler as an oracle
```

## Coverage: combinatorial over aspects

Coverage is **t-wise over a configurable set of aspects**, with `outcome`
treated as just another aspect (`coverage.py`). MiniZinc enumerates the feasible
space once; Python computes the t-wise obligations and greedily covers them
(preferring fewer faults, so representatives stay clean).

| profile       | request                                               | cases |
| ------------- | ----------------------------------------------------- | ----- |
| `onewise`     | 1-wise over all aspects (incl. `outcome`)             | 34    |
| `normal`      | 2-wise over input aspects, `outcome == ACCEPT`        | 13    |
| `exceptional` | 2-wise over `builder_type × outcome`, rejections only | 16    |
| `standard`    | `normal ∪ exceptional`                                | 29    |
| `pairwise`    | 2-wise over all aspects                               | —     |

## Usage

```bash
# smoke profile: generate + validate
uv run python -m tests.generators.compliance_runners.state_transition.bid_processing.run

# combinatorial-over-aspects coverage: profile summary, or materialize one
uv run python -m ...bid_processing.coverage                       # summary
uv run python -m ...bid_processing.coverage standard --materialize  # or: onewise|normal|exceptional|pairwise
```

## Output

Standard [operations format](../../../../formats/operations/README.md) under
`reftests/minimal/gloas/operations/execution_payload_bid/main/case_XXXX/`: `pre`
/ `execution_payload_bid` / `post` (omitted on rejection) `.ssz_snappy`,
`meta.yaml`, `manifest.yaml`, and `dimensions.yaml` (the serialized solution).

## Notes

- **Real BLS.** Signatures are signed with the deterministic builder keys —
  valid, wrong-key (invalid), and `G2_POINT_AT_INFINITY` (self-build).
- **Rejection = no `post`.** This handler `assert`s, so rejected cases omit
  `post`; only `ACCEPT` cases carry it.
- **`state_slot_past_genesis` is always true** (the spec requires
  `state.slot > GENESIS_SLOT`), so `REJECT_NOT_PAST_GENESIS` is never produced.
- **Coherence.** The aspect model links `cmp_balance_min_deposit` to
  `cmp_builder_balance_to_bid_value_plus_min_balance` so the solver does not
  produce physically impossible balance/bid combinations.
