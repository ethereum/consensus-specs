"""
Traced Spec Proxy
-----------------
A wrapper around the spec object that records all interactions.

It uses `wrapt.ObjectProxy` to intercept function calls, recording their:
1. Arguments (sanitized and serialized to ssz artifacts when appropriate)
2. Return values (processed the same way)
3. State context (injecting load_state/assert_state when it's changed)
"""

import inspect
from typing import Any

import wrapt

from eth2spec.utils.ssz.ssz_impl import serialize as ssz_serialize
from eth2spec.utils.ssz.ssz_typing import View

from .models import (
    AssertStateOp,
    LoadStateOp,
    SpecCallOp,
    TraceConfig,
)

NON_SSZ_TYPES = bool | int | str | bytes


def is_serializable(value: Any) -> bool:
    """Simple type checking."""
    if value is None:
        return False

    if not isinstance(value, View):
        return False

    # do not ssz primitives even if they are subclassing View
    if isinstance(value, NON_SSZ_TYPES):
        return False

    return True


class RecordingSpec(wrapt.ObjectProxy):
    """
    A proxy that wraps the 'spec' object to record execution traces.

    All magic methods and attributes work as before (pass-through).
    It automatically intercepts all normal function/method calls.
    It automatically handles state versioning and deduplication.
    """

    # Internal state
    _model: TraceConfig
    _last_state_root: str | None

    def __init__(self, wrapped_spec: Any):
        super().__init__(wrapped_spec)

        self._last_state_root = None

        self._model = TraceConfig(default_fork=wrapped_spec.fork)

    def __getattr__(self, name: str) -> Any:
        """
        Intercepts attribute access on the spec object.

        Wrap lowercase methods into a wrapt decorator.
        Pass everything else through.
        """
        # We use lazy wrapping (wrapping each method when it's called)

        # 1. Retrieve the real attribute from the wrapped spec
        real_attr = super().__getattr__(name)

        # 2. Filter: Only wrap public, lowercase functions
        if name.startswith("_") or not name.islower() or not callable(real_attr):
            return real_attr

        # 3. Decorate: Apply the decorator factory and return
        return self._spec_call_hook(real_attr)

    @wrapt.decorator
    def _spec_call_hook(
        self, wrapped: Any, instance: "RecordingSpec", args: tuple, kwargs: dict
    ) -> Any:
        """
        The main hook that records the execution step.

        Args:
            wrapped: The original (unwrapped) spec function.
            instance: The original spec object.
            args/kwargs: Arguments passed to the function.
        """
        method_name = wrapped.__name__
        op_name = "spec_call"

        # A. Prepare arguments: bind to signature and serialize
        bound_args = self._bind_args(wrapped, args, kwargs)

        # Process arguments and auto-register any new SSZ objects as artifacts
        serial_params = {k: self._process_arg(v) for k, v in bound_args.arguments.items()}

        # B. Identify State object and handle external state mutations
        self._capture_pre_state(state := bound_args.arguments.get("state"))

        # C. Execute the real function with original args/kwargs
        result = wrapped(*args, **kwargs)

        # D. Record the successful step
        self._record_step(op_name, method_name, serial_params, result)

        # E. Update tracked state if mutated
        if state is not None:
            self._capture_post_state(state)

        return result

    def _bind_args(self, func: callable, args: tuple, kwargs: dict) -> inspect.BoundArguments:
        """
        Binds positional and keyword arguments to the function signature.

        We do this because we often use positional arguments in spec tests,
        but for recording we want to have a consistent mapping of parameter names to values.
        """
        sig = inspect.signature(func)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        return bound

    def _capture_pre_state(self, state: View | None) -> None:
        """Finds the BeaconState argument (if any) and captures its root hash."""
        if not isinstance(state, View):
            return
        if (old_root := self._last_state_root) != (new_root := state.hash_tree_root().hex()):
            # Assert last output state (was serialized in capture_post_state)
            if old_root:
                self._model.trace.append(AssertStateOp(state_root=old_root))
            # Handle out-of-band mutation / add LoadState:
            # note: this is always serialized before so no process_arg
            self._model.trace.append(LoadStateOp(state_root=new_root))
            self._last_state_root = new_root

    def _record_step(
        self,
        op: str,
        method: str,
        params: dict,
        result: Any,
    ) -> None:
        """Appends a step to the trace."""
        # Auto-register the result if it's an SSZ object (by calling process_arg)
        serialized_result = self._process_arg(result)

        # Create the model to validate and sanitize data (bytes->hex, etc.)
        step_model = SpecCallOp(
            op=op,
            method=method,
            input=params,
            assert_output=serialized_result,
        )
        self._model.trace.append(step_model)

    def _capture_post_state(self, state: View | None) -> None:
        """Updates the internal state tracker if the state object was mutated."""
        if not isinstance(state, View) or self._last_state_root is None:
            # it's not possible to get a new state here that wasn't registered
            # as pre_state before the call so maybe this check is excessive
            return

        if self._last_state_root == (new_root := state.hash_tree_root().hex()):
            return  # No content change

        self._process_arg(state)
        self._last_state_root = new_root

    def _process_arg(self, arg: View | Any) -> str | Any:
        """
        Process a potential container.
        Returns the root hash of container or the original primitive.
        """

        # recursively handle lists and tuples preserving type
        if isinstance(arg, tuple):
            return tuple(self._process_arg(elem) for elem in arg)
        if isinstance(arg, list):
            return [self._process_arg(elem) for elem in arg]

        if not is_serializable(arg):
            return arg

        # ssz-serialize (dumper will snappy-compress later)
        ssz_hash = arg.hash_tree_root().hex()
        self._model._artifacts[ssz_hash] = ssz_serialize(arg)

        # Generate artifact name (content-addressed by hex root hash)
        return f"{ssz_hash}.ssz_snappy"

    def _record_auto_assert_step(self) -> None:
        """Appends assert_state step at the end of the trace."""
        # Auto-register last state root in assert_state step

        if self._last_state_root:
            step_model = AssertStateOp(state_root=self._last_state_root)
            self._model.trace.append(step_model)

    def _finalize_trace(self) -> None:
        """Finalize the trace for saving."""
        self._record_auto_assert_step()
