---
name: run-tests
description: >-
  Run tests and generate reference tests. Use when the user asks to run tests,
  verify changes, check a fix, or regenerate reference tests.
compatibility: Requires make and uv
---

# Running tests

All testing is done with `make test`. Do not use `pytest` directly. When
possible, testing should be targeted to areas affected by the change rather than
running the full suite. When fixing issues, the targeted set should be run once
to collect failures, then individual failing tests should be re-run to verify
fixes rather than re-running the whole filtered set after each edit.

## Filter by name

Tests can be filtered by name via the `k=<string>` flag. This value is passed
directly to pytest with `-k` and therefore supports its features, such as
boolean operators (`and`, `or`, `not`). For example,
`make test k="gossip and valid"` is valid.

## Filter by fork

Tests can be limited to a single fork via the `fork=<fork>` flag. It is not
currently possible to specify multiple forks with the flag. The available forks
are the names of all directories in `./specs/` (except for `_features`) and all
directories in `./specs/_features/`.

## Filter by preset

Tests can be run against a preset via the `preset=<preset>` flag. There are
three presets: general, minimal, and mainnet. By default, `make test` only runs
minimal tests. The general tests cover things like BLS, KZG, and SSZ tests. The
minimal tests are fast to execute but do not cover the full range of possible
situations. The mainnet tests are very slow and should only be run in targeted
commands. Note that there are some tests which are only executed under a single
preset.

## Filter by component

Tests can be scoped to a component via the `component=<comp>` flag. Three values
are accepted: `all` (the default), `pyspec`, and `fw` (short for framework). The
`pyspec` value runs only the spec tests under `./tests/core/pyspec`, while `fw`
runs only the tests under `./tests/infra`. Some flags (`fork`, `preset`, etc)
are ignored with `component=fw` since those tests do not depend on the spec.

## Generate reference tests

Reference tests can be generated for clients to ensure compliance with the
specifications. Enable reference tests outputs with the `reftests=true` flag.
These are written to `./reftests` at the project root; this directory is
automatically created. Unlike `make test`, `reftests=true` runs all presets
(general, minimal, mainnet) by default; this can be overridden by using the
`preset=<preset>` flag. The framework deletes individual test case directories
before regenerating them, so targeted reruns will update existing reference
tests. If a test case function was deleted, `make test reftests=true` will not
delete its previously generated reference test.

## Track code coverage

Code coverage tracking can be enabled with the `coverage=true` flag. The results
are available as HTML for humans at `./tests/core/pyspec/.htmlcov/index.html`
and as JSON for robots at `./tests/core/pyspec/.htmlcov/coverage.json`.
