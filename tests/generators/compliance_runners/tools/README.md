# Shared compliance runner tools

These tools may be imported by generators and compliance runners. They do not
depend on either runner infrastructure or the coverage capture DSL.

`coverage_model.py` contains typed expression trees used by the
[explicit coverage declarations](../state_transition/evaluation/DECLARATIONS.md).
It evaluates supported expressions without parsing Python source. A separate
adapter connects the model to coverage profiles, observation, and scoring.

## Conditional factors

In addition to single-valued `requires`, `Factor.allowed` accepts conjunctions
of `(parent_name, allowed_values)` conditions. This represents, for example,
activation on either `LT` or `EQ` for a comparison factor. An empty allowed set
disables the child. `Model.project` projects already filtered complete
configurations, retaining recursive prerequisites. Passing `complete=True` to
`nwise` or `exhaustive` selects a complete configuration for each obligation
instead of returning only its projection. Inactive dimensions remain absent.

```python
from pathlib import Path

from tests.generators.compliance_runners.tools.conditional_factors import Factor, Model

model = Model(
    [
        Factor("A", (False, True)),
        Factor("B", (False, True), requires=(("A", True),)),
    ]
)

model.nwise(["B"], 1)  # {A=True, B=False}, {A=True, B=True}
model.nwise(["A"], 1)  # {A=False}, {A=True}
model.nwise(["A"], 1, complete=True)  # {A=False}, {A=True, B=False}
model.exhaustive(["A", "B"])  # {A=False}, plus both active B cases
model.exhaustive(["A", "B"], backend="minizinc", solver="gecode")
Path("conditional.mzn").write_text(model.to_minizinc())
```

`Model.complete(obligations, configurations=None, preference=None, ...)` also
completes existing partial obligations. By default it enumerates configurations
with the requested backend and breaks ties deterministically. A caller can
supply already filtered, complete configurations and a preference key;
completion then stays within that supplied scope without enumerating again. The
declaration adapter uses this path to preserve assertion fault bounds, prefer
consistent acceptance and fewer faults, and retain explicit requested values.
Impossible obligations raise `ValueError` rather than being silently altered or
dropped.

Run the exported model with
`minizinc --solver gecode --all-solutions conditional.mzn` or open it in the
MiniZinc IDE. Comments map integer encodings to factor names and values; zero
means inactive. The export enumerates full valid configurations. Python projects
them onto the requested interactions and adds prerequisites. Both backends share
that projection, so tests also assert explicit expected obligations rather than
relying only on backend agreement.

Strength counts selected active factors, excluding added prerequisites. If a
branch has fewer active selected factors than the requested strength, all of
them are included. If none are active, that branch contributes no obligation.
This preserves shorter branches during exhaustive enumeration without creating
an empty obligation for a request selecting only an inactive factor.

Activation conditions are conjunctions of factor/value pairs, recursively closed
over an acyclic dependency graph. Arbitrary Python predicates and disjunctive
activation are not supported. `forbidden` is an iterable of frozensets of
factor/value pairs that cannot hold simultaneously; an empty forbidden
combination makes the model unsatisfiable. A partial obligation is emitted only
when it has a valid complete extension. Inactive factors are absent, not
assigned an ordinary domain value or treated as missing observations.

This first implementation enumerates the entire finite configuration space and
deduplicates projected obligations. It is intended for small models and semantic
verification, not large-scale generation. MiniZinc is imported only when that
backend is requested. Solver failures or incomplete enumeration are errors,
never silently treated as empty coverage.

The state-transition declaration adapter maps finite dimensions and their
coverage activation conditions to this model. Bound targets can opt in with
`TARGET.for_spec(spec, backend="minizinc")`. Raw observation expressions are not
translated. The declaration adapter additionally compiles abstract feasibility,
assertion consistency, fault scopes, and coverage plans into two MiniZinc
stages. Legacy Python feasibility callbacks supply explicit finite compatibility
tables. See
[the declaration documentation](../state_transition/evaluation/DECLARATIONS.md#optional-minizinc-enumeration).
