"""
State tracking for automatic load/assert generation.

This module provides intelligent state change detection for trace generation.
"""

from __future__ import annotations

from eth2spec.utils.ssz.ssz_impl import hash_tree_root
from eth2spec.utils.ssz.ssz_typing import View

from .models import AssertStateOp, BaseOperation, LoadStateOp
from .ssz_store import SSZObjectStore

__all__ = ["StateTracker"]


class StateTracker:
    """
    Tracks state changes through spec method calls.

    Optimizes storage by detecting when state hasn't changed and automatically
    generating load_state/assert_state operations when manual modifications occur.

    Attributes:
        store: SSZ object store for persisting states
        last_state_root: Hash root of the previous state
        current_state_root: Hash root of the current state
        _state_loaded: Flag indicating if initial state has been loaded
    """

    def __init__(self, store: SSZObjectStore) -> None:
        """
        Initialize the state tracker.

        Args:
            store: SSZ object store for state persistence
        """
        self.store = store
        self.last_state_root: str | None = None
        self.current_state_root: str | None = None
        self._state_loaded = False

    def track_state_input(self, state: View, trace: list[BaseOperation]) -> None:
        """
        Track a state being used as input to a spec method.

        Automatically adds load_state operation if:
        - This is the first time state is used
        - State has been manually modified since last tracked output

        Args:
            state: The state object being used
            trace: The trace operation list to append to
        """
        state_root = hash_tree_root(state).hex()

        # First time seeing any state
        if not self._state_loaded:
            trace.append(LoadStateOp(state_root=state_root))
            self.current_state_root = state_root
            self._state_loaded = True
            return

        # State manually modified (doesn't match last output)
        if state_root != self.current_state_root:
            # Assert the previous state first
            if self.current_state_root:
                trace.append(AssertStateOp(state_root=self.current_state_root))
            # Load the new state
            trace.append(LoadStateOp(state_root=state_root))
            self.current_state_root = state_root

    def track_state_output(self, state: View) -> None:
        """
        Track state after a method call that modifies it.

        Updates internal tracking to reflect the new state root without
        adding trace operations (the mutation was from a spec call).

        Args:
            state: The modified state object
        """
        self.last_state_root = self.current_state_root
        self.current_state_root = hash_tree_root(state).hex()

    def finalize(self, trace: list[BaseOperation]) -> None:
        """
        Add final state assertion to complete the trace.

        Args:
            trace: The trace operation list to append to
        """
        if self.current_state_root:
            trace.append(AssertStateOp(state_root=self.current_state_root))
