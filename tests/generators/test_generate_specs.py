import sys
from pathlib import Path

from pysetup import generate_specs


def test_all_forks_with_custom_output_directory_use_fork_subdirectories(
    monkeypatch, tmp_path: Path
) -> None:
    generated: dict[str, Path] = {}

    def record_output_directory(fork: str, out_dir: Path, **_: object) -> None:
        generated[fork] = out_dir

    monkeypatch.setattr(sys, "argv", ["generate_specs.py", "--all-forks", "--out-dir", str(tmp_path)])
    monkeypatch.setattr(generate_specs, "generate_fork_specs", record_output_directory)

    assert generate_specs.main() == 0
    assert generated == {fork: tmp_path / fork for fork in generate_specs.spec_builders}
