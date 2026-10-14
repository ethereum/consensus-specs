"""Declaration profiles with complete, fault-scoped proposer-slashing witnesses."""

from .target import TARGET
from .witness import materializer_record


def build_profile(name, *, spec):
    target = TARGET.for_spec(spec)
    formula = target.profiles[name]
    chosen = set()
    # Complete within each compiled branch, retaining its fault restrictions.
    # Prefer fewer faults so max's low-fault witnesses also cover higher-order
    # exceptional projections wherever possible.
    for _, configurations, obligations in formula._compiled():
        ordered = sorted(
            configurations,
            key=lambda c: (target.assertion_result(dict(c)).fault_count, repr(sorted(c))),
        )
        for obligation in obligations:
            chosen.add(next(c for c in ordered if obligation <= c))
    return (
        [dict(o) for o in sorted(formula.run(), key=lambda o: repr(sorted(o)))],
        [materializer_record(dict(c)) for c in sorted(chosen, key=lambda c: repr(sorted(c)))],
    )


__all__ = ("TARGET", "build_profile")
