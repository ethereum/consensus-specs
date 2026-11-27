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

The model retains **661 of the 1,433 legacy signatures** on both minimal and
mainnet. Finality cannot be later than a current-epoch deposit, which excludes
580 signatures. Equality uses a slot in genesis epoch with the default
checkpoint. An initiated exit requires finality strictly after the deposit,
which excludes 192 more signatures. Of the retained signatures, 34 have zero
faults, 353 have one, and 274 have two.

The legacy fixture's at-most-one-failure constraint counted only `INVALID`
external signatures. An `INF` signature could coexist with one other failed
gate, producing two actual faults. The TARGET preserves this distinction;
exceptional profiles select exactly one independently counted fault.

| Profile     | Coverage                                      | Cases |
| ----------- | --------------------------------------------- | ----: |
| smoke       | One clean representative per terminal outcome |    12 |
| normal      | Grouped pairwise input aspects, zero faults   |    21 |
| exceptional | Each terminal outcome with exactly one fault  |    11 |
| standard    | Normal plus exceptional                       |    32 |
| max         | Every feasible complete signature             |   661 |

Normal covers all 189 grouped pairwise projections from the retained zero-fault
signatures. Smoke still covers all 12 outcomes.

The materializer reaches finality through signed blocks with attestations.
Exited-builder cases process a genesis builder's exit request from a parent
payload, then advance through skipped slots to the epochs immediately before,
at, and after the preset's withdrawal delay expires. Other external cases choose
a synthetic deposit epoch relative to the checkpoint. Pending payments start at
zero weight, as in bid processing. Builder balances and versions remain targeted
handler inputs. Generation covers self-builds and existing external builders
after slot zero with a block hash distinct from its parent hash.

The mixed-radix projection encoding is larger than Gecode's integer range, so
MiniZinc enumerates feasible rows and the shared projection evaluator operates
on those rows. It does not enumerate the raw Cartesian space. Regression tests
compare fingerprints and fault scopes for the retained legacy rows, grouped
profile coverage, and Python reference projections over the same rows.

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
