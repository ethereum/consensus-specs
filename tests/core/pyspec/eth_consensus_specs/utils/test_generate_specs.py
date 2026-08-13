import importlib.util
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType

import pytest

from pysetup import generate_specs
from pysetup.typing import BuildTarget


@pytest.fixture
def source_file(tmp_path: Path) -> Path:
    path = tmp_path / "source.md"
    path.write_text("stub")
    return path


@pytest.fixture
def stub_spec_builder(monkeypatch: pytest.MonkeyPatch) -> None:
    def build_spec(
        fork: str,
        preset_name: str,
        source_files: list[Path],
        preset_files: list[Path],
        config_file: Path,
    ) -> str:
        return f"PRESET_NAME = {preset_name!r}\n"

    monkeypatch.setattr(generate_specs, "build_spec", build_spec)


def build_target(name: str, tmp_path: Path) -> BuildTarget:
    return BuildTarget(name, [], tmp_path / "config.yaml")


@contextmanager
def import_generated_package(package_dir: Path) -> Iterator[ModuleType]:
    package_name = "generated_spec_package"
    module_spec = importlib.util.spec_from_file_location(
        package_name,
        package_dir / "__init__.py",
        submodule_search_locations=[str(package_dir)],
    )
    assert module_spec is not None
    assert module_spec.loader is not None

    module = importlib.util.module_from_spec(module_spec)
    sys.modules[package_name] = module
    try:
        module_spec.loader.exec_module(module)
        yield module
    finally:
        for module_name in tuple(sys.modules):
            if module_name == package_name or module_name.startswith(f"{package_name}."):
                del sys.modules[module_name]


def test_generate_minimal_only_package(
    tmp_path: Path,
    source_file: Path,
    stub_spec_builder: None,
) -> None:
    package_dir = tmp_path / "generated"

    generate_specs.generate_fork_specs(
        "phase0",
        package_dir,
        [build_target("minimal", tmp_path)],
        [source_file],
    )

    with import_generated_package(package_dir) as package:
        assert package.spec.PRESET_NAME == "minimal"


def test_generate_minimal_only_package_ignores_stale_mainnet(
    tmp_path: Path,
    source_file: Path,
    stub_spec_builder: None,
) -> None:
    package_dir = tmp_path / "generated"
    package_dir.mkdir()
    (package_dir / "mainnet.py").write_text("PRESET_NAME = 'stale-mainnet'\n")

    generate_specs.generate_fork_specs(
        "phase0",
        package_dir,
        [build_target("minimal", tmp_path)],
        [source_file],
    )

    with import_generated_package(package_dir) as package:
        assert package.spec.PRESET_NAME == "minimal"


def test_generate_package_keeps_mainnet_as_default(
    tmp_path: Path,
    source_file: Path,
    stub_spec_builder: None,
) -> None:
    package_dir = tmp_path / "generated"

    generate_specs.generate_fork_specs(
        "phase0",
        package_dir,
        [build_target("minimal", tmp_path), build_target("mainnet", tmp_path)],
        [source_file],
    )

    with import_generated_package(package_dir) as package:
        assert package.spec.PRESET_NAME == "mainnet"


def test_generate_package_rejects_empty_build_targets(
    tmp_path: Path,
    source_file: Path,
) -> None:
    with pytest.raises(ValueError, match="at least one build target is required"):
        generate_specs.generate_fork_specs("phase0", tmp_path / "generated", [], [source_file])


def test_parse_build_targets_accepts_identifier_with_underscore(tmp_path: Path) -> None:
    preset_dir = tmp_path / "preset"
    preset_dir.mkdir()
    (preset_dir / "preset.yaml").write_text("PRESET: 1\n")
    config_path = tmp_path / "config.yaml"
    config_path.write_text("CONFIG: 1\n")

    targets = generate_specs.parse_build_targets(f"foo_bar:{preset_dir}:{config_path}")

    assert targets[0].name == "foo_bar"


@pytest.mark.parametrize("name", ["123", "class"])
def test_parse_build_targets_rejects_invalid_module_identifier(
    name: str,
    tmp_path: Path,
) -> None:
    preset_dir = tmp_path / "preset"
    preset_dir.mkdir()
    (preset_dir / "preset.yaml").write_text("PRESET: 1\n")
    config_path = tmp_path / "config.yaml"
    config_path.write_text("CONFIG: 1\n")

    with pytest.raises(ValueError, match="must be a valid Python identifier"):
        generate_specs.parse_build_targets(f"{name}:{preset_dir}:{config_path}")
