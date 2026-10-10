"""Shared provider adapter for explicit coverage declarations."""

from __future__ import annotations


def profile_records(target, name: str) -> list[dict]:
    """Expand a bound profile in a stable order, independent of set iteration."""
    obligations = target.profiles[name].run()
    return [
        dict(items)
        for items in sorted((tuple(sorted(obligation)) for obligation in obligations), key=repr)
    ]


def coverage_profiles(target, *, empty_profiles=()):
    """Expose declaration profiles through the provider's ``build_profile`` API.

    Providers without rejection cases explicitly list ``exceptional`` as empty.
    Concrete witness adapters can instead call ``profile_records`` directly.
    """
    empty_profiles = frozenset(empty_profiles)
    if empty_profiles & target.profiles.keys():
        raise ValueError("empty profiles must not override declared profiles")

    def build_profile(name: str, *, spec) -> tuple[list[dict], list[dict]]:
        if name in empty_profiles:
            return [], []
        records = profile_records(target.for_spec(spec), name)
        return records, records

    return build_profile
