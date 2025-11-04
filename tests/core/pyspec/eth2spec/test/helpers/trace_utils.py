#!/usr/bin/env python3
"""
Utility script to validate, inspect, and debug spec traces.

Usage:
    python trace_utils.py validate traces/test_example/trace.yaml
    python trace_utils.py inspect traces/test_example/trace.yaml
    python trace_utils.py stats traces/test_example/
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML


def validate_trace(trace_file: Path) -> bool:
    """
    Validate a trace file for correctness.

    Returns:
        True if valid, False otherwise
    """
    try:
        yaml = YAML()
        with trace_file.open() as f:
            trace_data = yaml.load(f)

        # Check required fields
        if "default_fork" not in trace_data:
            print("❌ Missing 'default_fork' field")
            return False

        if "trace" not in trace_data:
            print("❌ Missing 'trace' field")
            return False

        if not isinstance(trace_data["trace"], list):
            print("❌ 'trace' must be a list")
            return False

        # Validate operations
        valid_ops = {"load_state", "spec_call", "assert_state"}

        for i, op in enumerate(trace_data["trace"]):
            if "op" not in op:
                print(f"❌ Operation {i} missing 'op' field")
                return False

            if op["op"] not in valid_ops:
                print(f"❌ Operation {i} has invalid op: {op['op']}")
                return False

            # Validate specific operation types
            if op["op"] == "load_state" and "state_root" not in op:
                print(f"❌ load_state operation {i} missing 'state_root'")
                return False

            if op["op"] == "assert_state" and "state_root" not in op:
                print(f"❌ assert_state operation {i} missing 'state_root'")
                return False

            if op["op"] == "spec_call" and "method" not in op:
                print(f"❌ spec_call operation {i} missing 'method'")
                return False

        # Check trace structure
        if not any(o["op"] == "load_state" for o in trace_data["trace"]):
            print("⚠️  Warning: No load_state operations found")

        if not any(o["op"] == "assert_state" for o in trace_data["trace"]):
            print("⚠️  Warning: No assert_state operations found")

        print("✅ Trace file is valid")
        print(f"   Fork: {trace_data['default_fork']}")
        print(f"   Operations: {len(trace_data['trace'])}")

        return True

    except Exception as e:
        print(f"❌ Error validating trace: {e}")
        return False


def inspect_trace(trace_file: Path) -> None:
    """
    Display detailed information about a trace file.
    """
    yaml = YAML()
    with trace_file.open() as f:
        trace_data = yaml.load(f)

    print(f"\n{'=' * 70}")
    print(f"TRACE INSPECTION: {trace_file.name}")
    print(f"{'=' * 70}\n")

    print(f"📁 File: {trace_file}")
    print(f"🔱 Fork: {trace_data['default_fork']}")
    print(f"📊 Total Operations: {len(trace_data['trace'])}\n")

    # Count operation types
    op_counts: dict[str, int] = {}
    spec_methods: dict[str, int] = {}

    for op in trace_data["trace"]:
        op_type = op["op"]
        op_counts[op_type] = op_counts.get(op_type, 0) + 1

        if op_type == "spec_call":
            method = op["method"]
            spec_methods[method] = spec_methods.get(method, 0) + 1

    print("📈 Operation Summary:")
    for op_type, count in sorted(op_counts.items()):
        print(f"   • {op_type:20} {count:3} operations")

    if spec_methods:
        print("\n🔧 Spec Methods Called:")
        for method, count in sorted(spec_methods.items(), key=lambda x: -x[1]):
            print(f"   • {method:40} {count:3}×")

    # Detailed trace
    print(f"\n{'─' * 70}")
    print("DETAILED TRACE:")
    print(f"{'─' * 70}\n")

    for i, op in enumerate(trace_data["trace"], 1):
        op_type = op["op"]

        if op_type == "load_state":
            root = op["state_root"][:16] + "..."
            print(f"{i:3}. 📥 LOAD STATE")
            print(f"     Root: {root}")

        elif op_type == "assert_state":
            root = op["state_root"][:16] + "..."
            print(f"{i:3}. ✅ ASSERT STATE")
            print(f"     Root: {root}")

        elif op_type == "spec_call":
            method = op["method"]
            has_input = "input" in op and op["input"]
            has_output = "assert_output" in op and op["assert_output"] is not None

            print(f"{i:3}. 🔧 SPEC CALL: {method}")

            if has_input:
                print(f"     Input: {_format_value(op['input'], indent=12)}")

            if has_output:
                print(f"     Output: {_format_value(op['assert_output'], indent=12)}")

        print()


def _format_value(value: Any, indent: int = 0) -> str:
    """Format a value for display."""
    if isinstance(value, dict):
        if "ssz_file" in value:
            return f"<SSZ: {value['ssz_file']}>"
        return json.dumps(value, indent=2)

    if isinstance(value, list):
        if len(value) <= 3:
            return str(value)
        return f"[{len(value)} items]"

    if isinstance(value, str) and len(value) > 50:
        return value[:50] + "..."

    return str(value)


def compute_stats(trace_dir: Path) -> None:
    """
    Compute statistics for all traces in a directory.
    """
    trace_files = list(trace_dir.rglob("trace.yaml"))

    if not trace_files:
        print(f"❌ No trace files found in {trace_dir}")
        return

    print(f"\n{'=' * 70}")
    print(f"TRACE STATISTICS: {trace_dir}")
    print(f"{'=' * 70}\n")

    print(f"📁 Directory: {trace_dir}")
    print(f"📊 Total Traces: {len(trace_files)}\n")

    total_ops = 0
    total_spec_calls = 0
    all_methods = set()
    all_forks = set()

    yaml = YAML()

    for trace_file in trace_files:
        with trace_file.open() as f:
            trace_data = yaml.load(f)

        all_forks.add(trace_data["default_fork"])
        total_ops += len(trace_data["trace"])

        for op in trace_data["trace"]:
            if op["op"] == "spec_call":
                total_spec_calls += 1
                all_methods.add(op["method"])

    print(f"🔱 Forks: {', '.join(sorted(all_forks))}")
    print(f"📊 Total Operations: {total_ops}")
    print(f"🔧 Total Spec Calls: {total_spec_calls}")
    print(f"📝 Unique Methods: {len(all_methods)}")
    print(f"📈 Avg Ops/Trace: {total_ops / len(trace_files):.1f}")

    # List all unique methods
    print("\n🔧 All Spec Methods Used:")
    for method in sorted(all_methods):
        print(f"   • {method}")

    # Check SSZ objects
    ssz_dirs = list(trace_dir.rglob("ssz_objects"))
    if ssz_dirs:
        total_ssz_files = sum(len(list(d.glob("*.ssz_snappy"))) for d in ssz_dirs)
        print(f"\n💾 SSZ Objects Stored: {total_ssz_files}")


def convert_to_json(trace_file: Path, output_file: Path = None) -> None:
    """Convert a YAML trace to JSON format."""
    yaml = YAML()
    with trace_file.open() as f:
        trace_data = yaml.load(f)

    if output_file is None:
        output_file = trace_file.with_suffix(".json")

    with output_file.open("w") as f:
        json.dump(trace_data, f, indent=2)

    print(f"✅ Converted to JSON: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Utility for working with spec trace files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate a trace file")
    validate_parser.add_argument("trace_file", type=Path, help="Path to trace.yaml")

    # Inspect command
    inspect_parser = subparsers.add_parser("inspect", help="Inspect a trace file in detail")
    inspect_parser.add_argument("trace_file", type=Path, help="Path to trace.yaml")

    # Stats command
    stats_parser = subparsers.add_parser(
        "stats", help="Compute statistics for all traces in a directory"
    )
    stats_parser.add_argument("trace_dir", type=Path, help="Directory containing traces")

    # Convert command
    convert_parser = subparsers.add_parser("convert", help="Convert YAML trace to JSON")
    convert_parser.add_argument("trace_file", type=Path, help="Path to trace.yaml")
    convert_parser.add_argument("--output", "-o", type=Path, help="Output JSON file")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == "validate":
            success = validate_trace(args.trace_file)
            return 0 if success else 1

        elif args.command == "inspect":
            inspect_trace(args.trace_file)
            return 0

        elif args.command == "stats":
            compute_stats(args.trace_dir)
            return 0

        elif args.command == "convert":
            convert_to_json(args.trace_file, args.output)
            return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
