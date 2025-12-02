"""
Trace Models
------------
Pydantic models defining the schema for the generated test vector artifacts:
- TraceConfig
- TraceStep: LoadStateOp | SpecCallOp | AssertStateOp
"""

from abc import ABC
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, PrivateAttr


class TraceStepModel(BaseModel, ABC):
    """
    A single abstract step in the execution trace.
    """

    model_config = ConfigDict(extra="forbid")
    op: str


class LoadStateOp(TraceStepModel):
    """
    Load state step in the execution trace.

    Used when a previously-unseen state is used in a spec call.
    State root is recorded as 'state_root'.
    """

    op: Literal["load_state"] = Field(default="load_state")
    state_root: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_serializer("state_root", mode="plain", when_used="always")
    @classmethod
    def sanitize_data(cls, v: str) -> str:
        # add ssz_snappy suffix (dumper handles the actual compression)
        return f"{v}.ssz_snappy"


class AssertStateOp(TraceStepModel):
    """
    Assert state step in the execution trace.

    Auto-added at the end of the trace with the last known state root.
    State root is recorded as 'state_root'.
    """

    op: Literal["assert_state"] = Field(default="assert_state")
    state_root: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_serializer("state_root", mode="plain", when_used="always")
    @classmethod
    def sanitize_data(cls, v: str) -> str:
        # add ssz_snappy suffix (dumper handles the actual compression)
        return f"{v}.ssz_snappy"


class SpecCallOp(TraceStepModel):
    """
    Spec call step in the execution trace.

    Spec method called is recorded as 'method'.
    """

    op: Literal["spec_call"] = Field(default="spec_call")
    method: str = Field(description="The spec function name, e.g., 'process_slots'")
    input: dict[str, Any | str | None] = Field(
        default_factory=dict, description="Arguments passed to the function"
    )
    assert_output: Any | str | None = Field(
        default=None, description="The return value (ssz hash or primitive)"
    )

    # when_used=json so that we can build pythonic-style yaml with types as well
    @field_serializer("input", "assert_output", mode="plain", when_used="json")
    @classmethod
    def sanitize_data(cls, v: Any) -> Any:
        # convert raw bytes to 0x-prefixed hex
        if isinstance(v, bytes):
            return f"0x{v.hex()}"
        # coerce primitive types into their raw form
        # (pre-processor just passes them through without coercing)
        if isinstance(v, str):
            return str(v)
        if isinstance(v, int):
            return int(v)
        # recursively clean simple structures
        if isinstance(v, tuple):
            return tuple(cls.sanitize_data(x) for x in v)
        if isinstance(v, list):
            return [cls.sanitize_data(x) for x in v]
        if isinstance(v, dict):
            return {k: cls.sanitize_data(val) for k, val in v.items()}
        return v


class TraceConfig(BaseModel):
    """
    The root schema for the trace file.
    Contains metadata, context, and the execution trace.
    """

    default_fork: str = Field(default="")
    trace: list[Annotated[AssertStateOp | LoadStateOp | SpecCallOp, Field(discriminator="op")]] = (
        Field(default_factory=list)
    )

    # Private registry state (not serialized directly, used to build the trace)
    _artifacts: dict[str, bytes] = PrivateAttr(default_factory=dict)
