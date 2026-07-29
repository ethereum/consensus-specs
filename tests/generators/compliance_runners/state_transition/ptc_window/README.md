# `process_ptc_window` compliance tests

Epoch-processing vectors for the Gloas PTC cache rotation. They cover genesis
and later epoch boundaries and independently reconstruct the shifted window and
new lookahead tail.

This is an `epoch_processing` sub-transition. Cases contain only `pre` and
`post`, written under
`minimal/gloas/epoch_processing/ptc_window/main/case_XXXX/`. The intentionally
small profiles cover genesis-end and later-epoch-end contexts; the handler is
branchless, so exact retained-section shifting and tail-slot recomputation
provide the meaningful coverage rather than a large case count.

Serialized dimensions cover epoch position, pairwise distinguishability of the
old sections, lookahead-plus-one tail context, retained shift, recomputed tail,
state effect, and the single successful outcome. Validation reconstructs the
tail with `compute_ptc`, checks `get_ptc` lookup behavior, and verifies no
unrelated state changes.

Run and validate the standard profile:

```bash
UV_CACHE_DIR=.uv-cache uv run python -m \
  tests.generators.compliance_runners.state_transition.ptc_window.run
```

Inspect coverage profiles or materialize a specific profile:

```bash
UV_CACHE_DIR=.uv-cache uv run python -m \
  tests.generators.compliance_runners.state_transition.ptc_window.coverage
UV_CACHE_DIR=.uv-cache uv run python -m \
  tests.generators.compliance_runners.state_transition.ptc_window.coverage \
  standard --materialize
```
