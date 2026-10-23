# `process_execution_payload_bid` TARGET provider

`target.py` declares coverage for self-build and external-builder bids. It uses
shared MiniZinc/Gecode generation, inherited through
`coverage_profiles(TARGET)`. The former handwritten MiniZinc model, coverage
selector, and validator have been replaced by the shared declaration adapters.

`observation.py` reads numeric balances, epochs, slots, pending amounts, and
commitment counts from the decoded pre-state and signed bid. Comparisons use
`cmp3`, Boolean predicates use native booleans, and builder-only dimensions are
inactive for self-builds. Signature classification enables real BLS verification
and does not trust metadata. Claims are recovered through `target_validator`.

## Coverage and legacy parity

The native model retains all **1,433 legacy signatures** on both minimal and
mainnet after normalizing `F`/`T` to booleans and inactive values to `NA`. The
added `fault_count` dimension independently counts applicable failing gates: 66
signatures have zero faults, 755 have one, and 612 have two.

The legacy fixture's at-most-one-failure constraint counted only `INVALID`
external signatures. An `INF` signature could coexist with one other failed
gate, producing two actual faults. The TARGET preserves this distinction;
exceptional profiles select exactly one independently counted fault.

| Profile     | Coverage                                      | Cases |
| ----------- | --------------------------------------------- | ----: |
| smoke       | One clean representative per terminal outcome |    12 |
| normal      | Grouped pairwise input aspects, zero faults   |    28 |
| exceptional | Each terminal outcome with exactly one fault  |    11 |
| standard    | Normal plus exceptional                       |    39 |
| max         | Every feasible complete signature             | 1,433 |

Normal preserves all 206 original grouped pairwise projections. Its 28 complete
witnesses replace the old greedy selector's 13 representatives; standard changes
from 24 to 39 accordingly. These are coverage-equivalent sets, not identical
representative selections. Smoke stays at one case per reachable outcome.

Generation retains the existing fixture scope: self-builds or existing external
builders, states past genesis, and a block hash distinct from its parent hash.
The materializer guarantees the latter explicitly. Missing builders and genesis
rejections can be observed but are outside the generated space.

The mixed-radix projection encoding is larger than Gecode's integer range, so
MiniZinc enumerates feasible rows and the shared projection evaluator operates
on those rows. It does not enumerate the raw Cartesian space. Regression tests
compare exhaustive legacy fingerprints, fault scopes, legacy profile coverage,
and Python reference projections/completions over the legacy-validated rows.

## Generate and validate

```bash
make comptests kind=state_transition handler=execution_payload_bid profile=smoke seed=124 \
  comptests_dir=/tmp/bid-target-vectors

uv run python -m tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl \
  --target bid_processing --preset minimal --profile smoke --tests /tmp/bid-target-vectors
```

The ordinary provider runner accepts `preset=mainnet` as well. Vectors use the
operations format under
`<preset>/gloas/operations/execution_payload_bid/pyspec_tests/case_XXXX/`, with
real BLS signatures, complete TARGET claims, and a post-state only for accepted
bids.

Tests exercise both preset smoke pipelines, independent recovery and replay, all
standard representatives, every external-builder state, all self-build
signatures, and numeric balance witnesses for every feasible signature.
