#!/usr/bin/env python3
"""Combine pyspec coverage data from the minimal and mainnet presets.

The pyspec is generated once per preset (eth_consensus_specs/<fork>/minimal.py
and eth_consensus_specs/<fork>/mainnet.py), so coverage.py treats them as
unrelated files. This script folds the mainnet data onto the minimal modules.
Line numbers are translated with a diff-based mapping, so it works even when
the two files do not align exactly. Coverage of preset-specific lines (those
with no identical counterpart in the minimal module) is dropped and reported.

Each fork's combined data is recorded under a short <fork>.py name (eg fulu.py)
in the current directory. The script creates those files as copies of the
minimal modules because report generation needs to read the source. Run this
script and the report commands from the same directory, then delete the copies.

Usage:
    uv run python scripts/combine_preset_coverage.py [DATA_FILE ...]

Reads .coverage by default and writes .coverage.combined. Pass multiple data
files (e.g. from separate minimal and mainnet runs) to merge them all.
"""

import argparse
import difflib
import shutil
from pathlib import Path

from coverage import CoverageData


def line_map(from_file: str, to_file: str) -> dict:
    """Map line numbers in from_file to matching lines in to_file (1-based).

    Only textually identical lines are mapped, so coverage of code that
    genuinely differs between presets is never misattributed.
    """
    a = Path(from_file).read_text().splitlines(keepends=True)
    b = Path(to_file).read_text().splitlines(keepends=True)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    mapping = {}
    for blk in sm.get_matching_blocks():
        for i in range(blk.size):
            mapping[blk.a + i + 1] = blk.b + i + 1
    return mapping


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "data_files",
        nargs="*",
        default=[".coverage"],
        help="coverage data files to merge (default: .coverage)",
    )
    parser.add_argument(
        "--output",
        default=".coverage.combined",
        help="output data file (default: .coverage.combined)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="show each dropped entry with its source line",
    )
    args = parser.parse_args()

    dst = CoverageData(args.output)
    total_dropped = 0
    created = []

    for data_file in args.data_files:
        src = CoverageData(data_file)
        src.read()

        for f in sorted(src.measured_files()):
            p = Path(f)
            minimal = p.with_name("minimal.py")
            if p.name not in ("minimal.py", "mainnet.py") or not minimal.exists():
                # Not a per-preset spec module: copy as-is.
                if src.has_arcs():
                    dst.add_arcs({f: src.arcs(f)})
                else:
                    dst.add_lines({f: src.lines(f)})
                continue

            # Record the data under a short per-fork name (eg fulu.py), backed
            # by a copy of the minimal module so reports can read the source.
            target = Path.cwd() / f"{p.parent.name}.py"
            if str(target) not in created:
                shutil.copyfile(minimal, target)
                created.append(str(target))
            canon = str(target)

            if p.name == "minimal.py":
                # The minimal module is the merge target, no translation needed.
                if src.has_arcs():
                    dst.add_arcs({canon: src.arcs(f)})
                else:
                    dst.add_lines({canon: src.lines(f)})
                continue

            mapping = line_map(f, str(minimal))
            source = Path(f).read_text().splitlines()

            def translate(n: int) -> int | None:
                # Negative arc endpoints mean "exit from the function whose
                # body starts at line -n", so map the magnitude and keep the sign.
                mapped = mapping.get(abs(n))
                if mapped is None:
                    return None
                return mapped if n > 0 else -mapped

            def describe(n: int) -> str:
                text = source[abs(n) - 1].strip() if 0 < abs(n) <= len(source) else "?"
                return f"line {n} [{text}]"

            dropped = []
            if src.has_arcs():
                arcs = []
                for a, b in src.arcs(f):
                    ta, tb = translate(a), translate(b)
                    if ta is not None and tb is not None:
                        arcs.append((ta, tb))
                    else:
                        bad = a if ta is None else b
                        dropped.append((abs(bad), f"arc ({a} -> {b}): {describe(bad)}"))
                dst.add_arcs({canon: arcs})
            else:
                lines = []
                for n in src.lines(f):
                    tn = translate(n)
                    if tn is not None:
                        lines.append(tn)
                    else:
                        dropped.append((abs(n), describe(n)))
                dst.add_lines({canon: lines})

            if dropped:
                print(f"{f}: dropped {len(dropped)} preset-specific entries")
                if args.verbose:
                    for _, entry in sorted(set(dropped)):
                        print(f"  {entry}")
            total_dropped += len(dropped)

    dst.write()
    print(f"Wrote {args.output} (dropped {total_dropped} preset-specific entries)")
    if created:
        names = ", ".join(Path(c).name for c in sorted(created))
        print(f"Created source copies for report generation: {names}")
        print("Generate reports from this directory, then delete the copies.")


if __name__ == "__main__":
    main()
