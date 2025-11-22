"""
Spec Trace - Automatic test vector generation for Ethereum consensus specs.

This package provides a transparent proxy system that automatically records
spec method calls and generates test vectors without requiring manual yield
statements.

See: https://github.com/ethereum/consensus-specs/issues/4603

Example:
    @spec_trace()
    def test_example(spec, state):
        spec.process_slots(state, 10)
        # Trace is automatically generated!
"""

from .decorators import create_spec_proxy, spec_trace
from .models import (
    AssertStateOp,
    BaseOperation,
    LoadStateOp,
    SpecCallOp,
    TraceConfig,
)
from .proxy_core import SpecProxy
from .ssz_store import SSZObjectStore
from .state_tracker import StateTracker

__all__ = [
    # Decorators (main API)
    "spec_trace",
    "create_spec_proxy",
    # Models
    "BaseOperation",
    "LoadStateOp",
    "SpecCallOp",
    "AssertStateOp",
    "TraceConfig",
    # Core classes
    "SpecProxy",
    "SSZObjectStore",
    "StateTracker",
]

__version__ = "1.0.0"
