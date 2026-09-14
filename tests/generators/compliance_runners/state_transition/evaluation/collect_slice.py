"""Materialize a mutable PySpec call slice for one or more root functions.

Excluded functions remain imported from the installed PySpec, so the generated
module remains executable while the evaluation denominator stays focused on
the Gloas-specific code under test.
"""

from __future__ import annotations

import argparse
import ast
import builtins
import importlib
import inspect
import sys
import textwrap
import types
import typing
from pathlib import Path


def load_module(fork: str, preset: str):
    return importlib.import_module(f"eth_consensus_specs.{fork}.{preset}")


def unwrap(function):
    """Peel PySpec decorators to the source function."""
    while isinstance(function, types.FunctionType):
        if hasattr(function, "__wrapped__"):
            function = function.__wrapped__
        elif function.__name__ == "wrapper" and function.__closure__:
            cells = dict(zip(function.__code__.co_freevars, function.__closure__, strict=True))
            if "value_fn" not in cells:
                break
            function = cells["value_fn"].cell_contents
        else:
            break
    return function


def references(function) -> list[str]:
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    seen: set[str] = set()
    result = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id not in seen:
            seen.add(node.id)
            result.append(node.id)
    return result


def collect(module, roots: list[str], excluded: set[str]):
    """Return source in callee-first order plus the required package imports."""
    expanded: list[tuple[str, str]] = []
    expanded_names: set[str] = set()
    reachable_from: dict[str, set[str]] = {}
    imports: list[str] = []
    typing_imports: list[str] = []
    visited: set[tuple[str, str]] = set()
    uses_config = False

    def add_import(name: str) -> None:
        if name not in imports and name != "config":
            imports.append(name)

    def visit(name: str, root: str) -> None:
        nonlocal uses_config
        if (name, root) in visited:
            return
        if not hasattr(module, name):
            raise ValueError(f"{name} is not in {module.__name__}")
        visited.add((name, root))
        function = unwrap(getattr(module, name))
        if not isinstance(function, types.FunctionType):
            add_import(name)
            return
        if name in excluded:
            add_import(name)
            return
        reachable_from.setdefault(name, set()).add(root)
        source = textwrap.dedent(inspect.getsource(function))
        uses_config |= "config." in source
        for reference in references(function):
            if reference == name or hasattr(builtins, reference):
                continue
            if hasattr(typing, reference) and not hasattr(module, reference):
                if reference not in typing_imports:
                    typing_imports.append(reference)
            elif hasattr(module, reference):
                object_ = getattr(module, reference)
                if isinstance(unwrap(object_), types.FunctionType):
                    visit(reference, root)
                else:
                    add_import(reference)
        if name not in expanded_names:
            expanded_names.add(name)
            expanded.append((name, source))

    for root in roots:
        if root in excluded:
            raise ValueError(f"root {root} cannot also be excluded")
        visit(root, root)
    return expanded, imports, typing_imports, uses_config, reachable_from


def emit(module, roots, excluded, expanded, imports, typing_imports, uses_config, reachable_from, group) -> str:
    parts = [
        f'"""Code slice for {", ".join(f"`{root}`" for root in roots)}.',
        "",
        f"Generated from installed `{module.__name__}` by evaluation.collect_slice.",
        "Excluded helpers are imported from the package and intentionally omitted.",
        f"Excluded: {', '.join(sorted(excluded)) or '(none)'}",
        f"Evaluation group: {group or '(ad hoc roots)'}",
        '"""',
        "",
    ]
    import_names = [*imports, *( ["config"] if uses_config else [])]
    if import_names:
        parts.extend([f"from {module.__name__} import (", *(f"    {name}," for name in import_names), ")"])
    if typing_imports:
        parts.append(f"from typing import {', '.join(typing_imports)}")
    for name, source in expanded:
        roots_text = ", ".join(sorted(reachable_from[name]))
        parts.extend(("", f"# Reachable from: {roots_text}", source.rstrip()))
    return "\n".join(parts) + "\n"


def check(path: Path, module) -> int:
    text = path.read_text()
    failures = 0
    for node in ast.parse(text).body:
        if not isinstance(node, ast.FunctionDef):
            continue
        expected = textwrap.dedent(inspect.getsource(unwrap(getattr(module, node.name)))).rstrip()
        actual = ast.get_source_segment(text, node).rstrip()
        if actual != expected:
            print(f"FAIL {node.name}: source differs from installed package")
            failures += 1
        else:
            print(f"OK   {node.name}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("roots", nargs="*", help="one or more PySpec root functions")
    parser.add_argument("--fork", default="gloas")
    parser.add_argument("--preset", default="minimal")
    parser.add_argument("--exclude", nargs="*", default=[])
    parser.add_argument("--group", help="group name recorded in the slice annotation")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()
    module = load_module(args.fork, args.preset)
    if args.check:
        return check(args.check, module)
    if not args.roots:
        parser.error("at least one root function is required")
    expanded, imports, typing_imports, uses_config, reachable_from = collect(
        module, args.roots, set(args.exclude)
    )
    output = emit(
        module, args.roots, set(args.exclude), expanded, imports, typing_imports, uses_config,
        reachable_from, args.group,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
