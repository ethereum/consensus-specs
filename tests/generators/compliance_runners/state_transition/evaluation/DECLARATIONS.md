# Explicit coverage declarations

The declaration API in `declarations.py` builds expression trees rather than
parsing or executing capture-function source. It currently powers
`eth1_data_reset`, `historical_summaries_update`, `slashings_reset`,
`randao_mixes_reset`, `sync_committee_updates`, `participation_flag_updates`,
`block_header`, `operations`, `voluntary_exit`, `proposer_slashing`,
`inactivity_updates`, `inactivity_updates_loop`,
`justification_and_finalization`, `registry_updates`, `rewards_and_penalties`,
`proposer_lookahead`, `process_slot`, `ptc_window`, and
`pending_consolidations`, `deposit_request`, `slashings`, and `sync_aggregate`.
These targets use this API. `coverage_dsl.py` provides observation abstraction,
scoring, vector loading, and the CLI; it no longer provides capture decorators
or a second formula implementation.

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
print(target.review())
obligations = target.profiles["arithmetic"].run()
```

The existing coverage CLI binds the selected spec automatically. `--describe`
shows the declaration review with each comparison's declared granularity.
Programmatic `review()` uses the same declarations. The review includes domains,
bound constants, derived expressions, activation and availability, profile
sizes, pruned counts, and example obligations with conditional factors included
or omitted.

## Expressions and inputs

`coverage_spec` infers attributes and constants when their lists are omitted. It
traverses aspect values, activation and availability expressions, target
applicability, and constraints. Repeated references to the same declaration are
collected once in first-reference order; distinct declarations with the same
name still raise an error. Constant getters must still be supplied to `bind`.

Explicit `attributes=` and `constants=` lists retain their existing validation
and can include inputs not referenced by the expressions. Keep explicit lists
for constants used only by Python callbacks, such as `constant_feasibility`, or
extra attributes supplied by an observer. Those callbacks are not inspected.

- `attribute(name, Integer(...))` or `attribute(name, Boolean())` declares a
  per-record input. A missing key is an adapter error; an explicit `NA` value
  means an unavailable observation.
- `Bytes(length=32)` declares opaque roots with validated length. Bytes support
  equality and inequality, not arithmetic or ordering.
- Domains expose a scalar `value_type`, which determines legal operations.
  `Finite((value, ...))` declares an exact finite set. Scalar domains of the
  same type compose with `|`, for example
  `Integer(0, 255) | Finite((2**64 - 1,))`. Validation preserves the gap between
  the interval and the sentinel. `domain.contains(expression)` builds a boolean
  expression from bounds, equalities, and disjunctions. Integer interval
  inference still uses a conservative hull; it does not prove reachability
  across domain gaps.
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
- Ordered alternatives can be written as
  `choose((condition1, value1), (condition2, value2), fallback)`. The first true
  condition wins; later conditions and unselected values are skipped.
  Alternating condition/value arguments and the original three-argument form
  still work. Flat choices lower to the same expression trees as nested choices.
- Python `and`, `or`, `not`, chained comparisons, arbitrary callables, and
  unsupported operators are rejected. There is no implicit source translation.

`factor` declares a boolean factor. `comparison` stores an integer difference
and declares its granularity with `granularity="predicate"` (the default),
`"cmp3"`, or `"cmp5"`, using `op` for its predicate meaning (default `>`).
Targets also support the mapping syntax used in the sibling checkout:
`dimension(name, identity(predicate))`,
`dimension(name, cmp3(lhs, rhs, op="<"))`,
`dimension(name, cmp5(lhs, rhs, op="<"))`,
`dimension(name, predicate(lhs, rhs, op="=="))`,
`dimension(name, identity(value, domain=Finite(values)))`,
`dimension(name, count(value))`, and
`dimension(name, modulo_boundary(lhs, period))`. These forms lower to the
existing boolean, comparison, categorical, and modulo declarations, preserving
activation, availability, and coverage domains. `count` uses `ZERO`, `ONE`, and
`MANY`. The optional `op` on `cmp3` and `cmp5` preserves predicate meaning in
constraints and activation without changing their three or five buckets. Mapping
forms accept `when`, `available_when`, and `description` on `dimension`; an
explicit coverage domain belongs on `identity`.

`dimension(name, expression)` covers a small domain exactly. For an attribute or
constant it reuses that input's declared domain. Boolean expressions infer a
boolean coverage domain. `choose` expressions infer the union of their branch
domains, preserving gaps and deduplicating values in branch order; an `identity`
wrapper or explicit `Finite` domain is optional. For example,
`dimension("credential_type", choose(is_compounding, "COMPOUNDING", "STANDARD"))`
covers both labels. Inference obeys the same enumeration limit as explicit
domains. An integer attribute declared with `Integer(0, 4)` therefore needs no
second enumeration of those five values. Boolean domains use the same predicate
abstraction as `factor`; other finite domains use categorical values. An
optional `domain=` supplies the coverage domain for a computed expression. Exact
enumeration is limited to 1024 values by default; use comparison or categorical
abstractions for larger domains. When a dimension depends only on constants,
binding refines its coverage domain to the single resulting value if target
applicability, activation, and availability are known true. Otherwise refinement
is deferred, preserving lazy evaluation of inactive or unavailable values. Fresh
bindings are refined independently. Integer domains also constrain enumeration:
comparison buckets that cannot intersect the expression's inferred interval are
removed. For example, comparing `attribute("vote_count", Integer(min=0))` with
zero at `cmp5` yields only `EQ`, `GT_1`, and `GT_FAR`; `Integer(min=0, max=1)`
yields `EQ` and `GT_1`. Intervals propagate conservatively through addition,
subtraction, `maximum`, `choose`, derived expressions, and positive remainder.
Bound constants refine these intervals per spec. This does not infer
correlations between expressions. Domain pruning also applies to unfiltered
enumeration; feasibility callbacks remain a separate filter.

Granularity is fixed per comparison across all profiles; a target may mix
granularities across different comparisons. `categorical` declares a finite
domain and validates observed values against it. Attribute, constant, and factor
names must be unique within a specification; aspect grouping does not create
namespaces.

```python
boundary = comparison("epoch_boundary", next_epoch, period, op="==", granularity="cmp5")
```

`modulo(name, attribute, positive_constant)` declares a categorical coverage
factor for a remainder, with buckets `ZERO` (0), `ONE` (1), `LAST` (constant−1),
and `INTERIOR` (2 through constant−2). Every remainder is classified. The
modulus must be a positive integer literal or a constant whose declared minimum
is at least one. Periods 1, 2, and 3 omit unreachable buckets: coincident
boundaries use `ZERO` first, then `ONE`. These domains are refined when the spec
is bound. Activation uses explicit categorical tests, such as
`when=position == "ZERO"`.

```python
position = modulo("reset_remainder", next_epoch, period)
nonempty = comparison("votes_nonempty", vote_count, 0, granularity="cmp5")
```

Two comparisons of `next_epoch % period` against 0 and `period - 1` also benefit
from the remainder's implicit non-negative upper bound. Use `modulo` for a
single coverage dimension; the comparison form allows finer distances from each
end but needs explicit feasibility constraints for relationships between the
two.

The ETH1 reset target now uses this modulo factor and a non-negative vote-count
comparison. Normal/standard/max cover 12 combinations for periods of at least
four; smoke covers the seven individual bucket obligations. Regenerate older
vectors, whose boolean factor claims use the previous target schema.

The historical-summary and sync-committee targets use `update_remainder` and
`period_remainder` respectively. Slashings and RANDAO resets observe
`next_epoch` and classify `destination_position` against their spec-bound vector
length. Their adapters still read the source/destination contents at the actual
circular indices. Slot processing uses the four buckets for `ring_position`,
distinguishing index 1 from other interior positions. Effective-balance updates
replace the boolean alignment claim with `balance_remainder`, and concrete
witnesses cover all rounding buckets around hysteresis and cap boundaries.
Regenerate vectors for these six targets: the factor names and/or values have
changed.

`modulo_representative(bucket, period)` in the concretization module chooses a
concrete remainder for a bucket and rejects buckets that do not exist for that
period. Epoch generators map remainder zero to a positive multiple of the
period, so the next epoch remains at least one.

Enumeration uses `target.profiles[name].run()`, observation abstraction uses
`target.record(observation)`, and scoring uses
`score(target, records, formula)`. These functions do not accept a runtime
granularity. Feasibility callbacks take only the assignment; `holds(value)`,
`abstract(raw)`, and `far(value)` use the comparison's declaration. Activation
always uses predicate truth, including for comparisons whose coverage values are
cmp3/cmp5 buckets.

The CLI no longer accepts `--granularity`. JSON reports contain a
`comparison_granularities` mapping and a single `profiles` list, replacing the
old reports grouped by global granularity. Effective-balance comparisons use
cmp5 in every profile, and generated claims no longer carry a global
`granularity` field. Older effective-balance vectors should be regenerated for
the configured factor domains.

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

`constraints=(expression, ...)` declares feasibility over factor references and
spec-bound constants. `aspect.ref(name)` returns a symbolic declaration;
`aspect[name]` retains the observation abstraction used by witness adapters. A
comparison reference denotes its predicate truth at every granularity;
`coverage_value(factor)` explicitly refers to its coverage bucket. `all_of`,
`any_of`, and `implies` compose rules without Python boolean coercion:

```python
constraints = (
    OUTCOME.ref("accepted") == all_of(*HEADER.declarations),
    implies(coverage_value(EXCEEDS) == "GT_1", CHURN.ref("additional_epochs") != "MANY"),
)
```

Inactive references are unknown. A known false constraint rejects a
configuration; an unknown constraint leaves it eligible. Boolean connectives
preserve known violations even when another operand is unknown. `present(f)`
tests inclusion explicitly. This evaluation is conservative for inactive
references, not a solver check for a joint concrete extension. Raw attributes
are rejected in these constraints because enumeration supplies abstract factor
assignments rather than concrete attribute values.

Concrete-witness checks can still use `feasible=` and `constant_feasibility=`.
Declared constraints and callbacks are conjoined by both the specification's and
bound target's `feasible()` methods. They filter complete abstract
configurations before projection, so a partial obligation needs a retained
complete extension. Unfiltered enumeration preserves the scorer's
unexpected-observation check. Review output includes the declared constraints.

## Provider adapters

`state_transition/declaration_coverage.py` provides `coverage_profiles(TARGET)`
for providers that materialize the obligations directly. Its `build_profile`
requires `spec=` and returns a single list of canonical complete cases. Cases
have a stable order based on sorted factor/value pairs. When `TARGET.profiles`
omits `exceptional`, the adapter returns empty records for that profile.
Declared profiles are evaluated normally; other missing names still fail.

Witness generation always delegates selection to
`conditional_factors.Model.complete` over the declaration backend's feasible
configurations for each formula branch. The declaration layer supplies the
acceptance/fault preference; the shared model selects deterministic complete
extensions while respecting inactive dimensions. Every active dimension is
supplied, so materializers do not need to fill missing abstract fields. Block
header retains its concrete joint-slot constructor; abstract completion does not
choose raw slots or construct consensus objects. Effective-balance updates
likewise choose concrete balances in their materializer, using the same witness
table that defines target feasibility.

Cases contain only target dimensions and encode inactive fields as `"NA"` using
the target's activation model. Active values retain their native types and
missing active fields raise errors. The same dimension encoding is available as
`materializer_record(bound_target, assignment)`.

Fault scopes select cases during generation; assertion counts are computed when
materializers build claimed records. Materializers use
`self.claimed_record(TARGET, solution)` to build dimension metadata from the
same activation model. It encodes inactive dimensions as `"NA"`, excludes
concrete inputs and solver metadata, and adds `fault_count` when the target
declares assertions. Claims retain the requested dimension values so validation
can detect mismatches in the constructed state.
`profile_records(bound_target, name)` is also available for custom adapters.
`coverage_profiles(..., backend="minizinc", solver="gecode")` selects native
declaration compilation, as used by payload attestation, voluntary exit, and
proposer slashing. Omitting these options preserves the target's existing
defaults. Scenario and remaining handwritten MiniZinc providers retain their
existing profile implementations.

## Shared validation

`state_transition/declaration_validation.py` provides
`target_validator(TARGET, operation_name="voluntary_exit", operation_type="SignedVoluntaryExit", spec=lambda: spec)`.
It returns generic `recover` and `validate_case` functions. Case validation
decodes pre, operation, and optional post, projects `TARGET.observation()`
through `TARGET.record()`, encodes inactive dimensions as `"NA"`, and compares
claimed fields. The provider runner injects each case's preset explicitly,
including for these closures.

Materializers emit canonical target dimensions using native values and `"NA"`
for inactive dimensions. Validation compares these fields directly, with no
provider-specific metadata mapping. Proposer slashing consumes completed target
assignments. Voluntary exit also generates complete assignments directly from
its target through MiniZinc. Its materializer selects aligned effective balances
and churn budgets from the abstract churn dimensions; generation records carry
no scenario names or concrete numeric hints.

The shared validator also recovers `fault_count` from assertions when claimed.
It checks observed acceptance against known assertion outcomes, respecting
`AssertionSet.complete`: incomplete sets can predict rejection but cannot
require acceptance. Unknown assertions remain unknown, and post-state presence
supplies actual acceptance rather than predicted outcomes. Unknown claimed
fields produce mismatches instead of being silently ignored.

## Current limits

Enumeration explores the complete finite factor model and caches it per bound
target and filtering mode. It is intended for small focus areas.
Expression-to-DL or UTVPI translation and sampling are not implemented. The
optional MiniZinc backend translates finite domains, activation, abstract
feasibility constraints, assertion consistency, fault scopes, and coverage
formulas. Raw observation expressions and Python feasibility callbacks are not
source-translated; callbacks supply explicit finite compatibility tables. The
shared conditional-factor tool's standalone export covers activation only.

Block-header `slot_matches_state` and `slot_is_newer` use `cmp5`. For a valid
pre-state, the latest header slot cannot exceed the state slot. Consequently
`block_slot - latest_header_slot >= block_slot - state_slot`; feasibility
removes bucket pairs that violate this ordering. Both comparisons still cover
all five buckets across their reachable combinations. An accepted header has an
`EQ` state-slot match and a `GT_1` or `GT_FAR` latest-header delta. A duplicate
header can fail the newer-header assertion with an `EQ` delta; older-header
negative deltas also imply a state-slot mismatch, so the first assertion rejects
those vectors.

Materialization completes partial obligations with the fewest failing gates,
preserves requested acceptance, and chooses jointly reachable non-negative
slots. A current-slot latest header retains its zero state-root cache. Blocks
are initially built for the state slot before their slot is varied for the
assertion slice, avoiding full slot transitions during witness construction.
Tests check the first failing assertion, later-gate isolation, and actual
profile coverage. Proposer-index equality retains predicate granularity.
Regenerate block-header vectors for the new slot-bucket claims.

The assertion-slice targets `block_header` and `operations` declare an `outcome`
aspect from the observed `post_present` attribute. Their normal and exceptional
profiles fix `accepted` to true and false respectively. Their feasibility rule
assumes acceptance exactly when every assertion in the slice holds; failures in
excluded processing are outside this coverage model. Operation-count limits are
spec-bound constants. The header's proposer slashing check uses `available_when`
because a missing validator makes the lookup unavailable without introducing a
new coverage dimension.

Voluntary-exit `current_ge_message_epoch` and `current_ge_seasoned` use `cmp5`.
Epoch witnesses realize two epochs before, one before, exactly at, one after,
and two after each boundary. MiniZinc compiles the target's feasibility rules,
assertion fault scopes, and coverage formulas. Normal and exceptional profiles
use the declaration assertion set; pending-loop coverage includes zero, one, and
many matching entries, foreign entries, and actual acceptance. A future
activation is at least `SHARD_COMMITTEE_PERIOD + 1` epochs short of seasoning,
so unactivated validators cannot have only a one-epoch seasoning deficit when
the period is positive. The declared feasibility rule excludes that impossible
combination. Validation recovers the same dimensions from pre, signed exit, and
optional post. Regenerate vectors to obtain the declaration-based profiles.

Voluntary-exit `balance_gt_consumable` uses `cmp5` for the effective balance
against the available exit budget. Effective balances and fresh churn are
aligned to the spec-bound `balance_increment`, so fresh-budget `LT_1` and `GT_1`
buckets are infeasible when the increment exceeds one Gwei. Carried budgets can
be unaligned: partial withdrawal requests consume the same churn budget in
arbitrary Gwei amounts. When foreign pending entries are requested, the
materializer realizes those one-Gwei residuals by processing a foreign partial
withdrawal before the voluntary exit. Otherwise it sets a carried budget
directly, keeping the pending-entry shape independent of the churn dimensions. A
`GT_1` excess always fits in one additional epoch and cannot require `MANY`.

Churn profiles include `earliest_lt_new`, `balance_gt_consumable`, and the
conditional `additional_epochs` (`ONE` or `MANY`). Witnesses cover fresh and
carried budgets, equality, aligned under/overflow boundaries, and multi-epoch
overflow; they recalculate the fresh limit when the selected effective balance
changes total active balance. Larger balances use compounding credentials within
the effective-balance cap. The DSL's conditional `additional_epochs` factor
remains inactive when the exit fits the budget. Regenerate voluntary-exit
vectors to include the new churn claims.

`voluntary_exit` declares `additional_epochs` with `when=EXCEEDS`, so churn
exhaustiveness includes both within-budget and exceeding-budget branches. The
`ONE`/`MANY` classification compares the positive excess with one epoch's churn,
which is equivalent to classifying the ceiling division for positive churn.
Validator lookup and signature availability remain observation gates.

Historical-summary occupancy and the value cleared by slashings reset now use
`cmp5` comparisons against zero. Their non-negative domains leave `EQ`, `GT_1`,
and `GT_FAR`, and concretization realizes empty/zero, singleton/one, and larger
values explicitly.

The inactivity loop declares `cmp5` for `score_gt_zero`, `leaking`, and
`score_vs_recovery_rate`. Recovery remains active only when the leak predicate
is false, including its below-threshold and equality buckets. Feasibility uses
concrete witnesses around zero, the leak threshold, and the
participation-adjusted recovery threshold. These witnesses preserve
relationships between score, participation, recovery saturation, and the
resulting score change. Materialization completes partial obligations with a
feasible full assignment and selects its score/finality-delay witness.
Regenerate existing vectors for these three targets: the numeric factors now
claim comparison buckets rather than booleans.

Proposer lookahead declares `fewer_candidates_than_slots` as a `cmp5` comparison
of the active, unslashed candidate count against `slots_per_epoch`. Its
witnesses use counts slots−2, slots−1, slots, slots+1, and slots+2. Both
negative buckets require `new_proposers_repeat=True`: fewer candidates than
slots cannot supply distinct proposers for every slot. The materializer
preserves the requested pool size while constructing repeated or distinct
proposer lists. For distinct lists it searches balance acceptance thresholds
across slots, using compounding credentials and balances aligned to the spec
increment. This avoids relying on a rare random permutation for an exact-size
mainnet candidate pool. The bounded search retries with deterministic RANDAO
mixes and verifies its result using spec proposer selection. Regenerate older
proposer-lookahead vectors, whose candidate-count claims were booleans.

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

## Assertions, outcomes, and fault-limited profiles

Use `assertion(name, expression, ...)` for predicates that must hold for normal
behavior. It accepts the same boolean expressions, predicate/`cmp5` mappings,
activation (`when`), and observation availability (`available_when`) as
`dimension`. A failed comparison contributes one fault regardless of its
boundary bucket. Ordinary dimensions do not contribute faults.

```python
CHECKS = aspect(
    "checks",
    assertion("slot_matches", cmp5(block_slot, state_slot, op="==")),
    assertion("parent_matches", parent_root_match),
)
OUTCOME = aspect("outcome", dimension("accepted", post_present))
ASSERTIONS = assertion_set(CHECKS, observed=OUTCOME.ref("accepted"), complete=True)
PROFILES = {
    "normal": ASSERTIONS.normal(CHECKS.exhaustive()),
    "exceptional": ASSERTIONS.exceptional(CHECKS.each(), faults=1),
    "multiple": ASSERTIONS.exceptional(CHECKS.nwise(2), faults=(2, 3)),
    "all_faults": ASSERTIONS.exceptional(CHECKS.nwise(2)),
}
# Pass assertions=ASSERTIONS to coverage_spec(...).
```

An assertion set collects assertion declarations from the supplied aspects
(ignoring ordinary dimensions), or accepts individual assertions directly.
`faults(plan, minimum=0, maximum=None)` supplies a general inclusive fault
range. Normal profiles require exactly zero faults; exceptional profiles require
at least one. Scoped plans compose using the existing product and union
operators. Limits apply to complete configurations **before** projection and to
the actual records scored against each branch. A matching projection from a
record outside the branch's fault range earns no coverage. These restrictions
also apply when computing unexpected/infeasible observations.

`target.assertion_result(record)` returns `failed`, `unknown`, `fault_count`,
and `expected_accepted`. The observed `accepted` dimension continues to come
from `post_present`; it is never replaced by the prediction. Inactive assertions
contribute no fault. An applicable but unavailable assertion leaves the exact
fault count unknown (`None`), and cannot satisfy a finite upper fault bound. A
known failure predicts rejection even if another assertion is unknown; otherwise
unknown assertions leave the prediction unknown.

Set `complete=True` only when the assertions fully characterize acceptance in
the target scope. The default `complete=False` allows rejection after all
modeled assertions pass, for example when the operations count-limit slice
passes but subsequent operation processing fails. A known failed assertion still
rules out acceptance. The assertion set supplies this feasibility rule; there is
no need for a manual `accepted == all_of(...)` constraint. Scoring reports
outcome disagreements separately in `Report.outcome_mismatches`, including the
zero-based record index and both outcomes, even when the chosen coverage formula
does not select the outcome dimension. `--records` displays assertion summaries,
and `--describe` displays assertion membership and limits.

Generation adapters should use `generation_obligations()` (as `profile_records`
does), rather than treating scoped `run()` projections as unrestricted witness
requests. It completes all obligations within their permitted configurations, so
a downstream witness cannot add extra faults to a scoped obligation. Coverage
projections from `run()` remain partial. Complete assignment selection also
prefers fewer faults. For incomplete slices, completion prefers agreement with
the predicted outcome when the obligation permits it; this is a generation
preference, not an assumption about all observed executions.

The migrated block-header, operations, and voluntary-exit targets use
single-fault `exceptional` profiles. Their `max` profiles retain unrestricted
exceptional coverage, including combinations where dependencies force multiple
failures.

### BLS-to-execution-change migration

`bls_to_execution_change/target.py` models the five feasible provider cases:
acceptance and rejection at the validator index, credential prefix, pubkey
match, or signature check. Its outcome is derived in assertion order, and the
feasibility table keeps generated dimension claims consistent with the
materialized operation. The provider uses the shared declaration adapters for
profile generation and case validation; its former handler MiniZinc model and
custom validator have been removed.

### Optional MiniZinc enumeration

Existing targets can select the shared conditional-factor MiniZinc backend at
binding time:

```python
target = TARGET.for_spec(spec, backend="minizinc", solver="gecode")
obligations = target.profiles["normal"].run()
witnesses = target.profiles["normal"].generation_obligations()
model = target.definition.model(target.bound_constants)
activation_source = model.to_minizinc()
feasibility_source = target.to_minizinc()
profile_sources = target.profiles["normal"].to_minizinc()
```

The coverage scoring CLI accepts `--backend minizinc` and `--solver gecode`.
Python remains the default; MiniZinc and the selected solver are required only
when that backend enumerates configurations or exports profile models. Bind the
original target template again to change the backend, solver, or spec; bound
targets retain their own caches.

This backend translates finite dimension domains and conditional activation,
encoding inactive dimensions as zero and omitting them from decoded assignments.
Declarative feasibility constraints, assertion/outcome consistency, and profile
fault bounds are compiled into MiniZinc. Inactive references preserve the
declarations' three-valued semantics: a known false constraint rejects a row,
while an unknown constraint does not. Constant-only expressions are folded
before emission, including comparisons of large spec constants.

Coverage uses a second MiniZinc stage over the solved finite configurations.
MiniZinc set comprehensions implement `each`, `nwise`, exhaustive projection,
recursive prerequisites, fixed obligations, unions, and compatible products.
Products merge independently supported leaf obligations, then require a common
complete extension; this preserves short conditional branches. Unions with
different fault restrictions retain separate scoped models. The solver
enumerates the encoded obligations themselves, avoiding duplicate solutions for
unrelated completions. Python decodes the results, chooses deterministic
witnesses, and independently observes and scores vectors.

Legacy `feasible=` and `constant_feasibility=` callbacks are not source
translated. They evaluate the finite rows produced by native feasibility, then
their accepted rows become an explicit MiniZinc compatibility table. Targets
without callbacks do not call Python feasibility or projection functions.
`filtered=False` omits both declarative and callback feasibility while retaining
activation and profile fault scopes, preserving unexpected-observation scoring.

`target.to_minizinc()` exports feasibility. A bound profile's `to_minizinc()`
returns a tuple of dictionaries, each with `feasibility` and `coverage` sources
for one fault scope; the coverage source embeds rows solved from that scope. The
shared conditional model's `to_minizinc()` still exports only activation.

This remains a reference implementation that enumerates complete finite
configurations before projection, not a scalable search over large state spaces.
Mixed-radix obligation encodings and nonconstant numeric expressions must fit
Gecode's signed integer range; oversized models fail explicitly. No concrete
state construction or raw observation expression is translated.

`test_minizinc_backend.py` compares raw and feasible configurations, every
feasible profile, deterministic witnesses, covered obligations, and outcomes for
all registered targets under minimal and mainnet. Unfiltered profile/report
comparisons are restricted to smaller raw spaces. Small explicit cases also
check three-valued constraints, independent product witnesses, unknown fault
counts, missing outcomes, arithmetic, and independently executable exports. The
native-path test fails if Python feasibility, projection, or scope evaluation is
used during MiniZinc obligation generation.

### Proposer-slashing migration

`proposer_slashing/target.py` covers eight assertion predicates: matching slots,
matching proposer indices, distinct headers, the three slashability predicates,
and two signatures. Both signatures use the first header's proposer key, as
specified, even when an earlier assertion would reject. Exit initiation is an
ordinary branch: an exited validator remains slashable until withdrawability.
The payment window, matching payment proposer, and exit-churn variant are also
ordinary dimensions. Churn is active only for accepted slashings that initiate
an exit; payment clearing is observed from the post-state only for accepted
slashings inside the payment window with a populated pre-state payment. Empty
payment entries do not supply clearing-effect coverage. Missing validator data
remains unknown.

The provider uses MiniZinc to translate target feasibility rules, assertion
fault scopes, and coverage formulas. It completes declaration obligations within
each profile's scope and supplies canonical target dimensions directly to the
materializer. Metadata records both the predicted fault count and claimed
acceptance. The observer derives assertion truth from the actual headers,
proposer state, and BLS signatures; acceptance is observed independently from
post-state presence. Case validation checks these observations against metadata
and reports expected/observed acceptance disagreements.

The completed migration comparison established equivalence with the former
MiniZinc handler model across all 1,610 feasible signatures under both presets;
that model has been removed. Regression tests retain the configuration counts
and compare native configurations and complete profile witnesses against the
Python reference backend. A generation guard rejects Python configuration
enumeration to verify the provider actually uses MiniZinc. The `max` profile
retains all 360 signatures with at most two faults (20 normal, 80 with one
fault, 260 with two), which also cover every exceptional pair in the full space.
`normal` retains 20 representatives. `smoke` and `exceptional` now cover
individual declaration dimensions in addition to rejection categories; their
representative counts need not equal the old outcome-only selections. Tests
materialize every `max` witness under both presets and score every profile's
representatives against the resulting observations.
