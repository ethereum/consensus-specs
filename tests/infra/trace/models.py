"""
Trace Models
------------
Pydantic models defining the schema for the generated test vector artifacts:
- Trace
- TraceStep
- Context
"""

import os
from typing import Any, cast, TypeAlias

import yaml
from pydantic import BaseModel, Field, field_validator, PrivateAttr
from pydantic.types import constr
from remerkleable.complex import Container

from eth2spec.utils.ssz.ssz_impl import serialize as ssz_serialize

# --- Configuration ---

# Classes that should be treated as tracked SSZ objects in the trace.
# Maps class name -> context collection name.
CLASS_NAME_MAP: dict[str, str] = {
    "BeaconState": "states",
    "BeaconBlock": "blocks",
    "Attestation": "attestations",
}

# Non-SSZ fixtures that should be captured by name.
NON_SSZ_FIXTURES: set[str] = {"store"}

# Regex to match a context variable reference, e.g., "$context.states.initial"
CONTEXT_VAR_REGEX = r"^\$context\.\w+\.\w+$"
ContextVar: TypeAlias = constr(pattern=CONTEXT_VAR_REGEX)


class ContextObjectsModel(BaseModel):
    """
    Defines the SSZ objects (artifacts) loaded in the 'context' block.
    Maps logical names (e.g., 'v0') to filenames (e.g., 'state_root.ssz').
    """

    states: dict[str, str] = Field(
        default_factory=dict, description="Map of state names to SSZ filenames"
    )
    blocks: dict[str, str] = Field(
        default_factory=dict, description="Map of block names to SSZ filenames"
    )
    attestations: dict[str, str] = Field(
        default_factory=dict, description="Map of attestation names to SSZ filenames"
    )


class ContextModel(BaseModel):
    """
    The 'context' block of the trace file.
    Contains static fixtures, parameters, and references to binary objects.
    """

    fixtures: list[str] = Field(
        default_factory=list, description="List of non-SSZ fixtures to inject (e.g. 'store')"
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Simple test setup parameters (e.g. validator_count)"
    )
    objects: ContextObjectsModel = Field(default_factory=ContextObjectsModel)


def _clean_value(v: Any) -> Any:
    """
    Recursively sanitizes values for the trace:
    - Bytes -> Hex string (raw)
    - Int subclasses -> int
    - Lists/Dicts -> Recursive clean
    """
    if isinstance(v, bytes):
        return f"0x{v.hex()}"
    if isinstance(v, int):
        return int(v)
    if isinstance(v, list):
        return [_clean_value(x) for x in v]
    if isinstance(v, dict):
        return {k: _clean_value(val) for k, val in v.items()}
    return v


class TraceStepModel(BaseModel):
    """
    A single step in the execution trace.
    Represents a function call ('op'), its inputs, and its outcome.
    """

    op: str = Field(..., description="The spec function name, e.g., 'process_slots'")
    params: dict[str, Any] = Field(
        default_factory=dict, description="Arguments passed to the function"
    )
    result: Any | None = Field(
        None, description="The return value (context var reference or primitive)"
    )
    error: dict[str, str] | None = Field(
        None, description="Error details if the operation raised an exception"
    )

    @field_validator("params", "result", mode="before")
    @classmethod
    def sanitize_data(cls, v: Any) -> Any:
        return _clean_value(v)


class TraceModel(BaseModel):
    """
    The root schema for the trace file.
    Contains metadata, context, and the execution trace.
    """

    metadata: dict[str, Any] = Field(..., description="Test run metadata (fork, preset, etc.)")
    context: ContextModel = Field(default_factory=ContextModel)
    trace: list[TraceStepModel] = Field(default_factory=list)

    # Private registry state (not serialized directly, used to build the trace)
    _hash_to_name: dict[int, str] = PrivateAttr(default_factory=dict)
    _name_to_obj: dict[str, Any] = PrivateAttr(default_factory=dict)
    _artifacts: dict[str, Container] = PrivateAttr(default_factory=dict)

    def register_object(self, obj: Any) -> ContextVar | None:
        """
        Registers an object in the trace context.
        - If it's an SSZ object (Container), it gets a hash-based name.
        - If it's a primitive, it returns None (passed through).
        """
        if obj is None:
            return None

        if not isinstance(obj, Container):
            return None

        class_name = type(obj).__name__
        if class_name not in CLASS_NAME_MAP:
            return None  # Unknown object type

        # Generate Name (Content-Addressed)
        obj_type = CLASS_NAME_MAP[class_name]
        root_hex = obj.hash_tree_root().hex()
        context_name = cast(ContextVar, f"$context.{obj_type}.{root_hex}")
        filename = f"{obj_type}_{root_hex}.ssz"

        # Update Registry
        self._hash_to_name[root_hex] = context_name
        self._name_to_obj[context_name] = obj
        self._artifacts[filename] = obj

        # Update the public ContextObjectsModel (for output)
        if hasattr(self.context.objects, obj_type):
            getattr(self.context.objects, obj_type)[root_hex] = filename

        return context_name

    def dump_to_dir(self, output_dir: str, config: dict[str, Any] = None) -> None:
        """
        Writes the trace and all artifacts to the specified directory.
        """
        os.makedirs(output_dir, exist_ok=True)

        # 1. Write SSZ artifacts
        for filename, obj in self._artifacts.items():
            self._write_ssz(os.path.join(output_dir, filename), obj)

        # 2. Write YAML files
        self._write_yaml(os.path.join(output_dir, "trace.yaml"), self.model_dump(exclude_none=True))

        print(f"[Trace Recorder] Saved artifacts to {output_dir}")

    def _write_ssz(self, path: str, obj: Any) -> None:
        """Helper to write an SSZ object to disk."""
        try:
            with open(path, "wb") as f:
                f.write(ssz_serialize(obj))
        except Exception as e:
            print(f"ERROR: Failed to write SSZ artifact {path}: {e}")

    def _write_yaml(self, path: str, data: Any) -> None:
        """Helper to write data as YAML to disk."""
        try:
            with open(path, "w") as f:
                yaml.dump(data, f, sort_keys=False, default_flow_style=False)
        except Exception as e:
            print(f"ERROR: Failed to write YAML {path}: {e}")


class ConfigModel(BaseModel):
    """
    Schema for configuration constants
    """

    config: dict[str, Any] = Field(..., description="Dictionary of config constants")


class MetaModel(BaseModel):
    """
    Schema for metadata
    """

    meta: dict[str, Any] = Field(..., description="Dictionary of metadata key/value pairs")
