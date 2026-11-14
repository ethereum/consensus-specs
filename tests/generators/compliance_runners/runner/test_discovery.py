"""Regression tests for mixed-format vector discovery."""

from .discovery import gather_tests, select_tests


def test_mixed_roots_and_filtering(tmp_path):
    root = tmp_path / "batch" / "reftests"
    for runner in ("operations", "fork_choice_compliance", "fork_choice", "unknown"):
        case = root / "minimal" / "gloas" / runner / "handler" / "main" / "case_0"
        case.mkdir(parents=True)
    cases = list(gather_tests(tmp_path))
    assert len(cases) == 3
    assert len(list(gather_tests(root, kind="fork_choice"))) == 2
    assert [case.runner for case in gather_tests([root], kind="state_transition")] == ["operations"]
    assert select_tests(cases, start=1, limit=1) == cases[1:2]


def test_manifest_metadata(tmp_path):
    case = tmp_path / "minimal/gloas/operations/old/main/case_0"
    case.mkdir(parents=True)
    (case / "manifest.yaml").write_text("runner: operations\nhandler: deposit\nsuite: smoke\n")
    (info,) = gather_tests(tmp_path)
    assert info.handler == "deposit"
    assert info.suite == "smoke"
    assert info.id == "minimal::gloas::operations::deposit::smoke::case_0"
