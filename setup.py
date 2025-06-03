import copy
import logging
import os
import string
import warnings
from collections import OrderedDict
from collections.abc import Sequence
from distutils import dir_util
from distutils.util import convert_path
from functools import cache
from pathlib import Path
from typing import cast

from ruamel.yaml import YAML
from setuptools import Command, find_packages, setup
from setuptools.command.build_py import build_py

from pysetup.constants import (
    PHASE0,
)
from pysetup.helpers import (
    combine_spec_objects,
    dependency_order_class_objects,
    objects_to_spec,
    parse_config_vars,
)
from pysetup.md_doc_paths import get_md_doc_paths
from pysetup.md_to_spec import MarkdownToSpec
from pysetup.spec_builders import spec_builders
from pysetup.typing import (
    BuildTarget,
    SpecObject,
)

# Ignore '1.5.0-alpha.*' to '1.5.0a*' messages.
warnings.filterwarnings("ignore", message="Normalizing .* to .*")


# Ignore 'running' and 'creating' messages
class PyspecFilter(logging.Filter):
    def filter(self, record):
        return not record.getMessage().startswith(("running ", "creating "))


logging.getLogger().addFilter(PyspecFilter())


def get_spec(
    file_name: Path,
    preset: dict[str, str],
    config: dict[str, str | list[dict[str, str]]],
    preset_name: str,
) -> SpecObject:
    return MarkdownToSpec(file_name, preset, config, preset_name).run()


@cache
def load_preset(preset_files: Sequence[Path]) -> dict[str, str]:
    """
    Loads a directory of preset files, merges the result into one preset.
    """
    preset = {}
    for fork_file in preset_files:
        yaml = YAML(typ="base")
        fork_preset: dict = yaml.load(fork_file)
        if fork_preset is None:  # for empty YAML files
            continue
        if not set(fork_preset.keys()).isdisjoint(preset.keys()):
            duplicates = set(fork_preset.keys()).intersection(set(preset.keys()))
            raise Exception(f"duplicate config var(s) in preset files: {', '.join(duplicates)}")
        preset.update(fork_preset)
    assert preset != {}
    return cast(dict[str, str], parse_config_vars(preset))


@cache
def load_config(config_path: Path) -> dict[str, str | list[dict[str, str]]]:
    """
    Loads the given configuration file.
    """
    yaml = YAML(typ="base")
    config_data = yaml.load(config_path)
    return parse_config_vars(config_data)


def build_spec(
    fork: str,
    preset_name: str,
    source_files: Sequence[Path],
    preset_files: Sequence[Path],
    config_file: Path,
) -> str:
    preset = load_preset(tuple(preset_files))
    config = load_config(config_file)
    all_specs = [get_spec(spec, preset, config, preset_name) for spec in source_files]

    spec_object = all_specs[0]
    for value in all_specs[1:]:
        spec_object = combine_spec_objects(spec_object, value)

    class_objects = {**spec_object.ssz_objects, **spec_object.dataclasses}

    # Ensure it's ordered after multiple forks
    new_objects = {}
    while OrderedDict(new_objects) != OrderedDict(class_objects):
        new_objects = copy.deepcopy(class_objects)
        dependency_order_class_objects(
            class_objects,
            spec_object.custom_types | spec_object.preset_dep_custom_types,
        )

    return objects_to_spec(preset_name, spec_object, fork, class_objects)


class PySpecCommand(Command):
    """Convert spec markdown files to a spec python file"""

    description = "Convert spec markdown files to a spec python file"

    spec_fork: str
    md_doc_paths: str
    parsed_md_doc_paths: list[str]
    build_targets: str
    parsed_build_targets: list[BuildTarget]
    out_dir: str

    # The format is (long option, short option, description).
    user_options = [
        ("spec-fork=", None, "Spec fork to tag build with. Used to select md-docs defaults."),
        ("md-doc-paths=", None, "List of paths of markdown files to build spec with"),
        (
            "build-targets=",
            None,
            "Names, directory paths of compile-time presets, and default config paths.",
        ),
        ("out-dir=", None, "Output directory to write spec package to"),
    ]

    def initialize_options(self):
        """Set default values for options."""
        # Each user option must be listed here with their default value.
        self.spec_fork = PHASE0
        self.md_doc_paths = ""
        self.out_dir = "pyspec_output"
        self.build_targets = """
                minimal:presets/minimal:configs/minimal.yaml
                mainnet:presets/mainnet:configs/mainnet.yaml
        """

    def finalize_options(self):
        """Post-process options."""
        if len(self.md_doc_paths) == 0:
            self.md_doc_paths = get_md_doc_paths(self.spec_fork)
            if len(self.md_doc_paths) == 0:
                raise Exception(
                    f"No markdown files specified, and spec fork {self.spec_fork!r} is unknown"
                )

        self.parsed_md_doc_paths = self.md_doc_paths.split()

        for filename in self.parsed_md_doc_paths:
            if not os.path.exists(filename):
                raise Exception(f"Pyspec markdown input file {filename!r} does not exist")

        self.parsed_build_targets = []
        for target in self.build_targets.split():
            target = target.strip()
            data = target.split(":")
            if len(data) != 3:
                raise Exception(
                    f"invalid target, expected 'name:preset_dir:config_file' format, but got: {target}"
                )
            name, preset_dir_path, config_path = data
            if any((c not in string.digits + string.ascii_letters) for c in name):
                raise Exception(f"invalid target name: {name!r}")
            if not os.path.exists(preset_dir_path):
                raise Exception(f"Preset dir {preset_dir_path!r} does not exist")
            _, _, preset_file_names = next(os.walk(preset_dir_path))
            preset_paths = [(Path(preset_dir_path) / name) for name in preset_file_names]

            if not os.path.exists(config_path):
                raise Exception(f"Config file {config_path!r} does not exist")
            self.parsed_build_targets.append(BuildTarget(name, preset_paths, Path(config_path)))

    def run(self):
        if not self.dry_run:
            dir_util.mkpath(self.out_dir)

        print(f"Building pyspec: {self.spec_fork}")
        for name, preset_paths, config_path in self.parsed_build_targets:
            spec_str = build_spec(
                spec_builders[self.spec_fork].fork,
                name,
                self.parsed_md_doc_paths,
                preset_paths,
                config_path,
            )
            if self.dry_run:
                self.announce(
                    "dry run successfully prepared contents for spec."
                    f' out dir: "{self.out_dir}", spec fork: "{self.spec_fork}", build target: "{name}"'
                )
                self.debug_print(spec_str)
            else:
                with open(os.path.join(self.out_dir, name + ".py"), "w") as out:
                    out.write(spec_str)

        if not self.dry_run:
            with open(os.path.join(self.out_dir, "__init__.py"), "w") as out:
                # `mainnet` is the default spec.
                out.write("from . import mainnet as spec  # noqa:F401\n")


class BuildPyCommand(build_py):
    """Customize the build command to run the spec-builder on setup.py build"""

    def initialize_options(self):
        super().initialize_options()

    def run_pyspec_cmd(self, spec_fork: str, **opts):
        cmd_obj: PySpecCommand = self.distribution.reinitialize_command("pyspec")
        cmd_obj.spec_fork = spec_fork
        cmd_obj.out_dir = os.path.join(self.build_lib, "eth2spec", spec_fork)
        for k, v in opts.items():
            setattr(cmd_obj, k, v)
        self.run_command("pyspec")

    def run(self):
        for spec_fork in spec_builders:
            self.run_pyspec_cmd(spec_fork=spec_fork)

        super().run()


class PyspecDevCommand(Command):
    """Build the markdown files in-place to their source location for testing."""

    description = "Build the markdown files in-place to their source location for testing."
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run_pyspec_cmd(self, spec_fork: str, **opts):
        cmd_obj: PySpecCommand = self.distribution.reinitialize_command("pyspec")
        cmd_obj.spec_fork = spec_fork
        eth2spec_dir = convert_path(self.distribution.package_dir["eth2spec"])
        cmd_obj.out_dir = os.path.join(eth2spec_dir, spec_fork)
        for k, v in opts.items():
            setattr(cmd_obj, k, v)
        self.run_command("pyspec")

    def run(self):
        for spec_fork in spec_builders:
            self.run_pyspec_cmd(spec_fork=spec_fork)


commands = {
    "pyspec": PySpecCommand,
    "build_py": BuildPyCommand,
    "pyspecdev": PyspecDevCommand,
}

with open("README.md", encoding="utf8") as f:
    readme = f.read()

# How to use "VERSION.txt" file:
# - dev branch contains "X.Y.Z.dev", where "X.Y.Z" is the target version to release dev into.
#    -> Changed as part of 'master' backport to 'dev'
# - master branch contains "X.Y.Z", where "X.Y.Z" is the current version.
#    -> Changed as part of 'dev' release (or other branch) into 'master'
#    -> In case of a commit on master without git tag, target the next version
#        with ".postN" (release candidate, numbered) suffixed.
# See https://www.python.org/dev/peps/pep-0440/#public-version-identifiers
with open(os.path.join("tests", "core", "pyspec", "eth2spec", "VERSION.txt")) as f:
    spec_version = f.read().strip()

setup(
    version=spec_version,
    long_description=readme,
    long_description_content_type="text/markdown",
    url="https://github.com/ethereum/consensus-specs",
    include_package_data=False,
    package_data={
        "configs": ["*.yaml"],
        "eth2spec": ["VERSION.txt"],
        "presets": ["**/*.yaml", "**/*.json"],
        "specs": ["**/*.md"],
        "sync": ["optimistic.md"],
    },
    package_dir={
        "configs": "configs",
        "eth2spec": "tests/core/pyspec/eth2spec",
        "presets": "presets",
        "specs": "specs",
        "sync": "sync",
    },
    packages=find_packages(where="tests/core/pyspec")
    + ["configs", "presets", "specs", "presets", "sync"],
    py_modules=["eth2spec"],
    cmdclass=commands,
)
