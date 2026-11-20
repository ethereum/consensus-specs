# Aggregate `process_withdrawals` TARGET provider

`target.py` declares the aggregate withdrawal sources: pending builder entries,
pending validator partial withdrawals, the builder sweep, and the validator
sweep. Generation inherits the shared MiniZinc/Gecode default through
`coverage_profiles(TARGET)`. The single pending-builder-entry slice remains a
separate provider, `builder_pending_withdrawal_processing`.

Both providers share `materializer.py`, which builds concrete pre/post states
without a solver-backed fixture catalog. Claims and validation use the shared
TARGET adapters. `observation.py` recovers numeric counts and source predicates
from the decoded pre-state and the spec's expected-withdrawal calculation;
comparison dimensions use `cmp3`, and Boolean dimensions use native booleans.

## Legacy parity and profile semantics

The declaration preserves all **873 legacy signatures** on both minimal and
mainnet after normalizing `F`/`T` to booleans: 864 process a revealed parent and
nine exercise the empty-parent no-op. There are no rejecting assertions in this
slice. For compatibility, profile names retain their original interaction
strength rather than partitioning processing and no-op states.

| Profile     | Grouped coverage         | Obligations | Cases |
| ----------- | ------------------------ | ----------: | ----: |
| smoke       | One-wise aspect states   |          44 |    40 |
| exceptional | Same one-wise request    |          44 |    40 |
| normal      | Pairwise aspect states   |         393 |   267 |
| standard    | Same pairwise request    |         393 |   267 |
| max         | Every complete signature |         873 |   873 |

The shared declaration adapter chooses complete witnesses for obligations. The
former greedy selector produced 30 one-wise and 125 pairwise cases. Exact
signatures and coverage obligations are preserved; representative sets differ.
This provider has no terminal-outcome column, so smoke covers aspect states
rather than selecting one case per outcome.

The model retains the legacy fixture restrictions, including a builder count
above the builder withdrawal limit, fewer withdrawn builders than the sweep
window, and the source-priority relationships originally expressed for minimal.
These restrict generated fixtures and are not general protocol rules.

Concrete queue sizes scale with each preset. When pending partials consume their
cap, preceding builder withdrawals leave exactly that much capacity. Partial
entries emit separate positive withdrawals, so processed-entry counts and
prior-output counts agree. Mainnet fixtures use real 16,384-position builder and
validator sweep boundaries, including an eligible validator outside the sweep
window.

## Generate, score, and replay

The normal withdrawals runner generates both providers and distinguishes their
metadata through `test_provider`:

```bash
make comptests kind=state_transition handler=withdrawals profile=smoke preset=minimal \
  seed=124 comptests_dir=/tmp/withdrawal-target-vectors

uv run python -m tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl \
  --target withdrawal_processing --preset minimal --profile smoke \
  --tests /tmp/withdrawal-target-vectors
```

Use `preset=mainnet` and `--preset mainnet` for mainnet. Coverage loading
filters aggregate and single-entry vectors independently. Both slices always
emit a post-state, including an unchanged state for an empty-parent no-op.

Regression tests compare exhaustive legacy fingerprints and every grouped
coverage obligation on both presets. Python reference projection/completion
parity uses the independently legacy-validated feasible rows instead of
allocating millions of raw configurations. Concrete checks cover every minimal
signature, mainnet standard witnesses, shared smoke pipelines, independent
recovery, replay, metadata tampering, and missing post-states.
