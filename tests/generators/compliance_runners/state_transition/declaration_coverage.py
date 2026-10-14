"""Shared provider adapter for explicit coverage declarations."""

from __future__ import annotations


def profile_records(target, name: str, *, complete=False) -> list[dict]:
    """Expand a bound profile in a stable order, independent of set iteration."""
    obligations = target.profiles[name].generation_obligations(complete=complete)
    return [
        dict(items)
        for items in sorted((tuple(sorted(obligation)) for obligation in obligations), key=repr)
    ]


def coverage_profiles(target, *, empty_profiles=(), complete=False, witness=None, candidates=None):
    """Expose declaration profiles through the provider's ``build_profile`` API.

    Providers without rejection cases explicitly list ``exceptional`` as empty.
    ``complete`` requests full abstract assignments within each formula branch.
    ``witness(record)`` converts assignments to materializer records; alternatively,
    ``candidates(spec)`` supplies concrete records to match against obligations.
    Representative selection and deduplication are deterministic.
    """
    empty_profiles = frozenset(empty_profiles)
    if empty_profiles & target.profiles.keys():
        raise ValueError("empty profiles must not override declared profiles")
    if witness is not None and candidates is not None:
        raise ValueError("choose either a witness adapter or concrete candidates")

    def build_profile(name: str, *, spec) -> tuple[list[dict], list[dict]]:
        if name in empty_profiles:
            return [], []
        bound = target.for_spec(spec)
        records = profile_records(bound, name, complete=complete)
        if witness is None and candidates is None:
            return records, records
        if candidates is not None:
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
