"""Shared provider adapter for explicit coverage declarations."""

from __future__ import annotations

from tests.generators.compliance_runners.tools.coverage_model import MISSING

from .evaluation.coverage_dsl import NA


def materializer_record(target, assignment):
    """Encode a complete abstract assignment using the target's activation model.

    Inactive dimensions become ``"NA"``. Active values retain their native types.
    """
    if target._bound_spec is None:
        raise ValueError("bind the target with for_spec(spec) before adapting witnesses")
    model = target.definition.model(target.bound_constants)
    names = tuple(f.name for f in model.factors)
    active = {}
    for factor in model._ordered:
        if not all(
            parent in active and active[parent] in values for parent, values in factor.conditions
        ):
            continue
        value = assignment.get(factor.name, MISSING)
        if value is NA or value is MISSING:
            raise ValueError(f"missing active dimension: {factor.name}")
        if not any(type(value) is type(v) and value == v for v in factor.values):
            raise ValueError(f"invalid coverage value for {factor.name}: {value!r}")
        active[factor.name] = value
    return {name: active.get(name, "NA") for name in names}


def profile_records(target, name: str) -> list[dict]:
    """Return canonical complete profile cases in a stable order."""
    obligations = target.profiles[name].generation_obligations()
    return [
        materializer_record(target, dict(items))
        for items in sorted((tuple(sorted(obligation)) for obligation in obligations), key=repr)
    ]


def coverage_profiles(target, *, backend=None, solver=None):
    """Expose complete declaration witnesses through the provider profile API.

    Return canonical complete cases in stable order.
    Cases contain only TARGET dimensions, encoding inactive values as "NA". An
    omitted exceptional profile returns empty lists; other missing profiles
    raise an error. Omitted backend/solver options inherit the TARGET defaults declared by
    bind(). Explicit options override those defaults for this adapter.
    """

    def build_profile(name: str, *, spec) -> list[dict]:
        if name == "exceptional" and name not in target.profiles:
            return []
        bound = target.for_spec(spec, backend=backend, solver=solver)
        return profile_records(bound, name)

    return build_profile
