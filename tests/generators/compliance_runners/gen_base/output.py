from __future__ import annotations

from tests.infra.dumper import Dumper

from .gen_typing import TestCaseResult


def dump_test_case_result(test_case_result: TestCaseResult, dumper: Dumper) -> None:
    """Write a collected test case result to storage."""
    test_case = test_case_result.test_case

    for name, kind, data in test_case_result.case_parts:
        method = getattr(dumper, f"dump_{kind}", None)
        if method is None:
            raise ValueError(f"Unknown kind {kind!r}")
        method(test_case.dir, name, data)

    if test_case_result.meta:
        dumper.dump_meta(test_case.dir, test_case_result.meta)

    manifest_data = {
        "preset": test_case.preset_name,
        "fork": test_case.fork_name,
        "runner": test_case.runner_name,
        "handler": test_case.handler_name,
        "suite": test_case.suite_name,
        "case": test_case.case_name,
    }
    dumper.dump_manifest(test_case.dir, manifest_data)
