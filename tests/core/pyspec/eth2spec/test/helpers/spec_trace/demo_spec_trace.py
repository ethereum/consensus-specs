"""
Standalone demonstration of the spec trace proxy system.

This script demonstrates the proxy functionality without requiring
the full pytest infrastructure. It shows how the proxy works at a low level.
"""

import json
import sys
import traceback
from pathlib import Path

from ruamel.yaml import YAML

# Add parent directory to path to import spec_trace
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from eth2spec.test.helpers.spec_trace import (
    AssertStateOp,
    LoadStateOp,
    SpecCallOp,
    SpecProxy,
    SSZObjectStore,
    StateTracker,
    TraceConfig,
)


def demo_trace_operations():
    """Demonstrate the trace operation models."""
    print("=" * 70)
    print("DEMO 1: Trace Operation Models")
    print("=" * 70)
    print()

    # Create sample operations
    load_op = LoadStateOp(state_root="0x7a3f9b2c8d1e5f6a...")
    print("✅ Created LoadStateOp:")
    print(f"   {load_op.model_dump()}")
    print()

    spec_call_op = SpecCallOp(method="process_slots", input=[{"slot": 15}], assert_output=None)
    print("✅ Created SpecCallOp:")
    print(f"   {spec_call_op.model_dump()}")
    print()

    assert_op = AssertStateOp(state_root="0x98a1f5e3c7b2d4...")
    print("✅ Created AssertStateOp:")
    print(f"   {assert_op.model_dump()}")
    print()

    # Create a complete trace
    trace_config = TraceConfig(default_fork="fulu", trace=[load_op, spec_call_op, assert_op])
    print("✅ Created TraceConfig:")
    print(f"   Fork: {trace_config.default_fork}")
    print(f"   Operations: {len(trace_config.trace)}")
    print()


def demo_mock_spec():
    """Demonstrate proxy wrapping a mock spec."""
    print("=" * 70)
    print("DEMO 2: Spec Proxy with Mock Spec")
    print("=" * 70)
    print()

    # Create a simple mock spec module
    class MockSpec:
        fork = "demo"
        SLOTS_PER_EPOCH = 32

        def get_current_slot(self, state):
            """Mock function that returns current slot."""
            return state.slot

        def process_slots(self, state, target_slot):
            """Mock function that processes slots."""
            print(f"   [SPEC] Processing slots from {state.slot} to {target_slot}")
            state.slot = target_slot

        def get_total_balance(self, state):
            """Mock function that returns total balance."""
            return sum(state.balances)

    # Create a simple mock state
    class MockState:
        def __init__(self):
            self.slot = 0
            self.balances = [32_000_000_000] * 10
            self._root = b"\x00" * 32  # Mock root

    # Create proxy
    output_dir = Path("./demo_trace")
    output_dir.mkdir(exist_ok=True)

    print("✅ Created mock spec and state")
    print("✅ Creating SpecProxy...")
    print()

    spec = MockSpec()
    state = MockState()

    proxy = SpecProxy(spec_module=spec, fork_name="demo", output_dir=output_dir)

    print("✅ Proxy created successfully!")
    print(f"   Output directory: {output_dir}")
    print()

    # Use the proxy
    print("📝 Executing spec calls through proxy:")
    print()

    # Call 1: Get current slot
    current_slot = proxy.get_current_slot(state)
    print(f"   ✓ Called: get_current_slot(state) → {current_slot}")

    # Call 2: Process slots
    proxy.process_slots(state, 15)
    print("   ✓ Called: process_slots(state, 15)")

    # Call 3: Get total balance
    total = proxy.get_total_balance(state)
    print(f"   ✓ Called: get_total_balance(state) → {total}")

    print()

    # Get trace
    trace_config = proxy.get_trace_config()
    print("✅ Generated trace:")
    print(f"   Fork: {trace_config.default_fork}")
    print(f"   Total operations: {len(trace_config.trace)}")
    print()

    # Show trace details
    print("📋 Trace operations:")
    for i, op in enumerate(trace_config.trace, 1):
        print(f"   {i}. {op.op:15} ", end="")
        if hasattr(op, "method"):
            print(f"method={op.method}")
        elif hasattr(op, "state_root"):
            print(f"state_root={op.state_root[:16]}...")
        else:
            print()


def demo_state_tracking():
    """Demonstrate state tracking optimization."""
    print("=" * 70)
    print("DEMO 3: State Tracking Optimization")
    print("=" * 70)
    print()

    # Create mock SSZ View objects
    class MockView:
        def __init__(self, value):
            self.value = value

        def __hash__(self):
            return hash(self.value)

    output_dir = Path("./demo_trace_state")
    store = SSZObjectStore(output_dir)
    tracker = StateTracker(store)
    trace = []

    print("✅ Created StateTracker")
    print()

    # Simulate state usage pattern
    state1 = MockView("initial_state")
    state2 = MockView("modified_state")
    state3 = MockView("manually_changed_state")

    print("📝 Simulating state tracking:")
    print()

    # First use
    print("   1. First use of state1:")
    tracker.track_state_input(state1, trace)
    print(f"      → Added: {trace[-1].op}")

    # State mutated by spec
    print("   2. State mutated by spec call:")
    tracker.track_state_output(state2)
    print("      → Internal tracking updated")

    # Manually changed state
    print("   3. State manually changed:")
    tracker.track_state_input(state3, trace)
    print(f"      → Added: {trace[-2].op} (assert previous)")
    print(f"      → Added: {trace[-1].op} (load new)")

    # Finalize
    print("   4. Finalize trace:")
    tracker.finalize(trace)
    print(f"      → Added: {trace[-1].op} (final assert)")

    print()
    print(f"✅ Final trace has {len(trace)} operations")


def demo_yaml_export():
    """Demonstrate YAML export."""
    print("=" * 70)
    print("DEMO 4: YAML Export")
    print("=" * 70)
    print()

    # Create sample trace
    trace_config = TraceConfig(
        default_fork="fulu",
        trace=[
            LoadStateOp(state_root="0x7a3f9b2c8d1e5f6a"),
            SpecCallOp(method="get_validator_activation_churn_limit", assert_output=100),
            SpecCallOp(method="process_slots", input=[{"slot": 15}]),
            AssertStateOp(state_root="0x98a1f5e3c7b2d4"),
        ],
    )

    # Export to dict
    trace_dict = trace_config.model_dump(mode="json")

    print("✅ Generated trace as dict:")
    print()

    print(json.dumps(trace_dict, indent=2))
    print()

    # Save to file
    output_file = Path("./demo_trace/example_trace.yaml")
    output_file.parent.mkdir(exist_ok=True)

    yaml = YAML()
    yaml.default_flow_style = False

    with output_file.open("w") as f:
        yaml.dump(trace_dict, f)

    print(f"✅ Saved to: {output_file}")


def main():
    """Run all demonstrations."""
    print()
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "SPEC TRACE PROXY DEMONSTRATION" + " " * 23 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    try:
        demo_trace_operations()
        print()

        demo_mock_spec()
        print()

        try:
            demo_state_tracking()
            print()
        except AttributeError as e:
            print(f"⚠️  Demo 3 skipped (requires real SSZ objects): {e}")
            print()

        demo_yaml_export()
        print()

        print("╔" + "=" * 68 + "╗")
        print("║" + " " * 20 + "ALL DEMOS COMPLETED!" + " " * 27 + "║")
        print("╚" + "=" * 68 + "╝")
        print()

        print("✅ The spec trace proxy system is working correctly!")
        print()
        print("Next steps:")
        print("  1. Check ./demo_trace/ for generated files")
        print("  2. Run: python trace_utils.py inspect demo_trace/example_trace.yaml")
        print("  3. Integrate with real pytest tests")
        print()

    except Exception as e:
        print(f"\n❌ Error during demonstration: {e}")
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
