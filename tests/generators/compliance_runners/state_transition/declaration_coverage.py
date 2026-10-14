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


def profile_records(target, name: str, *, complete=False) -> list[dict]:
    """Expand a bound profile in a stable order, independent of set iteration."""
    obligations = target.profiles[name].generation_obligations(complete=complete)
    return [
        dict(items)
        for items in sorted((tuple(sorted(obligation)) for obligation in obligations), key=repr)
    ]


def coverage_profiles(
    target,
    *,
    complete=False,
    witness=None,
    candidates=None,
    materializer=False,
    backend=None,
    solver=None,
):
    """Expose declaration profiles through the provider's ``build_profile`` API.

    An omitted ``exceptional`` profile returns empty records. Other missing
    profile names raise an error.
    ``complete`` requests full abstract assignments within each formula branch.
    ``witness(record)`` converts assignments to materializer records; alternatively,
    ``candidates(spec)`` supplies concrete records to match against obligations.
    Representative selection and deduplication are deterministic.
    ``backend`` and ``solver`` optionally select the declaration target backend.
    ``materializer`` selects the generic adapter for all target dimensions,
    completing assignments and adding assertion fault metadata automatically.
    """
    if witness is not None and candidates is not None:
        raise ValueError("choose either a witness adapter or concrete candidates")
    if materializer and (witness is not None or candidates is not None):
        raise ValueError("choose either the generic materializer adapter or a custom adapter")

    def build_profile(name: str, *, spec) -> tuple[list[dict], list[dict]]:
        if name == "exceptional" and name not in target.profiles:
            return [], []
        bound = target.for_spec(spec, backend=backend, solver=solver)
        records = profile_records(bound, name, complete=complete or materializer)
        if witness is None and candidates is None and not materializer:
            return records, records
        if materializer:

            def adapt(record):
                return materializer_record(bound, record)

        elif candidates is not None:
            factor_names = {f.name for f in bound.factors}
            ordered = sorted(
                candidates(spec),
                key=lambda r: (
                    repr(sorted((n, v) for n, v in r.items() if n in factor_names)),
                    repr(sorted(r.items())),
                ),
            )

            def adapt(record):
                for candidate in ordered:
                    if record.items() <= candidate.items():
                        return candidate
                raise ValueError(f"no concrete witness for {record}")

        else:
            adapt = witness
        chosen = {}
        for record in records:
            representative = adapt(record)
            chosen.setdefault(tuple(sorted(representative.items())), representative)
        return records, list(chosen.values())

    return build_profile
