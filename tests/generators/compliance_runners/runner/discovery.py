"""Discover supported vector formats independently of their generators."""

from pathlib import Path
from typing import NamedTuple

from eth_consensus_specs.test.helpers.specs import spec_targets

from .io import read_yaml

RUNNER_KINDS = {
    "operations": "state_transition",
    "epoch_processing": "state_transition",
    "sanity": "state_transition",
    "fork_choice": "fork_choice",
    "fork_choice_compliance": "fork_choice",
}


class VectorCase(NamedTuple):
    preset: str
    fork: str
    runner: str
    handler: str
    suite: str
    test_dir: Path

    @property
    def kind(self):
        return RUNNER_KINDS[self.runner]

    @property
    def id(self):
        return "::".join((*self[:5], self.test_dir.name))


def gather_tests(tests_dir, *, kind=None):
    if kind not in (None, "state_transition", "fork_choice"):
        raise ValueError(f"Unknown vector kind: {kind}")
    if isinstance(tests_dir, (list, tuple)):
        for path in tests_dir:
            yield from gather_tests(path, kind=kind)
        return

    tests_path = Path(tests_dir)
    roots = (
        [tests_path]
        if any((tests_path / preset).is_dir() for preset in spec_targets)
        else sorted(tests_path.glob("*/reftests"))
    )
    for root in roots:
        for preset in sorted(spec_targets):
            for fork in sorted(spec_targets[preset]):
                for directory in sorted((root / preset / fork).glob("*/*/*/*")):
                    if not directory.is_dir():
                        continue
                    runner, handler, suite = directory.relative_to(root / preset / fork).parts[:3]
                    manifest_path = directory / "manifest.yaml"
                    if manifest_path.exists():
                        manifest = read_yaml(manifest_path)
                        runner, handler, suite = (
                            manifest[key] for key in ("runner", "handler", "suite")
                        )
                    case_kind = RUNNER_KINDS.get(runner)
                    if case_kind is None or (kind is not None and case_kind != kind):
                        continue
                    yield VectorCase(preset, fork, runner, handler, suite, directory)


def select_tests(tests, start=None, limit=None):
    if start is not None:
        tests = tests[start:]
    if limit is not None:
        tests = tests[:limit]
    return tests
