#!/usr/bin/env python3
"""Map a list of changed paths (one per line on stdin) to the set of forks
whose reference test vectors should be regenerated.

Used by .github/workflows/pr-vectors.yml to keep PR-triggered vector runs
focused on the forks actually touched by the PR.

Output: a single JSON array of fork names on stdout, e.g. ["gloas","heze"].
If the PR touches build/runner/utility code that affects every fork, or if
no recognizable spec/test paths changed, the script falls back to the full
fork list so the maintainer always gets a safe-by-default run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPECS_DIR = REPO_ROOT / "specs"


def all_forks() -> list[str]:
    return sorted(
        p.name for p in SPECS_DIR.iterdir() if p.is_dir() and not p.name.startswith("_")
    )


GLOBAL_PREFIXES = (
    "tests/generators/",
    "tests/core/pyspec/eth_consensus_specs/utils/",
    "tests/core/pyspec/eth_consensus_specs/config/",
    "configs/",
    "specs/_features/",
)

GLOBAL_FILES = {"Makefile", "pyproject.toml", "uv.lock"}


def affected(paths: list[str], forks: list[str]) -> set[str]:
    fork_set = set(forks)
    hit: set[str] = set()
    for raw in paths:
        path = raw.strip()
        if not path:
            continue
        if path in GLOBAL_FILES or path.startswith(GLOBAL_PREFIXES):
            return fork_set
        for fork in fork_set:
            if (
                path.startswith(f"specs/{fork}/")
                or path.startswith(f"presets/mainnet/{fork}.")
                or path.startswith(f"presets/minimal/{fork}.")
                or path.startswith(f"tests/core/pyspec/eth_consensus_specs/{fork}/")
                or path.startswith(f"tests/core/pyspec/eth_consensus_specs/test/{fork}/")
            ):
                hit.add(fork)
                break
    return hit


def main() -> int:
    forks = all_forks()
    paths = sys.stdin.read().splitlines()
    selected = affected(paths, forks)
    if not selected:
        selected = set(forks)
    print(json.dumps(sorted(selected)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
