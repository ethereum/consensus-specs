"""Reproducible generation/scoring baseline with isolated backend processes.

Imports are excluded from timings. Each profile starts with a fresh target
binding; scoring then uses that binding's generation caches. Repeats reuse the
worker process, so module-level fixture caches can warm up. RSS includes imports
and is a process peak, not incremental memory or a combined Python/solver peak.
"""

from __future__ import annotations

import argparse
import gc
import json
import platform
import resource
import subprocess
import sys
from hashlib import sha256
from importlib import import_module
from pathlib import Path
from statistics import median
from time import perf_counter

from tests.generators.compliance_runners.state_transition.declaration_coverage import (
    profile_records,
)
from tests.generators.compliance_runners.state_transition.evaluation import minizinc_backend
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    score,
    TARGETS,
)
from tests.generators.compliance_runners.state_transition.provider import PROFILES

from .backend_config import BACKENDS, DEFAULT_SOLVER

# The fourteen TARGET providers inheriting Python before centralization. Keep
# this baseline cohort stable so future measurements remain comparable.
MIGRATED_PROVIDERS = (
    "attestation",
    "attester_slashing",
    "bls_to_execution_change",
    "builder_deposit_request",
    "builder_exit_request",
    "builder_pending_payments",
    "builder_pending_withdrawal_processing",
    "deposit_request",
    "effective_balance_updates",
    "process_operations_dispatch",
    "pending_consolidations",
    "ptc_window",
    "slashings",
    "sync_aggregate",
)


def fingerprint(rows):
    canonical = sorted((tuple(sorted(dict(row).items())) for row in rows), key=repr)
    return sha256(json.dumps(canonical).encode()).hexdigest()


def distribution(values):
    return {"min": min(values), "median": median(values), "max": max(values)}


def measure(provider, preset, backend, profiles, repeats):
    from eth_consensus_specs.test.helpers.specs import spec_targets  # noqa: PLC0415

    template = import_module(TARGETS[provider]).TARGET
    spec = spec_targets[preset]["gloas"]
    samples = []
    solve_calls = 0
    original_solve = minizinc_backend._solve

    def solve(*args, **kwargs):
        nonlocal solve_calls
        solve_calls += 1
        return original_solve(*args, **kwargs)

    minizinc_backend._solve = solve
    try:
        for repeat in range(repeats):
            for profile in profiles:
                if profile not in template.profiles:
                    continue
                gc.collect()
                calls_before = solve_calls
                started = perf_counter()
                bound = template.for_spec(spec, backend=backend, solver=DEFAULT_SOLVER)
                records = profile_records(bound, profile)
                generation_seconds = perf_counter() - started
                generation_calls = solve_calls - calls_before
                formula = bound.profiles[profile]
                obligations = formula.run()
                observations = [
                    {k: v for k, v in record.items() if v != "NA"} for record in records
                ]
                calls_before = solve_calls
                started = perf_counter()
                report = score(bound, observations, formula, profile)
                scoring_seconds = perf_counter() - started
                if report.covered != report.total or report.unexpected or report.outcome_mismatches:
                    raise AssertionError(
                        f"incomplete scoring: {provider}/{preset}/{backend}/{profile}"
                    )
                samples.append(
                    {
                        "repeat": repeat,
                        "profile": profile,
                        "records": len(records),
                        "obligations": len(obligations),
                        "record_digest": fingerprint(records),
                        "obligation_digest": fingerprint(obligations),
                        "report_digest": sha256(
                            json.dumps(report.as_dict(), sort_keys=True).encode()
                        ).hexdigest(),
                        "generation_seconds": generation_seconds,
                        "scoring_seconds": scoring_seconds,
                        "generation_solver_calls": generation_calls,
                        "scoring_solver_calls": solve_calls - calls_before,
                    }
                )
                # Keep bindings independent and avoid retaining a previous
                # profile's feasible rows across the next measurement.
                del bound, formula, records, observations, obligations, report
    finally:
        minizinc_backend._solve = original_solve
    summaries = {}
    for profile in profiles:
        selected = [sample for sample in samples if sample["profile"] == profile]
        if not selected:
            continue
        signatures = {
            (s["record_digest"], s["obligation_digest"], s["report_digest"]) for s in selected
        }
        if len(signatures) != 1:
            raise AssertionError(
                f"nondeterministic results: {provider}/{preset}/{backend}/{profile}"
            )
        summaries[profile] = {
            key: selected[0][key]
            for key in (
                "records",
                "obligations",
                "record_digest",
                "obligation_digest",
                "report_digest",
            )
        } | {
            key: distribution([s[key] for s in selected])
            for key in (
                "generation_seconds",
                "scoring_seconds",
                "generation_solver_calls",
                "scoring_solver_calls",
            )
        }
    rss_unit = 1 if sys.platform == "darwin" else 1024
    return {
        "provider": provider,
        "preset": preset,
        "backend": backend,
        "profiles": summaries,
        "samples": samples,
        "python_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * rss_unit,
        "child_peak_rss_bytes": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * rss_unit,
    }


def check_parity(results):
    by_key = {}
    checked = 0
    for result in results:
        for profile, values in result["profiles"].items():
            key = result["provider"], result["preset"], profile
            signature = tuple(
                values[field]
                for field in (
                    "records",
                    "obligations",
                    "record_digest",
                    "obligation_digest",
                    "report_digest",
                )
            )
            if key in by_key:
                if by_key[key] != signature:
                    raise AssertionError(f"backend parity mismatch: {key}")
                checked += 1
            else:
                by_key[key] = signature
    return checked


def save_report(output, report):
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    lines = [
        "# TARGET backend baseline",
        "",
        f"Status: {report['status']}; repeats: {report['parameters']['repeats']}; parity comparisons: {report['parity_comparisons']}.",
        "",
        "Fresh binding per profile; scoring reuses generation caches. Imports are excluded from timings.",
        "Times below sum per-profile medians. RSS is each isolated Python worker's peak, including imports.",
        "Child-process peaks are recorded separately in JSON; these are not combined process peaks.",
        "",
        "| Provider | Preset | Backend | Generation (s) | Scoring (s) | Python peak (MiB) |",
        "|---|---|---|---:|---:|---:|",
    ]
    for result in report["results"]:
        generation = sum(v["generation_seconds"]["median"] for v in result["profiles"].values())
        scoring = sum(v["scoring_seconds"]["median"] for v in result["profiles"].values())
        lines.append(
            f"| {result['provider']} | {result['preset']} | {result['backend']} | {generation:.4f} | {scoring:.4f} | {result['python_peak_rss_bytes'] / 2**20:.1f} |"
        )
    output.with_suffix(".md").write_text("\n".join(lines) + "\n")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--providers", nargs="+", choices=sorted(TARGETS), default=MIGRATED_PROVIDERS
    )
    parser.add_argument(
        "--presets", nargs="+", choices=("minimal", "mainnet"), default=("minimal", "mainnet")
    )
    parser.add_argument("--backends", nargs="+", choices=BACKENDS, default=BACKENDS)
    parser.add_argument("--profiles", nargs="+", choices=PROFILES, default=PROFILES)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    return args


def main(argv=None):
    args = parse_args(argv)
    if args.worker:
        if not (len(args.providers) == len(args.presets) == len(args.backends) == 1):
            raise ValueError("a worker measures one provider/preset/backend")
        print(
            json.dumps(
                measure(
                    args.providers[0],
                    args.presets[0],
                    args.backends[0],
                    args.profiles,
                    args.repeats,
                )
            )
        )
        return
    import minizinc  # noqa: PLC0415 - parent environment metadata

    report = {
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "minizinc_python": minizinc.__version__,
            "minizinc_driver": str(minizinc.default_driver.parsed_version)
            if minizinc.default_driver
            else None,
            "solver": DEFAULT_SOLVER,
        },
        "parameters": {
            "providers": args.providers,
            "presets": args.presets,
            "backends": args.backends,
            "profiles": args.profiles,
            "repeats": args.repeats,
        },
        "status": "running",
        "parity_comparisons": 0,
        "results": [],
    }
    for provider in args.providers:
        for preset in args.presets:
            for backend in args.backends:
                command = [
                    sys.executable,
                    "-m",
                    __spec__.name,
                    "--worker",
                    "--providers",
                    provider,
                    "--presets",
                    preset,
                    "--backends",
                    backend,
                    "--profiles",
                    *args.profiles,
                    "--repeats",
                    str(args.repeats),
                    "--output",
                    str(args.output),
                ]
                result = subprocess.run(command, capture_output=True, text=True, check=False)
                if result.returncode:
                    raise RuntimeError(
                        f"benchmark worker failed for {provider}/{preset}/{backend}:\n{result.stderr}"
                    )
                report["results"].append(json.loads(result.stdout))
                report["parity_comparisons"] = check_parity(report["results"])
                save_report(args.output, report)
                print(f"{provider}/{preset}/{backend}: complete", flush=True)
    report["status"] = "complete"
    save_report(args.output, report)
    print(f"Parity comparisons: {report['parity_comparisons']}; report: {args.output}", flush=True)


if __name__ == "__main__":
    main()
