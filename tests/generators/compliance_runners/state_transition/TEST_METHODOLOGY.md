# Test modelling methodology

This document describes a methodology for generating compliance tests by
modelling semantic situations, materializing them into concrete test vectors,
and validating that each vector realizes its model solution. It is general — the
same structure applies to state-transition, fork-choice, and execution-spec
tests. The running example is the `process_execution_payload_bid` handler on the
`gloas` `BeaconState` (the exploratory model in [`old/models/`](old/models)
illustrates its solution space). It and [`builder_exit_request/`](builder_exit_request)
are worked aspect-based instances that **share** realization aspects from a
common [`aspects/`](aspects) directory; earlier single-model *smoke-profile*
versions are archived under [`old2/`](old2).

Central design principle:

> **Realization aspects** define reusable relations between coverage and
> materialization dimensions. **Handler aspects** bind those relations to a
> specific handler's state and operation. **Coverage aspects** select which
> projections and combinations become tests.

Separating *what a situation means and how to build it* from *which situations
become tests* lets handlers share semantic models, and lets one model support
different coverage strengths without rewriting domain constraints.

## Relational view

Model the system under test as a relation:

```text
DomainRelation ⊆ Input × Output × Outcome × Trace
```

- `Input` — the precondition plus the operation or event.
- `Output` — the resulting state or observable effect.
- `Outcome` — the terminal behavior (accept, reject, no-op, …).
- `Trace` — which semantic checks were reached.

For a state transition, `Input` is a `PreState` plus an optional operation and
`Output` is a `PostState`. Sequences of operations fit the same shape.

Predicate coverage is the minimum bar; combinations of predicates, boundary
relations, outcomes, effects, and traces expose more bugs. Source and branch
coverage are diagnostic feedback, not the coverage model itself.

## Dimensions

### Coverage dimensions

A **coverage dimension** is an atomic semantic projection used in a coverage
formula. Input-side coverage dimensions usually correspond to predicates or
comparisons extracted from the specification (`builder_found`, `builder_active`,
`bid_parent_hash_matches`, …).

- Boolean predicates should be exercised both true and false wherever they are
  applicable.
- Comparisons should keep their boundary structure rather than collapsing
  immediately to a boolean. Model the comparison as `{LT, EQ, GT}` and derive
  the boolean by choosing which outcomes count as true:

  ```text
  available_balance_to_bid_amount ∈ {LT, EQ, GT}
  can_builder_cover_bid := available_balance_to_bid_amount ∈ {EQ, GT}
  ```

  Mirror the specification's *exact* boundary — including any offsets and guards
  (for `can_builder_cover_bid`, the pending-withdrawal term and the
  minimum-balance guard) — rather than a simplified approximation.

Coverage dimensions may also be **derived** from output, outcome, or trace: the
handler outcome, whether a check was reached, whether a state field changed.
Derived dimensions relate to inputs by constraints, so a coverage formula can
select a target outcome or effect and the solver solves back to an input that
produces it.

### Materialization dimensions

A **materialization dimension** is a concrete or symbolic value needed to build
the vector (builder balance, bid value, referenced index, queue length, slot,
signing key). The division of labor is:

- the **solver** assigns coverage dimensions and *symbolic* comparison outcomes;
- the **materializer** chooses concrete operands that realize them.

The solver assignment is authoritative: the materializer must not substitute a
different, easier-to-construct value for a requested comparison or predicate.
Concrete protocol values are often too large for a finite-domain solver — prefer
a `{LT, EQ, GT}` comparison dimension and let the materializer pick operands.

Materialization dimensions need not appear in coverage formulas. Auxiliary
encoding variables are neither coverage obligations nor part of the materializer
contract unless explicitly exported.

## Aspects

An **aspect** is a reusable relation over dimensions, defined around semantic
functionality rather than the handler that first needs it (entity reference and
membership, builder/validator lifecycle, funds, withdrawal credentials and
authorization, queue capacity, slot/epoch relations, signed messages, …). Three
complementary layers:

### Realization aspects

A **realization aspect** connects coverage dimensions to materialization
dimensions and excludes incoherent assignments. It states what an assignment
means and how to realize it — not which assignments become tests. Each coverage
dimension it defines must carry:

- a stable name and a finite domain;
- a semantic description and a specification reference;
- an applicability condition, if any;
- materialization dimensions or rules sufficient to realize it;
- an independent procedure for recovering it from a serialized vector.

A dimension that must appear in solutions has to be a genuine solver output, not
an artifact the flattener can eliminate. In MiniZinc, *declare and constrain* it
(`var T: d; constraint d <-> …;`) rather than *define* it (`var T: d = …;`):
defined variables may be inlined away and then be absent from the solution — and
so from the materialized coverage fingerprint. Derived coverage dimensions
(outcome, effects, "check reached") in particular must be declared-and-constrained.

### Handler aspects

A **handler aspect** assembles shared realization aspects, binds their abstract
roles to concrete state and operation fields, and adds genuinely
handler-specific dimensions. For `process_execution_payload_bid` it might bind an
entity-reference aspect to `bid.builder_index` / `state.builders`, a
builder-lifecycle and a funds aspect to the referenced builder, and a
signed-message aspect to the bid — plus local dimensions for self-build, KZG
count, slot, and parent fields. It also states inter-aspect applicability
(lifecycle and funds apply only to an external bid whose reference resolves).

The same shared aspect bound by several handlers makes overlap explicit.
Realization aspects live in a common directory and are `include`d by each
handler model; a handler only binds their applicability to its own fields. For
example, `execution_payload_bid` and `builder_exit_request` include the *same*
`builder_lifecycle` (`is_active_builder`) and `builder_pending_balance`
(`get_pending_balance_to_withdraw_for_builder`) aspect files, binding
applicability to `builder_ref == EXISTING` and to `builder_pubkey_found`
respectively. Improving one domain model or recovery procedure then benefits
every handler that uses it.

### Coverage aspects

A **coverage aspect** expresses a coverage criterion over the exposed
dimensions; it selects, it does not materialize. It can be input-side or derived
from output, outcome, or trace:

```text
exhaustive(builder_active, builder_version_valid, available_balance_to_bid_amount)
cover_each(handler_outcome)
pairwise(handler_outcome, pending_payment_written)
```

Operators: `cover_each` (every applicable value of a dimension), `exhaustive`
(full cross product of the listed dimensions), `pairwise` / `three_way` (all 2-
or 3-tuples across dimensions), and single- vs multi-fault selection (for
diagnosis vs adversarial coverage).

## Applicability, reachability, and decisiveness

Guarded conditions need three distinct concepts; conflating them corrupts
coverage.

**Applicability.** A dimension is *applicable* when its value can be recovered
from the input vector. If a builder reference does not resolve, predicates over
that builder's lifecycle, funds, or key are not applicable. Represent it
explicitly:

```text
builder_active_applicable := external_bid and builder_found
```

When the guard is false the coverage value is `NA`; it must not be forced to an
arbitrary true or false merely to satisfy the solver.

**Reachability.** A predicate is *reached* when execution evaluates its check;
this depends on gate order. A predicate can be applicable but not reached: an
existing builder may simultaneously be inactive, mis-versioned, underfunded, and
badly signed — all recoverable from the vector even though execution stops at
the activity check. Later applicable dimensions must **not** be set to `NA`
merely because an earlier gate rejected the operation; a trace dimension records
which checks were reached.

**Decisiveness.** A predicate is *decisive* when it determines the terminal
outcome. First-failing-gate identifies the decisive predicate but does not erase
the other applicable assignments.

Keeping these separate permits rich multi-predicate enumeration while preserving
accurate short-circuit semantics.

## Coverage formulas and profiles

A coverage formula states which projections and combinations should appear; it
is separate from the constraints that define valid situations. The default
favors richer solutions: enumerate combinations within a small active aspect,
retain `LT`/`EQ`/`GT` boundaries, enumerate applicable predicates even when only
the first failing one is reached, and include successful and exceptional
combinations (and effects present vs absent). Across several large aspects, use
an explicit interaction policy — exhaustive for selected high-risk relations,
pairwise or three-way otherwise, single- and multi-fault cases.

The same handler relation supports multiple profiles:

```text
smoke:      one canonical case per outcome
standard:   exhaustive within aspects; pairwise across aspects
extended:   three-way across aspects; pairwise exceptional predicates
exhaustive: every satisfiable coverage assignment
```

One-case-per-outcome frontiers are useful smoke tests — the reference runners
are smoke-profile — but they are not a substitute for the richer profiles.

Quality is measured by satisfied obligations, not case count: every applicable
value of every dimension, every requested pair or tuple, every outcome, every
check reached and not reached where possible, every selected effect, every
comparison boundary. If satisfying assignments are too numerous, reduce them
with a deterministic set cover that preserves the declared obligations, and
report uncovered or unsatisfiable obligations explicitly. Deduplicate solutions
by a coverage fingerprint over applicable coverage values and `NA` markers — not
over auxiliary or concrete materialization choices.

## Materialization

A materializer converts one immutable solver solution into a concrete vector. It
must:

- consume the solution's coverage and materialization dimensions;
- choose concrete operands for symbolic comparison dimensions;
- construct all input objects, preserving **every** applicable coverage
  assignment;
- serialize the original solution alongside the vector;
- emit the expected outcome and effects when the test format requires them.

The materializer must **not** re-derive a new set of claims from the object it
constructed — doing so can hide a failure to realize the solver assignment. It
may use the executable specification to build auxiliary state or a candidate
post-state, but that execution must not overwrite the authoritative solution.

A per-case artifact retains at least the solution:

```yaml
solution:
  builder_found: true
  builder_active: false
  available_balance_to_bid_amount: LT
  outcome: REJECT_EXTERNAL_INACTIVE
```

## Validation

Validation has several independent responsibilities.

**Materialization correctness.** Decode the vector and independently recover
every applicable coverage dimension via its aspect's recovery procedure, then
compare to the solver assignment. A divergence is a generator failure even if
the handler produces the expected outcome.

```text
selected assignment → concrete vector → independently recovered assignment
```

Also check that every declared dimension is present, that `NA` agrees with its
applicability guard, that no undeclared dimensions appear, and that
materialization dimensions satisfy their declared constraints.

**Outcome, trace, and effect correctness.** Recover or observe the derived
dimensions and compare them to their model assignments — expected vs observed
outcome, reached checks, and state changes. For a rejected operation, confirm no
forbidden mutation occurred and that `post` is omitted where the format requires
it; distinguish this from a no-op whose `post` is present but unchanged.

**Global coverage audit.** After per-case checks, evaluate the whole suite
against its coverage aspects. The run must fail when a declared value or
requested combination is missing, an outcome/trace/effect obligation is
uncovered, duplicates displace a required assignment, or a supposedly satisfiable
obligation has no solution. Per-case correctness does not imply suite coverage.

**Implementation and code coverage.** Execute validated vectors against the
implementation and any independent oracles. Source and branch coverage are
diagnostic: gaps feed back into predicate extraction, aspect definitions,
bindings, or coverage formulas — they are not themselves the selection criterion.

## Pipeline

1. **Predicate extraction** — identify predicates, comparisons, and hidden
   boundary relations in the specification; record stable spec anchors.
1. **Aspect modelling** — define reusable realization relations between coverage
   and materialization dimensions.
1. **Handler assembly** — bind shared aspects to a handler's state and operation;
   add handler-local relations.
1. **Coverage selection** — apply input, outcome, trace, and effect coverage
   aspects at the chosen profile.
1. **Solving** — enumerate satisfying coverage assignments.
1. **Materialization** — build vectors without changing their assignments.
1. **Validation** — independently recover dimensions, outcomes, traces, and
   effects and compare them to the solutions.
1. **Coverage audit** — prove the suite satisfies its declared obligations.
1. **Implementation execution** — run the vectors and use code coverage and
   external oracles as feedback.
