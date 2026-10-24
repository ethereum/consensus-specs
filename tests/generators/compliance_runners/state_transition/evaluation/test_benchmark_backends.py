"""Benchmark baselines compare semantics independently of timing measurements."""

from copy import deepcopy

import pytest

from .benchmark_backends import check_parity, measure, save_report


def test_baseline_records_generation_scoring_and_parity(tmp_path):
    results = [
        measure("eth1_data_reset", "minimal", backend, ("smoke", "max"), 1)
        for backend in ("python", "minizinc")
    ]
    assert check_parity(results) == 2
    for result in results:
        assert result["python_peak_rss_bytes"] > 0
        for profile in result["profiles"].values():
            assert profile["records"] > 0
            assert profile["scoring_solver_calls"]["max"] == 0
            assert profile["generation_seconds"]["min"] >= 0
    assert results[0]["profiles"]["smoke"]["generation_solver_calls"]["max"] == 0
    assert results[1]["profiles"]["smoke"]["generation_solver_calls"]["min"] > 0
    output = tmp_path / "baseline.json"
    save_report(
        output,
        {
            "status": "complete",
            "parameters": {"repeats": 1},
            "parity_comparisons": 2,
            "results": results,
        },
    )
    assert output.is_file()
    assert "Status: complete" in output.with_suffix(".md").read_text()
    changed = deepcopy(results)
    changed[1]["profiles"]["smoke"]["record_digest"] = "different witnesses"
    with pytest.raises(AssertionError, match="backend parity mismatch"):
        check_parity(changed)
