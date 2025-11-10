from pathlib import Path
from typing import NamedTuple


class ProtocolDefinition(NamedTuple):
    # just function definitions currently. May expand with configuration vars in future.
    functions: dict[str, str]


class VariableDefinition(NamedTuple):
    type_name: str | None
    value: str
    comment: str | None  # e.g. "noqa: E501"
    type_hint: str | None  # e.g., "Final"


class SpecObject(NamedTuple):
    functions: dict[str, str]
    protocols: dict[str, ProtocolDefinition]
    custom_types: dict[str, str]
    constant_vars: dict[str, VariableDefinition]
    preset_dep_constant_vars: dict[str, VariableDefinition]
    preset_vars: dict[str, VariableDefinition]
    config_vars: dict[str, VariableDefinition]
    ssz_dep_constants: dict[str, str]  # the constants that depend on ssz_objects
    func_dep_presets: dict[str, str]  # the constants that depend on functions
    ssz_objects: dict[str, str]
    dataclasses: dict[str, str]


class BuildTarget(NamedTuple):
    name: str
    preset_paths: list[Path]
    config_path: Path
