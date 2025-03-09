from pathlib import Path
from typing import Dict, NamedTuple, Optional, List


class ProtocolDefinition(NamedTuple):
    # just function definitions currently. May expand with configuration vars in future.
    functions: Dict[str, str]


class VariableDefinition(NamedTuple):
    type_name: Optional[str]
    value: str
    comment: Optional[str]  # e.g. "noqa: E501"
    type_hint: Optional[str]  # e.g., "Final"


class SpecObject(NamedTuple):
    functions: Dict[str, str]
    protocols: Dict[str, ProtocolDefinition]
    custom_types: Dict[str, str]
    preset_dep_custom_types: Dict[str, str]  # the types that depend on presets
    constant_vars: Dict[str, VariableDefinition]
    preset_dep_constant_vars: Dict[str, VariableDefinition]
    preset_vars: Dict[str, VariableDefinition]
    config_vars: Dict[str, VariableDefinition]
    ssz_dep_constants: Dict[str, str]  # the constants that depend on ssz_objects
    func_dep_presets: Dict[str, str]  # the constants that depend on functions
    ssz_objects: Dict[str, str]
    dataclasses: Dict[str, str]


class BuildTarget(NamedTuple):
    name: str
    preset_paths: List[Path]
    config_path: Path
