"""
This file unit-tests the trace recorder itself using
pytest fixtures and unittest.mock.

This approach is faster and more isolated than using 'pytester'.
It's still pretty basic but covers the core recorder logic.
"""

import pytest
from remerkleable.basic import uint64
from remerkleable.complex import Container

from tests.infra.trace.traced_spec import RecordingSpec

# --- Mocks for eth2spec objects ---
# We rename these to match the expected class names in CLASS_NAME_MAP
# and inherit from Container so isinstance(x, Container) checks pass.


class BeaconState(Container):
    """Mocks a BeaconState"""

    slot: uint64

    def __new__(cls, root: bytes = b"\x00" * 32, slot: int = 0):
        # Intercept 'root' here so it doesn't go to Container.__new__
        # Container.__new__ enforces field validation, which we want to bypass for mocks
        return super().__new__(cls, slot=slot)

    def __init__(self, root: bytes = b"\x00" * 32, slot: int = 0):
        # Initialize the underlying Container with the slot value
        super().__init__(slot=slot)
        # Store our mock root separately
        self._root = root

    def hash_tree_root(self) -> bytes:
        # Return the mock root, not the calculated one
        return self._root

    def copy(self):
        return BeaconState(self._root, int(self.slot))


class BeaconBlock(Container):
    """Mocks a BeaconBlock"""

    slot: uint64

    def __new__(cls, root: bytes = b"\x01" * 32, slot: int = 0):
        return super().__new__(cls, slot=slot)

    def __init__(self, root: bytes = b"\x01" * 32, slot: int = 0):
        super().__init__(slot=slot)
        self._root = root

    def hash_tree_root(self) -> bytes:
        return self._root


class Attestation(Container):
    """Mocks an Attestation"""

    data: uint64  # Dummy field to satisfy Container requirements

    def __new__(cls, root: bytes = b"\x02" * 32):
        return super().__new__(cls, data=0)

    def __init__(self, root: bytes = b"\x02" * 32):
        super().__init__(data=0)
        self._root = root

    def hash_tree_root(self) -> bytes:
        return self._root


class Slot(int):
    """Mocks a Slot (int subclass)"""

    pass


class MockSpec:
    """Mocks the 'spec' object"""

    def tick(self, state: BeaconState, slot: int) -> None:
        # Simulate a state change by modifying the root
        # In a real spec, this would be a complex state transition
        new_root_int = int.from_bytes(state._root, "big") + 1
        state._root = new_root_int.to_bytes(32, "big")

    def no_op(self, state: BeaconState) -> None:
        # Does not modify state
        pass

    def get_current_epoch(self, state: BeaconState) -> int:
        return 0

    def get_root(self, data: bytes) -> bytes:
        return data  # Echo back bytes

    def get_block_root(self, block: BeaconBlock) -> bytes:
        return block.hash_tree_root()

    def fail_op(self) -> None:
        raise AssertionError("Something went wrong")


# --- Fixtures ---


@pytest.fixture
def mock_spec():
    return MockSpec()


@pytest.fixture
def recording_spec(mock_spec):
    # Initial context with one state
    # Root is 101010...
    initial_state = BeaconState(root=b"\x10" * 32)
    context = {"state": initial_state}

    return RecordingSpec(mock_spec, context)


# --- Tests ---


def test_basic_function_call(recording_spec):
    """Tests basic function recording and result capture."""
    proxy = recording_spec

    # The initial state is registered with a hash-based name
    root_hex = b"\x10" * 32
    # root_hex_str = root_hex.hex()

    # Find the context variable for this state
    state_name = None
    for name, obj in proxy._model._name_to_obj.items():
        if obj.hash_tree_root() == root_hex:
            state_name = name
            break
    assert state_name is not None

    # 1. Call function
    # This is the first usage of the state, so we expect an implicit load_state
    result = proxy.get_current_epoch(proxy._model._name_to_obj[state_name])

    assert result == 0
    assert len(proxy._model.trace) == 2

    # Verify auto-injected load_state
    load_step = proxy._model.trace[0]
    assert load_step.op == "load_state"
    assert load_step.result == state_name
    # TODO hash should match root_hex_str

    # Verify actual operation
    step = proxy._model.trace[1]
    assert step.op == "get_current_epoch"
    assert step.result == 0
    assert step.error is None


def test_argument_sanitization(recording_spec):
    """Tests that arguments are sanitized (bytes -> hex, subclasses -> primitives)."""
    proxy = recording_spec

    # 1. Bytes should be hex-encoded
    data = b"\xca\xfe"
    proxy.get_root(data)

    step = proxy._model.trace[0]
    assert step.params["data"] == "0xcafe"  # 0xhex

    # 2. Int subclasses (Slot) should be raw ints
    slot = Slot(42)

    root_hex = b"\x10" * 32
    root_hex_str = root_hex.hex()
    state_name = f"$context.states.{root_hex_str}"
    state = proxy._model._name_to_obj[state_name]

    proxy.tick(state, slot)

    # Step 0: get_root
    # Step 1: load_state (for tick)
    # Step 2: tick
    step = proxy._model.trace[2]
    assert step.op == "tick"
    assert step.params["slot"] == 42
    assert type(step.params["slot"]) is int


def test_result_sanitization(recording_spec):
    """Tests that return values are sanitized."""
    proxy = recording_spec

    # get_root returns bytes, expecting hex string in trace
    result = proxy.get_root(b"\xde\xad")

    step = proxy._model.trace[0]
    assert step.result == f"0x{result.hex()}" == "0xdead"


def test_exception_handling(recording_spec):
    """Tests that exceptions are captured in the trace."""
    proxy = recording_spec

    # Should re-raise the exception
    with pytest.raises(AssertionError, match="Something went wrong"):
        proxy.fail_op()

    assert len(proxy._model.trace) == 1
    step = proxy._model.trace[0]
    assert step.op == "fail_op"

    # "result" is excluded when None
    assert step.result is None

    assert step.error["type"] == "AssertionError"
    assert step.error["message"] == "Something went wrong"


def test_state_mutation_and_deduplication(recording_spec):
    """
    Tests the smart state tracking logic.
    """
    proxy = recording_spec

    root_hex = b"\x10" * 32
    root_hex_str = root_hex.hex()
    state_name = f"$context.states.{root_hex_str}"
    state = proxy._model._name_to_obj[state_name]

    # 1. Call op that DOES change state
    proxy.tick(state, 1)

    # We expect 2 steps: [load_state, tick]
    assert len(proxy._model.trace) == 2

    load_step = proxy._model.trace[0]
    tick_step = proxy._model.trace[1]

    assert load_step.op == "load_state"
    assert load_step.result == state_name
    assert tick_step.op == "tick"

    # Check naming convention: should be hash-based
    new_root = state.hash_tree_root().hex()
    assert new_root != root_hex_str

    # Ensure the recorder internally tracked the new root
    assert proxy._self_last_root == new_root

    # 2. Call op that DOES NOT change state
    proxy.no_op(state)

    # Should NOT add 'load_state' because recorder knows the state is already at new_root
    assert len(proxy._model.trace) == 3
    assert proxy._model.trace[2].op == "no_op"

    # 3. Simulate OUT-OF-BAND mutation
    manual_root_int = int.from_bytes(state._root, "big") + 1
    state._root = manual_root_int.to_bytes(32, "big")
    manual_root_hex = state.hash_tree_root().hex()

    # 4. Call op with this "new" state
    proxy.no_op(state)

    # Now we EXPECT 'load_state' because the passed state (manual_root)
    # differs from what the recorder expects (new_root)
    assert len(proxy._model.trace) == 5

    load_step_2 = proxy._model.trace[3]
    assert load_step_2.op == "load_state"
    assert load_step_2.result == f"$context.states.{manual_root_hex}"
    assert proxy._model.trace[4].op == "no_op"


def test_non_state_object_naming(recording_spec):
    """Tests that non-state objects (blocks) are named by hash."""
    proxy = recording_spec

    # Create a mock block
    block_root = b"\x02" * 32
    block = BeaconBlock(root=block_root)

    # Call a function with the block
    proxy.get_block_root(block)

    # Check the trace
    # We expect 1 step: get_block_root
    assert len(proxy._model.trace) == 1
    step = proxy._model.trace[0]

    # The argument should be serialized as a context var with the hash
    expected_name = f"$context.blocks.{block_root.hex()}"

    # Check params
    assert step.params["block"] == expected_name

    # The object should be registered in the map
    assert expected_name in proxy._model._hash_to_name.values()

    # The artifact should be queued with hash-based filename
    expected_filename = f"blocks_{block_root.hex()}.ssz"
    assert expected_filename in proxy._model._artifacts
