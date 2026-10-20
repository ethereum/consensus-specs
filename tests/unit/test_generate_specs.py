import subprocess
import sys
from pathlib import Path

import pytest

from pysetup.generate_specs import generate_fork_specs, parse_build_targets


@pytest.mark.parametrize(
    ("target_names", "default_target"),
    [
        (("minimal",), "minimal"),
        (("mainnet",), "mainnet"),
        (("minimal", "mainnet"), "mainnet"),
        (("mainnet", "minimal"), "mainnet"),
        (("custom", "minimal"), "custom"),
    ],
)
def test_generate_fork_specs_default_import(tmp_path, monkeypatch, target_names, default_target):
    monkeypatch.chdir(Path(__file__).resolve().parents[2])
    build_targets = parse_build_targets(
        " ".join(
            f"{name}:presets/{'mainnet' if name == 'mainnet' else 'minimal'}:"
            f"configs/{'mainnet' if name == 'mainnet' else 'minimal'}.yaml"
            for name in target_names
        )
    )
    out_dir = tmp_path / "generated_specs"

    generate_fork_specs("phase0", out_dir, build_targets)

    assert {path.name for path in out_dir.iterdir()} == {
        "__init__.py",
        *(f"{name}.py" for name in target_names),
    }
    assert (out_dir / "__init__.py").read_text() == (
        f"from . import {default_target} as spec  # noqa:F401\n"
    )
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from importlib import import_module; "
                "import generated_specs; "
                f"assert generated_specs.spec is import_module('generated_specs.{default_target}')"
            ),
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )


def test_generate_fork_specs_requires_build_targets(tmp_path):
    out_dir = tmp_path / "generated_specs"

    with pytest.raises(ValueError, match="At least one build target is required"):
        generate_fork_specs("phase0", out_dir, [])

    assert not out_dir.exists()
