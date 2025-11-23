"""
Traced Spec Proxy
-----------------
A wrapper around the spec object that records all interactions.

It uses `wrapt.ObjectProxy` to intercept function calls, recording their:
1. Arguments (sanitized and mapped to context variables)
2. Return values
3. State context (injecting 'load_state' when the context switches)
"""

import inspect
from typing import Any

import wrapt
from remerkleable.complex import Container

from .models import (
    CLASS_NAME_MAP,
    NON_SSZ_FIXTURES,
    TraceModel,
    TraceStepModel,
)


class RecordingSpec(wrapt.ObjectProxy):
    """
    A proxy that wraps the 'spec' object to record execution traces.

    It automatically handles state versioning and deduplication.
    It automatically intercepts all other function calls.
    """

    # Internal state
    _model: TraceModel
    _self_config_data: dict[str, Any]
    _self_last_root: str | None

    def __init__(
        self,
        wrapped_spec: Any,
        initial_context_fixtures: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        parameters: dict[str, Any] | None = None,
    ):
        super().__init__(wrapped_spec)

        self._self_config_data = {}
        self._self_last_root = None

        self._model = TraceModel(metadata=metadata or {}, context={"parameters": parameters or {}})

        # Register initial fixtures
        for name, obj in initial_context_fixtures.items():
            self._self_register_fixture(name, obj)

    # NOTE: _self_ prefix recommended in wrapt docs
    def _self_register_fixture(self, name: str, obj: Any) -> None:
        """Registers an initial fixture in the recording context."""
        class_name = type(obj).__name__
        if class_name not in CLASS_NAME_MAP:
            if name in NON_SSZ_FIXTURES:
                self._model.context.fixtures.append(name)
        else:
            # Seed the context with initial SSZ objects
            self._self_process_arg(obj)

    # --- Interception Logic ---

    def __getattr__(self, name: str) -> Any:
        """
        Intercepts attribute access on the spec object.
        If the attribute is a callable (function), it is wrapped to record execution.
        """
        # 1. Access recorder's own methods first
        if name == "save_trace":
            return object.__getattribute__(self, name)

        # 2. Retrieve the real attribute from the wrapped spec
        real_attr = super().__getattr__(name)

        # 3. If it's not a function or shouldn't be traced, return as-is
        if not callable(real_attr) or not name.islower() or name.startswith("_"):
            return real_attr

        # 4. Return the recording wrapper
        return self._self_create_wrapper(name, real_attr)

    def _self_create_wrapper(self, op_name: str, real_func: Any) -> Any:
        """Creates a closure to record the function call."""

        def record_wrapper(*args: Any, **kwargs: Any) -> Any:
            # A. Prepare arguments: bind to signature and serialize
            bound_args = self._self_bind_args(real_func, args, kwargs)

            # Process arguments and auto-register any NEW SSZ objects as artifacts
            serial_params = {k: self._self_process_arg(v) for k, v in bound_args.arguments.items()}

            # B. Identify State object and handle Context Switching
            state_obj, old_hash = self._self_capture_pre_state(bound_args)

            if old_hash is not None:
                current_root_hex = old_hash.hex()
                # If the state passed to this function is different from the last one we saw,
                # inject a `load_state` operation to switch context.
                if self._self_last_root != current_root_hex:
                    # Handle out-of-band mutation:
                    # The model's register_object logic handles re-registration if hash changed

                    # Ensure the state is registered with its current hash
                    state_var = self._self_process_arg(state_obj)

                    if state_var:
                        self._model.trace.append(
                            TraceStepModel(op="load_state", params={}, result=state_var)
                        )
                        self._self_last_root = current_root_hex

            # C. Execute the real function
            try:
                result = real_func(*args, **kwargs)
                error = None
            except Exception as e:
                result = None
                error = {"type": type(e).__name__, "message": str(e)}
                # We must record the step before re-raising
                self._self_record_step(op_name, serial_params, result, error)
                raise e

            # D. Record the successful step
            self._self_record_step(op_name, serial_params, result, None)

            # E. Update tracked state if mutated
            if state_obj is not None:
                self._self_update_state_tracker(state_obj, old_hash)

            return result

        return record_wrapper

    def _self_bind_args(self, func: Any, args: tuple, kwargs: dict) -> inspect.BoundArguments:
        """
        Binds positional and keyword arguments to the function signature.

        We do this because we often use positional arguments in spec tests,
        but for recording we want to have a consistent mapping of parameter names to values.
        """
        sig = inspect.signature(func)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        return bound

    # FIXME: typing for state_obj is tricky because specific implementation is in the spec
    def _self_capture_pre_state(
        self, bound_args: inspect.BoundArguments
    ) -> tuple[Container | None, bytes | None]:
        """Finds the BeaconState argument (if any) and captures its root hash."""
        state_obj = None

        # Look for 'state' in arguments
        state_obj = bound_args.arguments.get("state")

        # If found, capture the hash
        # Use duck typing for hash_tree_root to support Mocks
        if state_obj and hasattr(state_obj, "hash_tree_root"):
            return state_obj, state_obj.hash_tree_root()

        return None, None

    def _self_record_step(self, op: str, params: dict, result: Any, error: dict | None) -> None:
        """Appends a step to the trace."""
        # Auto-register the result if it's an SSZ object (by calling process_arg)
        serialized_result = self._self_process_arg(result) if result is not None else None

        # Create the model to validate and sanitize data (bytes->hex, etc.)
        step_model = TraceStepModel(op=op, params=params, result=serialized_result, error=error)
        self._model.trace.append(step_model)

    def _self_update_state_tracker(
        self,
        state_obj: Container,
        old_hash: bytes | None,
    ) -> None:
        """Updates the internal state tracker if the state object was mutated."""
        if not hasattr(state_obj, "hash_tree_root") or old_hash is None:
            return

        new_hash = state_obj.hash_tree_root()
        new_root_hex = new_hash.hex()

        # Always update the last root to the current state's new root
        # This ensures subsequent operations know what the current state is.
        self._self_last_root = new_root_hex

        if old_hash == new_hash:
            return  # No content change

        # State changed: Register the new state version in the model
        # This updates the mapping so future calls with this object ID get the new name
        self._self_process_arg(state_obj)

    def _self_process_arg(self, arg: Any) -> Any:
        """
        Delegates to TraceModel to register objects/artifacts.
        Returns the context variable string or the original primitive.
        """
        # Delegate registration to the model
        context_name = self._model.register_object(arg)
        if context_name:
            return context_name

        # If register_object returns None, it's a primitive (or unknown type)
        # Pass it through for Pydantic to handle
        return arg

    def save_trace(self, output_dir: str) -> None:
        """
        Writes the captured trace and artifacts to the filesystem.
        Delegates the actual writing to the TraceModel.
        """
        self._model.dump_to_dir(output_dir, config=self._self_config_data)
