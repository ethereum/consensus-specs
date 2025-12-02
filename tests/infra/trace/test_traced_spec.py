"""
This file unit-tests the trace recorder itself using mocks.

It's still pretty basic but covers the core recorder logic.
"""

import pytest
from remerkleable.basic import uint64
from remerkleable.complex import Container

from eth2spec.utils.ssz.ssz_impl import serialize as ssz_serialize
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

    fork = "mock"

    def tick(self, state: BeaconState, slot: int) -> None:
        # Simulate a state change by modifying the root
        # In a real spec, this would be a complex state transition
        new_root_int = int.from_bytes(state._root, "big") + 1
        state._root = new_root_int.to_bytes(32, "big")

    def no_op(self, state: BeaconState) -> None:
        # Does not modify state
        pass

    def iterate_something(self, state: BeaconState, arg_list1: tuple, arg_list2: list) -> None:
        # just for testing sanitization logic
        return list(arg_list1) + arg_list2

    def get_current_epoch(self, state: BeaconState) -> int:
        return 0

    def get_root(self, data: bytes) -> bytes:
        return data  # Echo back bytes

    def get_block_root(self, block: BeaconBlock) -> bytes:
        return block.hash_tree_root()


# --- Fixtures ---


@pytest.fixture
def mock_spec():
    return MockSpec()


@pytest.fixture
def recording_spec(mock_spec):
    return RecordingSpec(mock_spec)


# --- Tests ---


def test_basic_function_call(recording_spec):
    """Tests basic function recording and result capture."""
    proxy = recording_spec

    # The initial state is registered with a hash-based name
    root_hex = b"\x10" * 32
    root_hex_str = root_hex.hex()

    # Find the context variable for this state
    state = BeaconState(root=root_hex, slot=uint64(0))

    # 1. Call function
    # This is the first usage of the state, so we expect an implicit load_state
    result = proxy.get_current_epoch(state)

    assert result == 0
    assert len(proxy._model.trace) == 2

    # Verify auto-injected load_state
    load_step = proxy._model.trace[0]
    assert load_step.op == "load_state"
    assert load_step.state_root == root_hex_str

    assert load_step.model_dump(mode="json").get("state_root") == f"{root_hex_str}.ssz_snappy"
    assert proxy._model._artifacts[root_hex_str] == ssz_serialize(state)

    # Verify actual operation
    step = proxy._model.trace[1]
    assert step.op == "spec_call"
    assert step.method == "get_current_epoch"
    assert step.assert_output == 0

    proxy._finalize_trace()
    assert len(proxy._model.trace) == 3

    # Verify auto-injected assert_state (must be the same state)
    assert_step = proxy._model.trace[-1]
    assert assert_step.op == "assert_state"
    assert assert_step.state_root == root_hex_str

    assert assert_step.model_dump(mode="json").get("state_root") == f"{root_hex_str}.ssz_snappy"
    assert proxy._model._artifacts[root_hex_str] == ssz_serialize(state)



def test_argument_sanitization(recording_spec):
    """Tests that arguments are sanitized (bytes -> hex, subclasses -> primitives)."""
    proxy = recording_spec

    # 1. Bytes should be hex-encoded
    data = b"\xca\xfe"
    proxy.get_root(data)

    step = proxy._model.trace[0]
    assert step.input["data"] == b"\xca\xfe"  # raw here

    assert (step.model_dump(mode="json").get("input") or {}).get("data") == "0xcafe"

    # 2. Int subclasses (Slot) should be raw ints
    slot = Slot(42)

    root_hex = b"\x10" * 32
    root_hex_str = root_hex.hex()
    state_name = root_hex_str
    state = BeaconState(root=root_hex, slot=uint64(0))

    proxy.tick(state, slot)

    # Step 0: get_root
    # Step 1: load_state (for tick)
    # Step 2: tick
    step = proxy._model.trace[2]
    assert step.op == "spec_call"
    assert step.method == "tick"
    assert step.input["slot"] == 42
    assert isinstance(step.input["slot"], int)
    assert (step.model_dump(mode="json").get("input") or {}).get("slot") == 42

    assert proxy._model._artifacts[state_name] == ssz_serialize(state)

    assert proxy.iterate_something(state, (1, 2), [3]) == [1, 2, 3]

    step2 = proxy._model.trace[3]
    assert step2.op == "spec_call"
    assert step2.method == "iterate_something"
    assert step2.input["arg_list1"] == (1, 2)
    assert step2.input["arg_list2"] == [3]
    assert step2.assert_output == [1, 2, 3]
    assert isinstance(step2.input["arg_list1"], tuple)
    assert isinstance(step2.input["arg_list2"], list)
    assert isinstance(step2.assert_output, list)
    assert step2.model_dump(mode="json").get("assert_output") == [1, 2, 3]


def test_result_sanitization(recording_spec):
    """Tests that return values are sanitized."""
    proxy = recording_spec

    # get_root returns bytes, expecting hex string in trace
    result = proxy.get_root(b"\xde\xad")

    step = proxy._model.trace[0]
    assert step.assert_output == b"\xde\xad"
    assert step.model_dump(mode="json").get("assert_output") == f"0x{result.hex()}" == "0xdead"


def test_state_mutation_and_deduplication(recording_spec):
    """
    Tests the smart state tracking logic.
    """
    proxy = recording_spec

    root_hex = b"\x10" * 32
    root_hex_str = root_hex.hex()
    state_name = root_hex_str

    state = BeaconState(root=root_hex, slot=uint64(0))

    # 1. Call op that DOES change state
    proxy.tick(state, 1)

    # We expect 2 steps: [load_state, tick]
    assert len(proxy._model.trace) == 2

    load_step = proxy._model.trace[0]
    tick_step = proxy._model.trace[1]

    assert load_step.op == "load_state"
    assert load_step.state_root == root_hex_str
    assert tick_step.op == "spec_call"
    assert tick_step.method == "tick"
    assert proxy._model._artifacts[state_name] == ssz_serialize(state)

    # Check naming convention: should be hash-based
    new_root = state.hash_tree_root().hex()
    assert new_root != root_hex_str

    # Ensure the recorder internally tracked the new root
    assert proxy._last_state_root == new_root

    # 2. Call op that DOES NOT change state
    proxy.no_op(state)

    # Should NOT add 'load_state' because recorder knows the state is already at new_root
    assert len(proxy._model.trace) == 3
    assert proxy._model.trace[2].op == "spec_call"
    assert proxy._model.trace[2].method == "no_op"

    assert proxy._model._artifacts[state_name] == ssz_serialize(state)

    # 3. Simulate OUT-OF-BAND mutation
    manual_root_int = int.from_bytes(state._root, "big") + 1
    state._root = manual_root_int.to_bytes(32, "big")
    manual_root_hex = state.hash_tree_root().hex()

    # 4. Call op with this "new" state
    proxy.no_op(state)

    # Now we EXPECT 'load_state' because the passed state (manual_root)
    # differs from what the recorder expects (new_root)
    assert len(proxy._model.trace) == 6

    assert_step = proxy._model.trace[3]
    assert assert_step.op == "assert_state"
    load_step_2 = proxy._model.trace[4]
    assert load_step_2.op == "load_state"
    assert load_step_2.state_root == manual_root_hex
    assert proxy._model.trace[5].op == "spec_call"
    assert proxy._model.trace[5].method == "no_op"

    assert proxy._model._artifacts[manual_root_hex] == ssz_serialize(state)


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

    ## The argument should be serialized as a context var with the hash
    # The artifact should be queued with hash-based filename
    expected_name = block_root.hex()

    ## The object should be registered in the map
    assert block_root.hex() in proxy._model._artifacts

    # Check params
    assert step.input["block"] == f"{expected_name}.ssz_snappy"
    # already suffixed (other than state root in load/assert blocks)
    assert (step.model_dump(mode="json").get("input") or {}).get(
        "block"
    ) == f"{expected_name}.ssz_snappy"


def test_empty_trace(recording_spec):
    """Making sure no weird edge cases."""
    proxy = recording_spec

    # try to save a state that's not a state
    proxy._capture_pre_state(None)
    proxy._capture_post_state(None)
    # try to finalize without a single state being captured
    proxy._finalize_trace()

    # Check the trace
    assert len(proxy._model.trace) == 0
    assert len(proxy._model._artifacts) == 0
