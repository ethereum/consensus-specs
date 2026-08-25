# `process_ptc_window` compliance tests

Epoch-processing vectors for the Gloas PTC cache rotation. They cover genesis
and later epoch boundaries across minimum and larger active validator sets,
independently reconstructing the shifted window and new lookahead tail.

This is an `epoch_processing` sub-transition. Cases contain only `pre` and
`post`, written under
`minimal/gloas/epoch_processing/ptc_window/main/case_XXXX/`. The intentionally
small profiles cover the two epoch contexts and two validator set sizes; the
handler is branchless, so exact retained-section shifting and tail-slot
recomputation provide the meaningful coverage rather than a large case count.

Serialized dimensions cover epoch position and validator-set size. The handler
validator checks only that those claimed dimensions match the materialized
pre-state; the compliance test runner performs the transition correctness
checks.

Run and validate the standard profile:

```bash
UV_CACHE_DIR=.uv-cache uv run python -m \
  tests.generators.compliance_runners.state_transition.run ptc_window
```
