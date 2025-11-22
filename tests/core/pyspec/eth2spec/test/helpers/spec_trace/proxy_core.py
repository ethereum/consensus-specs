"""
Core proxy implementation for spec method interception.

This module provides the main SpecProxy class that transparently wraps
spec modules and records all method calls.
"""

from __future__ import annotations

from functools import wraps
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from eth2spec.utils.ssz.ssz_typing import View

from .models import BaseOperation, SpecCallOp, TraceConfig
from .ssz_store import SSZObjectStore
from .state_tracker import StateTracker

__all__ = ["SpecProxy"]


class SpecProxy:
    """
    Transparent proxy that wraps a spec module and records all method calls.

    This proxy intercepts all spec function calls and automatically:
    - Records the call with inputs and outputs
    - Handles SSZ object storage via content-addressed store
    - Tracks state changes through StateTracker
    - Generates load_state/assert_state operations

    Attributes:
        _spec: The wrapped spec module
        _fork_name: Name of the fork (e.g., 'phase0', 'altair', 'fulu')
        _trace: List of recorded trace operations
        _store: SSZ object store for persistence
        _state_tracker: State change tracker
        _state_var_name: Name of the state variable (default: 'state')
        _recording: Flag to enable/disable recording
        _state_mutating_methods: Set of method names that modify state
    """

    def __init__(
        self, spec_module: Any, fork_name: str, output_dir: Path, state_var_name: str = "state"
    ) -> None:
        """
        Initialize the spec proxy.

        Args:
            spec_module: The spec module to wrap
            fork_name: Name of the fork
            output_dir: Directory for storing trace files and SSZ objects
            state_var_name: Name of the state variable (default: 'state')
        """
        self._spec = spec_module
        self._fork_name = fork_name
        self._trace: list[BaseOperation] = []
        self._store = SSZObjectStore(output_dir)
        self._state_tracker = StateTracker(self._store)
        self._state_var_name = state_var_name
        self._recording = True

        # Methods that modify state (extend as needed)
        self._state_mutating_methods = {
            "process_slot",
            "process_slots",
            "process_epoch",
            "process_block",
            "process_execution_payload",
            "process_attestation",
            "process_deposit",
            "process_voluntary_exit",
            "process_sync_aggregate",
        }

    def __getattr__(self, name: str) -> Any:
        """
        Intercept attribute access to wrap spec functions.

        Args:
            name: Attribute name being accessed

        Returns:
            The wrapped function (if callable) or the attribute itself
        """
        attr = getattr(self._spec, name)

        # If it's not callable, return as-is
        if not callable(attr):
            return attr

        # If it's a callable, wrap it to record calls
        @wraps(attr)
        def wrapper(*args, **kwargs):
            if not self._recording:
                return attr(*args, **kwargs)

            # Check if first arg is state
            has_state_arg = len(args) > 0 and isinstance(args[0], View)
            state_arg = args[0] if has_state_arg else None

            # Track state input
            if has_state_arg and state_arg is not None:
                self._state_tracker.track_state_input(state_arg, self._trace)

            # Call the actual spec function
            result = attr(*args, **kwargs)

            # Record the call
            self._record_call(name, args, kwargs, result, state_arg)

            # Track state output if method mutates state
            if has_state_arg and name in self._state_mutating_methods:
                self._state_tracker.track_state_output(args[0])

            return result

        return wrapper

    def _record_call(
        self, method: str, args: tuple, kwargs: dict, result: Any, state_arg: View | None
    ) -> None:
        """
        Record a spec method call to the trace.

        Args:
            method: Name of the method called
            args: Positional arguments passed to the method
            kwargs: Keyword arguments passed to the method
            result: Return value from the method
            state_arg: The state argument (if present)
        """
        # Prepare input arguments
        input_data = []

        # Skip state argument (it's tracked separately via state_root)
        # If state_arg is not None, it means args[0] is the state, so skip it
        non_state_args = args[1:] if state_arg is not None else args

        for arg in non_state_args:
            serialized = self._serialize_value(arg)
            # Skip any accidentally serialized state objects (as strings)
            if not isinstance(serialized, str) or not serialized.startswith("<"):
                input_data.append(serialized)

        for key, value in kwargs.items():
            input_data.append({key: self._serialize_value(value)})

        # Prepare output
        output_data = self._serialize_value(result) if result is not None else None

        # Create operation
        op = SpecCallOp(
            method=method, input=input_data if input_data else None, assert_output=output_data
        )

        self._trace.append(op)

    def _serialize_value(self, value: Any) -> Any:
        """
        Serialize a value for storage in trace.

        SSZ objects are stored separately and referenced by hash.

        Args:
            value: The value to serialize

        Returns:
            Serialized representation of the value
        """
        if isinstance(value, View):
            # Store SSZ object and return reference
            return self._store.get_reference(value)

        # Handle basic types
        if isinstance(value, (int, str, bool)):
            return value

        if isinstance(value, bytes):
            return f"0x{value.hex()}"

        if isinstance(value, (list, tuple)):
            return [self._serialize_value(v) for v in value]

        if isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}

        # Fallback: convert to string
        return str(value)

    def get_trace_config(self) -> TraceConfig:
        """
        Get the complete trace configuration.

        Finalizes state tracking and returns the complete trace.

        Returns:
            TraceConfig object with all recorded operations
        """
        # Finalize state tracking
        self._state_tracker.finalize(self._trace)

        return TraceConfig(default_fork=self._fork_name, trace=self._trace)

    def save_trace(self, output_file: Path) -> None:
        """
        Save the trace to a YAML file.

        Args:
            output_file: Path where the trace YAML will be saved
        """
        trace_config = self.get_trace_config()

        # Save as YAML
        yaml = YAML()
        yaml.default_flow_style = False

        with output_file.open("w") as f:
            yaml.dump(trace_config.model_dump(mode="json"), f)

        print(f"Trace saved to: {output_file}")
        print(f"SSZ objects stored in: {self._store.output_dir}")
