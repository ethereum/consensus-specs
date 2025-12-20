"""
Trace Models
------------
Pydantic models defining the schema for the generated test vector artifacts:
- TraceConfig
- TraceStep: LoadStateOp | SpecCallOp | AssertStateOp
"""

from abc import ABC
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, PrivateAttr

from .typing import SERIALIZED_ARGS, SERIALIZED_KWARGS


def simple_sanitize_data(value: SERIALIZED_ARGS) -> SERIALIZED_ARGS:
    # convert raw bytes to 0x-prefixed hex
    if isinstance(value, bytes):
        return f"0x{value.hex()}"
    # recursively clean lists
    if isinstance(value, list):
        # typing hint: nesting never added
        return [simple_sanitize_data(x) for x in value]  # type: ignore[return-value]
    return value


class TraceStepModel(BaseModel, ABC):
    """
    A single abstract step in the execution trace.
    """

    model_config = ConfigDict(extra="forbid")


class StateOp(TraceStepModel):
    """
    Abstract base class for operations involving a state root.
    """

    state_root: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_serializer("state_root", mode="plain", when_used="always")
    @classmethod
    def sanitize_data(cls, v: str) -> str:
        # add ssz_snappy suffix (dumper handles the actual compression)
        return f"{v}.ssz_snappy"


class LoadStateOp(StateOp):
    """
    Load state step in the execution trace.

    Used when a previously-unseen state is used in a spec call.
    State root is recorded as 'state_root'.
    """

    op: Literal["load_state"] = Field(default="load_state")


class AssertStateOp(StateOp):
    """
    Assert state step in the execution trace.

    Auto-added at the end of the trace with the last known state root.
    State root is recorded as 'state_root'.
    """

    op: Literal["assert_state"] = Field(default="assert_state")


class SpecCallOp(TraceStepModel):
    """
    Spec call step in the execution trace.

    Spec method called is recorded as 'method'.
    """

    op: Literal["spec_call"] = Field(default="spec_call")
    method: str = Field(description="The spec function name, e.g., 'process_slots'")
    input: SERIALIZED_KWARGS = Field(
        default_factory=dict, description="Arguments passed to the function"
    )
    assert_output: SERIALIZED_ARGS = Field(
        default=None, description="The return value (ssz hash or primitive)"
    )

    @field_serializer("assert_output", mode="plain", when_used="json")
    @classmethod
    def sanitize_args(cls, value: SERIALIZED_ARGS) -> SERIALIZED_ARGS:
        return simple_sanitize_data(value)

    @field_serializer("input", mode="plain", when_used="json")
    @classmethod
    def sanitize_kwargs(cls, value: SERIALIZED_KWARGS) -> SERIALIZED_KWARGS:
        return {k: simple_sanitize_data(val) for k, val in value.items()}


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

    @property
    def artifacts(self) -> dict[str, bytes]:
        """The registered artifacts (state blobs, SSZ objects, etc)."""
        return self._artifacts
