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
configurations, retaining recursive prerequisites.

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
model.exhaustive(["A", "B"])  # {A=False}, plus both active B cases
model.exhaustive(["A", "B"], backend="minizinc", solver="gecode")
Path("conditional.mzn").write_text(model.to_minizinc())
```

Run the exported model with `minizinc --solver gecode --all-solutions conditional.mzn`
or open it in the MiniZinc IDE. Comments map integer encodings to factor names
and values; zero means inactive. The export enumerates full valid configurations.
Python projects them onto the requested interactions and adds prerequisites.
Both backends share that projection, so tests also assert explicit expected
obligations rather than relying only on backend agreement.

Strength counts selected active factors, excluding added prerequisites. If a
branch has fewer active selected factors than the requested strength, all of
them are included. If none are active, that branch contributes no obligation.
This preserves shorter branches during exhaustive enumeration without creating
an empty obligation for a request selecting only an inactive factor.

Activation conditions are conjunctions of factor/value pairs, recursively
closed over an acyclic dependency graph. Arbitrary Python predicates and
disjunctive activation are not supported. `forbidden` is an iterable of
frozensets of factor/value pairs that cannot hold simultaneously; an empty
forbidden combination makes the model unsatisfiable. A partial obligation is
emitted only when it has a valid complete extension. Inactive factors are
absent, not assigned an ordinary domain value or treated as missing observations.

This first implementation enumerates the entire finite configuration space and
deduplicates projected obligations. It is intended for small models and semantic
verification, not large-scale generation. MiniZinc is imported only when that
backend is requested. Solver failures or incomplete enumeration are errors,
never silently treated as empty coverage.

The existing coverage DSL is not automatically translated: its raw-attribute
gates need an explicit mapping to this finite activation model first.
