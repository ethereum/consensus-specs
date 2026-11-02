"""Single-pass solving retains MiniZinc diagnostics and exhaustive enumeration."""

import io
import json
import subprocess
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

import minizinc
import pytest

from .minizinc_backend import _solve


@pytest.fixture
def solver_process(monkeypatch):
    configuration = SimpleNamespace(
        stdFlags=["-a"], configuration=lambda: nullcontext("selected-solver")
    )
    monkeypatch.setattr(minizinc, "default_driver", SimpleNamespace(executable="/mock/minizinc"))
    lookups = []

    def lookup(solver, *, driver):
        lookups.append((solver, driver))
        return configuration

    monkeypatch.setattr(minizinc.Solver, "lookup", lookup)

    class Process:
        messages: ClassVar[list] = []
        stderr = b""
        returncode = 0
        killed = False
        terminated = False
        stuck = False
        commands: ClassVar[list] = []

        def __init__(self, command, *, stdout, stderr):
            self.commands.append(command)
            assert stdout == subprocess.PIPE
            self.model = Path(command[-1])
            assert self.model.read_text() == "solve satisfy;\n"
            stderr.write(self.stderr)
            self.stdout = io.BytesIO(
                b"\n".join(json.dumps(m).encode() for m in self.messages) + b"\n"
            )

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stdout.close()

        def wait(self, timeout=None):
            if self.stuck and timeout is not None:
                raise subprocess.TimeoutExpired("minizinc", timeout)
            return self.returncode

        def terminate(self):
            type(self).terminated = True

        def kill(self):
            self.killed = True
            type(self).killed = True

    monkeypatch.setattr(subprocess, "Popen", Process)
    return Process, configuration, lookups


def test_solve_uses_one_process_and_selected_solver(solver_process):
    process, _, lookups = solver_process
    process.messages = [
        {"type": "solution", "output": {"json": {"v_0": 1, "v_1": 0}}},
        {"type": "solution", "output": {"json": {"v_0": 2, "v_1": 1}}},
        {"type": "status", "status": "ALL_SOLUTIONS"},
    ]
    solutions = _solve("solve satisfy;\n", "requested-solver")
    assert [vars(s) for s in solutions] == [{"v_0": 1, "v_1": 0}, {"v_0": 2, "v_1": 1}]
    assert lookups == [("requested-solver", minizinc.default_driver)]
    assert len(process.commands) == 1
    command = process.commands[0]
    assert command[:-1] == [
        "/mock/minizinc",
        "--solver",
        "selected-solver",
        "--json-stream",
        "--output-mode",
        "json",
        "--all-solutions",
    ]
    assert not Path(command[-1]).parent.exists()


def test_unsatisfiable_and_warnings(solver_process):
    process, _, _ = solver_process
    process.messages = [
        {"type": "warning", "message": "model inconsistency"},
        {"type": "status", "status": "UNSATISFIABLE"},
    ]
    with pytest.warns(minizinc.error.MiniZincWarning, match="model inconsistency"):
        assert _solve("solve satisfy;\n", "gecode") == []


@pytest.mark.parametrize("status", [None, "SATISFIED", "UNKNOWN", "ERROR", "UNBOUNDED"])
def test_partial_results_are_rejected(solver_process, status):
    process, _, _ = solver_process
    process.messages = [{"type": "solution", "output": {"json": {"obligation": 1}}}]
    if status is not None:
        process.messages.append({"type": "status", "status": status})
    with pytest.raises(RuntimeError, match="incomplete MiniZinc enumeration"):
        _solve("solve satisfy;\n", "gecode")


def test_nonzero_exit_is_rejected_even_with_complete_status(solver_process):
    process, _, _ = solver_process
    process.returncode = 1
    process.stderr = b"Error: solver crashed"
    process.messages = [{"type": "status", "status": "ALL_SOLUTIONS"}]
    with pytest.raises(minizinc.error.MiniZincError, match="solver crashed"):
        _solve("solve satisfy;\n", "gecode")


@pytest.mark.parametrize("stuck", [False, True])
def test_stream_errors_terminate_process_and_clean_model(solver_process, stuck):
    process, _, _ = solver_process
    process.stuck = stuck
    process.messages = [{"type": "error", "what": "syntax error", "message": "bad model"}]
    with pytest.raises(minizinc.error.SyntaxError, match="bad model"):
        _solve("solve satisfy;\n", "gecode")
    assert process.terminated
    assert process.killed == stuck
    assert not Path(process.commands[0][-1]).parent.exists()


def test_solver_must_support_all_solutions(solver_process):
    process, configuration, _ = solver_process
    configuration.stdFlags = []
    with pytest.raises(NotImplementedError, match="-a flag"):
        _solve("solve satisfy;\n", "gecode")
    assert not process.commands


def test_missing_driver(monkeypatch):
    monkeypatch.setattr(minizinc, "default_driver", None)
    with pytest.raises(minizinc.error.ConfigurationError, match="No compatible MiniZinc driver"):
        _solve("solve satisfy;\n", "gecode")
