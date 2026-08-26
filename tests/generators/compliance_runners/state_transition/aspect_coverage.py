"""Handler-agnostic combinatorial-over-aspects coverage.

A handler describes its coverage as a set of *aspects*, each a factor whose value
is the tuple of its coverage dimensions (`outcome` is usually one of them). This
module enumerates the handler model's feasible space once and provides t-wise
covering-set selection over any subset of aspects. Enumerated records also
retain the handler's fault count, allowing profiles to classify cases
independently of the terminal outcome.

A handler's own `coverage.py` supplies:
  - `model_path`  : the handler MiniZinc model,
  - `dims`        : the solution variables to read (its coverage dimensions),
  - `aspects`     : {aspect_name: [dim, ...]} (include an `outcome` dimension),
  - `rank(rec)`   : lower = cleaner representative (e.g. fewer faults),
and then calls `enumerate_signatures(...)` + `build_profile(...)`.

See `execution_payload_bid/coverage.py` for a worked instantiation.
"""

from __future__ import annotations

from collections.abc import Callable
from itertools import combinations
from typing import TYPE_CHECKING

import minizinc

if TYPE_CHECKING:
    from pathlib import Path

Aspects = dict[str, list[str]]
Rank = Callable[[dict], int]


def _state(rec: dict, dims: list[str]) -> tuple:
    return tuple(rec[d] for d in dims)


def signature(rec: dict, aspects: Aspects) -> tuple:
    return tuple(_state(rec, dims) for dims in aspects.values())


def enumerate_signatures(
    model_path: Path, dims: list[str], aspects: Aspects, rank: Rank | None = None
) -> list[dict]:
    """Distinct aspect-state representatives over the model's feasible space.

    Dedups by the full aspect signature, keeping the lowest-`rank` representative.
    """
    rank = rank or (lambda _r: 0)
    model = minizinc.Model(str(model_path))
    result = minizinc.Instance(minizinc.Solver.lookup("gecode"), model).solve(all_solutions=True)
    reps: dict[tuple, dict] = {}
    for sol in result:
        rec = {n: (bool(v) if isinstance(v := getattr(sol, n), bool) else str(v)) for n in dims}
        rec["_rank"] = rank(rec)
        # The handler rank is currently its fault count. Keep that value
        # explicit so profile selection is independent of the terminal outcome.
        rec["_nfaults"] = rec["_rank"]
        sig = signature(rec, aspects)
        if sig not in reps or rec["_rank"] < reps[sig]["_rank"]:
            reps[sig] = rec
    return list(reps.values())


def filter_faults(recs: list[dict], nfaults: int) -> list[dict]:
    """Return records with exactly ``nfaults`` independently counted faults."""
    return [rec for rec in recs if rec["_nfaults"] == nfaults]


def smoke(recs: list[dict], outcome_aspects: Aspects) -> tuple[int, list[dict]]:
    """Select one representative for each terminal outcome, when present."""
    if not any("outcome" in dims for dims in outcome_aspects.values()):
        return cover(recs, outcome_aspects, 1)
    return cover(recs, {"outcome": ["outcome"]}, 1)


def build_profile(
    recs: list[dict],
    name: str,
    all_aspects: Aspects,
    input_aspects: Aspects,
    outcome_aspect: Aspects,
    *,
    normal_outcome_aspect: Aspects | None = None,
    exceptional_aspects: Aspects | None = None,
    normal_t: int = 2,
    exceptional_t: int = 1,
) -> tuple[int, list[dict]]:
    """Build a standard set of fault-count coverage profiles.

    Handler modules provide their aspect groups and may override the normal
    outcome coverage, exceptional aspects, or coverage strength when they have
    a handler-specific policy.
    """
    if name == "all":
        return len(recs), recs
    if name == "smoke":
        return smoke(recs, all_aspects)
    if name == "normal":
        normal_records = filter_faults(recs, 0)
        normal = cover(normal_records, input_aspects, normal_t)
        if normal_outcome_aspect is None:
            return normal
        _, normal_inputs = cover(normal_records, input_aspects, normal_t)
        _, normal_outcomes = cover(normal_records, normal_outcome_aspect, 1)
        return -1, dedup(normal_inputs + normal_outcomes, all_aspects)
    if name == "exceptional":
        exceptional_coverage = (
            exceptional_aspects if exceptional_aspects is not None else outcome_aspect
        )
        return cover(filter_faults(recs, 1), exceptional_coverage, exceptional_t)
    if name == "standard":
        _, normal = build_profile(
            recs,
            "normal",
            all_aspects,
            input_aspects,
            outcome_aspect,
            normal_outcome_aspect=normal_outcome_aspect,
            exceptional_aspects=exceptional_aspects,
            normal_t=normal_t,
            exceptional_t=exceptional_t,
        )
        _, exceptional = build_profile(
            recs,
            "exceptional",
            all_aspects,
            input_aspects,
            outcome_aspect,
            normal_outcome_aspect=normal_outcome_aspect,
            exceptional_aspects=exceptional_aspects,
            normal_t=normal_t,
            exceptional_t=exceptional_t,
        )
        return -1, dedup(normal + exceptional, all_aspects)
    raise ValueError(f"unknown profile: {name}")


def _slice(
    recs: list[dict], outcome_dim: str, outcome_filter: str | None, accept: set
) -> list[dict]:
    if outcome_filter == "normal":
        return [r for r in recs if r[outcome_dim] in accept]
    if outcome_filter == "exceptional":
        return [r for r in recs if r[outcome_dim] not in accept]
    return recs


def cover(
    recs: list[dict],
    aspects: Aspects,
    t: int,
    outcome_filter: str | None = None,
    outcome_dim: str = "outcome",
    accept: str | set = "ACCEPT",
) -> tuple[int, list[dict]]:
    """Greedy t-wise covering set over `aspects` (within an optional outcome slice).

    `accept` is the outcome value (or set of values) that count as "normal";
    everything else is "exceptional". Returns (number of feasible t-wise
    obligations, chosen representatives).
    """
    accept_set = {accept} if isinstance(accept, str) else set(accept)
    names = list(aspects)
    dims_of = [aspects[n] for n in names]

    # Candidates deduplicated by their projection onto the chosen aspects.
    reps: dict[tuple, dict] = {}
    for rec in _slice(recs, outcome_dim, outcome_filter, accept_set):
        proj = tuple(_state(rec, d) for d in dims_of)
        if proj not in reps or rec["_rank"] < reps[proj]["_rank"]:
            reps[proj] = rec

    all_obl: set = set()
    covered_by: dict[tuple, frozenset] = {}
    for proj in reps:
        combos = {(sub, tuple(proj[k] for k in sub)) for sub in combinations(range(len(names)), t)}
        covered_by[proj] = frozenset(combos)
        all_obl |= combos

    uncovered = set(all_obl)
    chosen: list[dict] = []
    while uncovered:
        best, best_gain, best_rank = None, 0, 1 << 30
        for proj, combos in covered_by.items():
            gain = len(combos & uncovered)
            if gain > best_gain or (
                gain == best_gain and gain > 0 and reps[proj]["_rank"] < best_rank
            ):
                best, best_gain, best_rank = proj, gain, reps[proj]["_rank"]
        if best is None or best_gain == 0:
            break
        chosen.append(reps[best])
        uncovered -= covered_by[best]
    return len(all_obl), chosen


def dedup(recs: list[dict], aspects: Aspects) -> list[dict]:
    """Deduplicate a list of representatives by their full aspect signature."""
    seen: set = set()
    out: list[dict] = []
    for r in recs:
        sig = signature(r, aspects)
        if sig not in seen:
            seen.add(sig)
            out.append(r)
    return out
