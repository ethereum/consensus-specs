# Explicit coverage declarations

The declaration API in `declarations.py` builds expression trees rather than
parsing or executing capture-function source. It currently powers
`eth1_data_reset`, `historical_summaries_update`, `slashings_reset`,
`randao_mixes_reset`, `sync_committee_updates`, `participation_flag_updates`,
`block_header`, `operations`, `voluntary_exit`, `inactivity_updates`,
`inactivity_updates_loop`, `justification_and_finalization`, `registry_updates`,
`rewards_and_penalties`, `proposer_lookahead`, and `process_slot`. These targets
use this API. `coverage_dsl.py` provides observation abstraction, scoring, vector
loading, and the CLI; it no longer provides capture decorators or a second
formula implementation.

## Authoring and review workflow

1. Define the focus, record scope, input attributes, and spec-bound constants.
2. Define derived quantities, factors, activation, aspects, and profiles.
3. Review the specification and its bound obligations.
4. Implement an observation adapter that returns exactly the declared
   attributes.
5. Implement or refine materialization using observed coverage as feedback.

See `../eth1_data_reset/target.py` for the small example and
`../inactivity_updates_loop/target.py` for conditional arithmetic.

The `process_slot` target consumes `sanity/slots` vectors with `slots.yaml: 1`.
Its observation adapter expects that slot count as `Context.operation`. It
records the pre-state inputs to the first slot transition; a multi-slot target
can later cover sequencing and epoch-boundary interactions.

```python
from eth_consensus_specs.test.helpers.specs import spec_targets
from tests.generators.compliance_runners.state_transition.inactivity_updates_loop.target import (
    TARGET,
)

target = TARGET.for_spec(spec_targets["minimal"]["gloas"])
print(target.review("cmp5"))
obligations = target.profiles["arithmetic"].run("cmp5")
```

The existing coverage CLI binds the selected spec automatically. `--describe`
shows the declaration review at predicate granularity. Programmatic `review()`
accepts predicate, cmp3, or cmp5. The review includes domains, bound constants,
derived expressions, activation and availability, profile sizes, pruned counts,
and example obligations with conditional factors included or omitted.

## Expressions and inputs

- `attribute(name, Integer(...))` or `attribute(name, Boolean())` declares a
  per-record input. A missing key is an adapter error; an explicit `NA` value
  means an unavailable observation.
- `Bytes(length=32)` declares opaque roots with validated length. Bytes support
  equality and inequality, not arithmetic or ordering.
- `constant(name, domain)` declares an input bound from a fixed spec. Binding
  validates its domain and snapshots its value. Start from the unbound target
  template for a different spec or configuration.
- `derived(name, expression)` names a reusable expression. It does not add an
  input that the adapter must supply.
- Supported expressions are integer addition, subtraction and remainder;
  comparisons; boolean `&`, `|`, `~`; `maximum`; and `choose`. `choose` and
  boolean operations evaluate only the required branch. Expression types are
  checked at declaration time; concrete domains are checked at binding and
  observation time.
- Python `and`, `or`, `not`, chained comparisons, arbitrary callables, and
  unsupported operators are rejected. There is no implicit source translation.

`factor` declares a boolean factor. `comparison` stores an integer difference
and abstracts it at the requested granularity, using `op` for its predicate
meaning (default `>`). `categorical` declares a finite domain and validates
observed values against it. Attribute, constant, and factor names must be unique
within a specification; aspect grouping does not create namespaces.

## Applicability, activation, and availability

`applicable_when` defines whether the focus exists in a record. Outside that
focus all factors are `NA`. The inactivity body currently requires one eligible
validator; multi-record iteration observation is not implemented.

`when` defines activation in terms of other factors. It supports conjunctions of
boolean factor tests, negations, and categorical equality/inequality. For a
comparison factor, a truth test selects all abstract values where its predicate
holds. Dependencies must be acyclic. Disjunctions and raw-attribute conditions
in `when` are rejected; introduce a meaningful controlling factor instead.

`available_when` describes observation availability (for example, the presence
of a post-state). It can depend on attributes and constants. It suppresses
observation but does not remove coverage obligations. This prevents missing
post-state data from being mistaken for complete coverage.

## Conditional formulas

`each`, `nwise`, and `exhaustive` select factors. Activation prerequisites are
added recursively and do not count toward strength. If fewer selected factors
are active in a branch, all active selected factors are included; if none are
active, that branch contributes no obligation. `fix` also adds prerequisites.
Union (`|`) and product (`*`) compose these formulas.

For B active only when A is true, selecting B alone requires both B values with
A=true. Exhaustive selection of A and B additionally includes A=false. The
inactivity arithmetic profile therefore no longer needs the manual union that
worked around conditional factors in the capture DSL. Its obligations now
explicitly include the applicable `leaking` value when requesting recovery.

Feasibility callbacks remain ordinary Python in this first version, including
callbacks built from bound constants. They filter complete abstract
configurations before projection, so a partial obligation needs a retained
complete extension. This is exact relative to the supplied constraints; it does
not infer every arithmetic relationship from expressions. Unfiltered enumeration
preserves the scorer's unexpected-observation check.

## Current limits

Enumeration explores the complete finite factor model and caches it per bound
target and granularity. It is intended for small focus areas. Expression-to-DL,
UTVPI, or MiniZinc translation and sampling are not implemented. The shared
conditional-factor tool still supports MiniZinc, but its activation-only export
must not be mistaken for a translation of the target's expressions or Python
feasibility constraints.

The assertion-slice targets `block_header` and `operations` declare an `outcome`
aspect from the observed `post_present` attribute. Their normal and exceptional
profiles fix `accepted` to true and false respectively. Their feasibility rule
assumes acceptance exactly when every assertion in the slice holds; failures in
excluded processing are outside this coverage model. Operation-count limits are
spec-bound constants. The header's proposer slashing check uses `available_when`
because a missing validator makes the lookup unavailable without introducing a
new coverage dimension.

`voluntary_exit` declares `additional_epochs` with `when=EXCEEDS`, so churn
exhaustiveness includes both within-budget and exceeding-budget branches. The
`ONE`/`MANY` classification compares the positive excess with one epoch's churn,
which is equivalent to classifying the ceiling division for positive churn.
Validator lookup and signature availability remain observation gates.

The outer `inactivity_updates` target declares the genesis, nonempty-loop, and
slashed-validator prerequisites as factor dependencies. Single-factor coverage
therefore includes their prerequisite assignments. Its `eligible` profile now
covers the full conditional aspect, including interactions between the slashed
boundary and the ineligible-validator flag; the old manual shape/boundary union
covered fewer interactions. Missing post-state only affects observation of
`scores_changed`. Full-configuration feasibility can also prune combinations
whose impossibility was invisible to the legacy partial-assignment filtering.

Observations contain exactly the declared attributes and factor values. Outcome
coverage is explicit: declare a `post_present` attribute and an `accepted`
factor when needed. The runtime does not inject or overwrite these names.
