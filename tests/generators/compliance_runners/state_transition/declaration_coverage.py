"""Shared provider adapter for explicit coverage declarations."""

from __future__ import annotations

from tests.generators.compliance_runners.tools.coverage_model import MISSING

from .evaluation.coverage_dsl import NA


def materializer_record(target, assignment):
    """Encode a complete abstract assignment using the target's activation model.

    Inactive dimensions become ``"NA"``. Active values retain their native types.
    Assertion fault counts supply ``_nfaults`` and ``_rank`` (zero for targets
    without assertions).
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
    summary = target.assertion_result(active)
    faults = 0 if summary is None else summary.fault_count
    if faults is None:
        raise ValueError(f"materializer witness has unknown assertions: {summary.unknown}")
    record = {name: active.get(name, "NA") for name in names}
    return {**record, "_nfaults": faults, "_rank": faults}


def profile_records(target, name: str) -> list[dict]:
    """Return complete profile witnesses in a stable order."""
    obligations = target.profiles[name].generation_obligations()
    return [
        dict(items)
        for items in sorted((tuple(sorted(obligation)) for obligation in obligations), key=repr)
    ]


def coverage_profiles(target, *, backend=None, solver=None):
    """Expose complete declaration witnesses through the provider profile API.

    Return abstract records and canonical materializer representatives in stable
    order. Representatives encode inactive dimensions as "NA" and include fault
    metadata. An omitted exceptional profile returns empty lists; other missing
    profiles raise an error. Backend and solver override the target defaults.
    """

    def build_profile(name: str, *, spec) -> tuple[list[dict], list[dict]]:
        if name == "exceptional" and name not in target.profiles:
            return [], []
        bound = target.for_spec(spec, backend=backend, solver=solver)
        records = profile_records(bound, name)
        return records, [materializer_record(bound, record) for record in records]

    return build_profile
