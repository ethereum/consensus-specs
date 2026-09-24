"""Coverage profiles for registry updates."""

from .target import TARGET


def build_profile(name: str, *, spec=None):
    if name == "exceptional":
        return [], []
    target = TARGET if spec is None else TARGET.for_spec(spec)
    profiles = target.profiles
    formula = profiles.get(name, profiles["standard"])
    records = [dict(item) for item in sorted(formula.run("predicate"), key=repr)]
    return records, records


__all__ = ("TARGET", "build_profile")
