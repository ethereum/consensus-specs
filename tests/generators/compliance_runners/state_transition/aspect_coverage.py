"""Handler-agnostic combinatorial-over-aspects coverage.

A handler describes its coverage as a set of *aspects*, each a factor whose value
is the tuple of its coverage dimensions (`outcome` is usually one of them). This
module enumerates the handler model's feasible space once and provides t-wise
covering-set selection over any subset of aspects, optionally restricted to an
outcome slice (normal / exceptional).

A handler's own `coverage.py` supplies:
  - `model_path`  : the handler MiniZinc model,
  - `dims`        : the solution variables to read (its coverage dimensions),
  - `aspects`     : {aspect_name: [dim, ...]} (include an `outcome` aspect),
  - `rank(rec)`   : lower = cleaner representative (e.g. fewer faults),
and then calls `enumerate_signatures(...)` + `cover(...)`.

See `execution_payload_bid/coverage.py` for a worked instantiation.
"""
from __future__ import annotations

from itertools import combinations
from pathlib import Path
from typing import Any, Callable

import minizinc

Aspects = dict[str, list[str]]
Rank = Callable[[dict], int]


def _state(rec: dict, dims: list[str]) -> tuple:
    return tuple(rec[d] for d in dims)


def signature(rec: dict, aspects: Aspects) -> tuple:
    return tuple(_state(rec, dims) for dims in aspects.values())


def enumerate_signatures(model_path: Path, dims: list[str], aspects: Aspects,
                         rank: Rank | None = None) -> list[dict]:
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
        sig = signature(rec, aspects)
        if sig not in reps or rec["_rank"] < reps[sig]["_rank"]:
            reps[sig] = rec
    return list(reps.values())


def _slice(recs: list[dict], outcome_dim: str, outcome_filter: str | None, accept: str) -> list[dict]:
    if outcome_filter == "normal":
        return [r for r in recs if r[outcome_dim] == accept]
    if outcome_filter == "exceptional":
        return [r for r in recs if r[outcome_dim] != accept]
    return recs


def cover(recs: list[dict], aspects: Aspects, t: int,
          outcome_filter: str | None = None, outcome_dim: str = "outcome",
          accept: str = "ACCEPT") -> tuple[int, list[dict]]:
    """Greedy t-wise covering set over `aspects` (within an optional outcome slice).

    Returns (number of feasible t-wise obligations, chosen representatives).
    """
    names = list(aspects)
    dims_of = [aspects[n] for n in names]

    # Candidates deduplicated by their projection onto the chosen aspects.
    reps: dict[tuple, dict] = {}
    for rec in _slice(recs, outcome_dim, outcome_filter, accept):
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
            if gain > best_gain or (gain == best_gain and gain > 0 and reps[proj]["_rank"] < best_rank):
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
