"""
Trace Models
------------
Pydantic models defining the schema for the generated test vector artifacts:
- TraceConfig
- TraceStep: LoadStateOp | SpecCallOp | AssertStateOp
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, PrivateAttr


class TraceStepModel(BaseModel):  # TODO: add ABC or whatever required for abstract class
    """
    A single abstract step in the execution trace.
    """

    # FIXME: I'm not sure this works well with SpecCallOp
    model_config = ConfigDict(extra="forbid")
    op: str


class LoadStateOp(TraceStepModel):
    """
    Load state step in the execution trace.

    Used when a previously-unseen state is used in spec all.
    State root is recorded as 'state_root'.
    """

    op: Literal["load_state"] = Field(default="load_state")
    state_root: str = Field()


class AssertStateOp(TraceStepModel):
    """
    Assert state step in the execution trace.

    Auto-added at the end of the trace with the last known state root.
    State root is recorded as 'state_root'.
    """

    op: Literal["assert_state"] = Field(default="assert_state")
    state_root: str = Field()


class SpecCallOp(TraceStepModel):
    """
    Spec call step in the execution trace.

    Spec method called is recorded as 'method'.
    """

    op: Literal["spec_call"] = Field(default="spec_call")
    method: str = Field(description="The spec function name, e.g., 'process_slots'")
    input: dict[str, Any] = Field(
        default_factory=dict, description="Arguments passed to the function"
    )
    assert_output: Any | str | None = Field(
        default=None, description="The return value (ssz hash or primitive)"
    )

    @field_validator("input", "assert_output", mode="before")
    @classmethod
    def sanitize_data(cls, v: Any) -> Any:
        # FIXME: there might be a better place for this in the serializer not validator
        # convert raw bytes to hex
        if isinstance(v, bytes):
            return f"0x{v.hex()}"
        # coerce primitive types into their raw form
        if isinstance(v, str):
            return str(v)
        if isinstance(v, int):
            return int(v)
        # recursively clean simple structures
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
