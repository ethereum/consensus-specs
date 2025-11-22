"""
Pydantic models for trace operations.

This module defines the data models for trace operations used in the
spec trace recording system.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

__all__ = [
    "BaseOperation",
    "LoadStateOp",
    "SpecCallOp",
    "AssertStateOp",
    "TraceConfig",
]


class BaseOperation(BaseModel):
    """Base class for all trace operations."""

    model_config = ConfigDict(extra="forbid")
    op: str


class LoadStateOp(BaseOperation):
    """
    Operation to load a state from disk.

    Attributes:
        op: Operation type identifier ('load_state')
        state_root: Hex-encoded hash tree root of the state
    """

    op: str = "load_state"
    state_root: str


class SpecCallOp(BaseOperation):
    """
    Operation representing a spec method call.

    Attributes:
        op: Operation type identifier ('spec_call')
        method: Name of the spec method being called
        input: Optional list of input parameters (non-state arguments)
               Each element can be a dict {param_name: value} or a plain value
        assert_output: Optional expected output value for validation
    """

    op: str = "spec_call"
    method: str
    input: list[dict[str, object] | object] | None = None
    assert_output: object | None = None


class AssertStateOp(BaseOperation):
    """
    Operation to assert the final state.

    Attributes:
        op: Operation type identifier ('assert_state')
        state_root: Hex-encoded hash tree root of the expected state
    """

    op: str = "assert_state"
    state_root: str


# Type alias for trace operations
TraceOperation = LoadStateOp | SpecCallOp | AssertStateOp


class TraceConfig(BaseModel):
    """
    Root configuration for a trace test vector.

    Attributes:
        default_fork: The fork name (e.g., 'phase0', 'altair', 'bellatrix', 'fulu')
        trace: Ordered list of trace operations
    """

    default_fork: str
    trace: list[TraceOperation]

    model_config = ConfigDict(arbitrary_types_allowed=True)
