import re
import textwrap
from functools import reduce
from typing import TypeVar

from .constants import CONSTANT_DEP_SUNDRY_CONSTANTS_FUNCTIONS
from .md_doc_paths import PREVIOUS_FORK_OF
from .spec_builders import spec_builders
from .typing import (
    ProtocolDefinition,
    SpecObject,
    VariableDefinition,
)


def collect_prev_forks(fork: str) -> list[str]:
    forks = [fork]
    while True:
        fork = PREVIOUS_FORK_OF[fork]
        if fork is None:
            return forks
        forks.append(fork)


def requires_mypy_type_ignore(value: str) -> bool:
    return (
        value.startswith("Bitlist")
        or value.startswith("ByteVector")
        or (value.startswith("List") and not re.match(r"^List\[\w+,\s*\w+\]$", value))
        or (value.startswith("Vector") and any(k in value for k in ["ceillog2", "floorlog2"]))
    )


def gen_new_type_definition(name: str, value: str) -> str:
    return (
        f"class {name}({value}):\n    pass"
        if not requires_mypy_type_ignore(value)
        else f"class {name}({value}):  # type: ignore\n    pass"
    )


def make_function_abstract(protocol_def: ProtocolDefinition, key: str):
    function = protocol_def.functions[key].split('"""')
    protocol_def.functions[key] = function[0] + "..."


def objects_to_spec(
    preset_name: str, spec_object: SpecObject, fork: str, ordered_class_objects: dict[str, str]
) -> str:
    """
    Given all the objects that constitute a spec, combine them into a single pyfile.
    """

    def gen_new_type_definitions(custom_types: dict[str, str]) -> str:
        return "\n\n\n".join(
            [gen_new_type_definition(key, value) for key, value in custom_types.items()]
        )

    new_type_definitions = gen_new_type_definitions(spec_object.custom_types)

    # Collect builders with the reversed previous forks
    # e.g. `[bellatrix, altair, phase0]` -> `[phase0, altair, bellatrix]`
    builders = [spec_builders[fork] for fork in collect_prev_forks(fork)[::-1]]

    def format_protocol(protocol_name: str, protocol_def: ProtocolDefinition) -> str:
        abstract_functions = ["verify_and_notify_new_payload"]
        for key in protocol_def.functions.keys():
            if key in abstract_functions:
                make_function_abstract(protocol_def, key)

        protocol = f"class {protocol_name}(Protocol):"
        for fn_source in protocol_def.functions.values():
            fn_source = fn_source.replace("self: " + protocol_name, "self")
            protocol += "\n\n" + textwrap.indent(fn_source, "    ")
        return protocol

    protocols_spec = "\n\n\n".join(format_protocol(k, v) for k, v in spec_object.protocols.items())
    for k in list(spec_object.functions):
        if k in [
            "ceillog2",
            "floorlog2",
            "compute_merkle_proof",
        ]:
            del spec_object.functions[k]

    functions = reduce(
        lambda fns, builder: builder.implement_optimizations(fns), builders, spec_object.functions
    )
    functions_spec = "\n\n\n".join(functions.values())
    ordered_class_objects_spec = "\n\n\n".join(ordered_class_objects.values())

    # Access global dict of config vars for runtime configurables
    # Ignore variable between quotes and doubles quotes
    for name in spec_object.config_vars.keys():
        functions_spec = re.sub(rf"(?<!['\"])\b{name}\b(?!['\"])", "config." + name, functions_spec)
        ordered_class_objects_spec = re.sub(
            rf"(?<!['\"])\b{name}\b(?!['\"])", "config." + name, ordered_class_objects_spec
        )

    def format_config_var(name: str, vardef) -> str:
        if isinstance(vardef, list):
            # A special case for list of records.
            indent = " " * 4
            lines = [f"{name}=("]
            for d in vardef:
                line = indent * 2 + "frozendict({\n"
                for k, v in d.items():
                    line += indent * 3 + f'"{k}": {v},\n'
                line += indent * 2 + "}),"
                lines.append(line)
            lines.append(indent + "),")
            return "\n".join(lines)
        elif vardef.type_name is None:
            out = f"{name}={vardef.value},"
        else:
            out = f"{name}={vardef.type_name}({vardef.value}),"
        if vardef.comment is not None:
            out += f"  # {vardef.comment}"
        return out

    def format_config_var_param(value):
        if isinstance(value, list):
            # A special case for list of records.
            return "tuple[frozendict[str, Any], ...]"
        elif isinstance(value, VariableDefinition):
            return value.type_name if value.type_name is not None else "int"

    config_spec = "class Configuration(NamedTuple):\n"
    config_spec += "    PRESET_BASE: str\n"
    config_spec += "\n".join(
        f"    {k}: {format_config_var_param(v)}" for k, v in spec_object.config_vars.items()
    )
    config_spec += "\n\n\nconfig = Configuration(\n"
    config_spec += f'    PRESET_BASE="{preset_name}",\n'
    config_spec += "\n".join(
        "    " + format_config_var(k, v) for k, v in spec_object.config_vars.items()
    )
    config_spec += "\n)\n"

    def format_constant(name: str, vardef: VariableDefinition) -> str:
        if vardef.type_name is None:
            if vardef.type_hint is None:
                out = f"{name} = {vardef.value}"
            else:
                out = f"{name}: {vardef.type_hint} = {vardef.value}"
        else:
            out = f"{name} = {vardef.type_name}({vardef.value})"
        if vardef.comment is not None:
            out += f"  # {vardef.comment}"
        return out

    # Merge all constant objects
    hardcoded_ssz_dep_constants = reduce(
        lambda obj, builder: {**obj, **builder.hardcoded_ssz_dep_constants()}, builders, {}
    )
    hardcoded_func_dep_presets = reduce(
        lambda obj, builder: {**obj, **builder.hardcoded_func_dep_presets(spec_object)},
        builders,
        {},
    )
    # Concatenate all strings
    imports = reduce(
        lambda txt, builder: (txt + "\n\n" + builder.imports(preset_name)).strip("\n"), builders, ""
    )
    classes = reduce(
        lambda txt, builder: (txt + "\n\n" + builder.classes()).strip("\n"), builders, ""
    )
    preparations = reduce(
        lambda txt, builder: (txt + "\n\n" + builder.preparations()).strip("\n"), builders, ""
    )
    sundry_functions = reduce(
        lambda txt, builder: (txt + "\n\n" + builder.sundry_functions()).strip("\n"), builders, ""
    )
    # Keep engine from the most recent fork
    execution_engine_cls = reduce(
        lambda txt, builder: builder.execution_engine_cls() or txt, builders, ""
    )

    # Remove deprecated constants
    deprecate_constants = reduce(
        lambda obj, builder: obj.union(builder.deprecate_constants()), builders, set()
    )
    # constant_vars = {k: v for k, v in spec_object.constant_vars.items() if k not in deprecate_constants}
    filtered_ssz_dep_constants = {
        k: v for k, v in hardcoded_ssz_dep_constants.items() if k not in deprecate_constants
    }
    # Remove deprecated presets
    deprecate_presets = reduce(
        lambda obj, builder: obj.union(builder.deprecate_presets()), builders, set()
    )
    # preset_vars = {k: v for k, v in spec_object.constant_vars.items() if k not in deprecate_constants}
    filtered_hardcoded_func_dep_presets = {
        k: v for k, v in hardcoded_func_dep_presets.items() if k not in deprecate_presets
    }

    constant_vars_spec = "# Constant vars\n" + "\n".join(
        format_constant(k, v) for k, v in spec_object.constant_vars.items()
    )
    preset_dep_constant_vars_spec = "# Preset computed constants\n" + "\n".join(
        format_constant(k, v) for k, v in spec_object.preset_dep_constant_vars.items()
    )
    preset_vars_spec = "# Preset vars\n" + "\n".join(
        format_constant(k, v) for k, v in spec_object.preset_vars.items()
    )
    ssz_dep_constants = "\n".join(
        map(lambda x: f"{x} = {hardcoded_ssz_dep_constants[x]}", hardcoded_ssz_dep_constants)
    )
    ssz_dep_constants_verification = "\n".join(
        map(
            lambda x: f"assert {x} == {spec_object.ssz_dep_constants[x]}",
            filtered_ssz_dep_constants,
        )
    )
    func_dep_presets_verification = "\n".join(
        map(
            lambda x: f"assert {x} == {spec_object.func_dep_presets[x]}  # noqa: E501",
            filtered_hardcoded_func_dep_presets,
        )
    )
    spec_strs = [
        imports,
        preparations,
        f"fork = '{fork}'\n",
        # The helper functions that some SSZ containers require. Need to be defined before `custom_type_dep_constants`
        CONSTANT_DEP_SUNDRY_CONSTANTS_FUNCTIONS,
        # The constants that some SSZ containers require. Need to be defined before `constants_spec`
        ssz_dep_constants,
        new_type_definitions,
        constant_vars_spec,
        # The presets that some SSZ types require.
        preset_vars_spec,
        preset_dep_constant_vars_spec,
        config_spec,
        # Custom classes which are not required to be SSZ containers.
        classes,
        ordered_class_objects_spec,
        protocols_spec,
        functions_spec,
        sundry_functions,
        execution_engine_cls,
        # Since some constants are hardcoded in setup.py, the following assertions verify that the hardcoded constants are
        # as same as the spec definition.
        ssz_dep_constants_verification,
        func_dep_presets_verification,
    ]
    return "\n\n\n".join([str.strip("\n") for str in spec_strs if str]) + "\n"


def combine_protocols(
    old_protocols: dict[str, ProtocolDefinition], new_protocols: dict[str, ProtocolDefinition]
) -> dict[str, ProtocolDefinition]:
    for key, value in new_protocols.items():
        if key not in old_protocols:
            old_protocols[key] = value
        else:
            functions = combine_dicts(old_protocols[key].functions, value.functions)
            old_protocols[key] = ProtocolDefinition(functions=functions)
    return old_protocols


T = TypeVar("T")


def combine_dicts(old_dict: dict[str, T], new_dict: dict[str, T]) -> dict[str, T]:
    return {**old_dict, **new_dict}


ignored_dependencies = [
    "bit",
    "Bitlist",
    "Bitvector",
    "boolean",
    "byte",
    "ByteList",
    "bytes",
    "Bytes1",
    "Bytes20",
    "Bytes31",
    "Bytes32",
    "Bytes4",
    "Bytes48",
    "Bytes8",
    "Bytes96",
    "ByteVector",
    "ceillog2",
    "Container",
    "defaultdict",
    "DefaultDict",
    "dict",
    "Dict",
    "field",
    "floorlog2",
    "List",
    "Optional",
    "ProgressiveBitlist",
    "ProgressiveList",
    "Sequence",
    "Set",
    "Tuple",
    "uint128",
    "uint16",
    "uint256",
    "uint32",
    "uint64",
    "uint8",
    "Vector",
]


def dependency_order_class_objects(objects: dict[str, str], custom_types: dict[str, str]) -> None:
    """
    Determines which SSZ Object is dependent on which other and orders them appropriately
    """
    items = list(objects.items())
    for key, value in items:
        dependencies = []
        for i, line in enumerate(value.split("\n")):
            if i == 0:
                match = re.match(r".+\((.+)\):", line)
            else:
                match = re.match(r"\s+\w+: (.+)", line)
            if not match:
                continue  # skip whitespace etc.
            line = match.group(1)
            if "#" in line:
                line = line[: line.index("#")]  # strip of comment
            dependencies.extend(
                re.findall(r"(\w+)", line)
            )  # catch all legible words, potential dependencies
        dependencies = filter(
            lambda x: "_" not in x and x.upper() != x, dependencies
        )  # filter out constants
        dependencies = filter(lambda x: x not in ignored_dependencies, dependencies)
        dependencies = filter(lambda x: x not in custom_types, dependencies)
        for dep in dependencies:
            key_list = list(objects.keys())
            for item in [dep, key] + key_list[key_list.index(dep) + 1 :]:
                objects[item] = objects.pop(item)


def combine_ssz_objects(old_objects: dict[str, str], new_objects: dict[str, str]) -> dict[str, str]:
    """
    Takes in old spec and new spec ssz objects, combines them,
    and returns the newer versions of the objects in dependency order.
    """
    for key, value in new_objects.items():
        old_objects[key] = value
    return old_objects


def combine_spec_objects(spec0: SpecObject, spec1: SpecObject) -> SpecObject:
    """
    Takes in two spec variants (as tuples of their objects) and combines them using the appropriate combiner function.
    """
    protocols = combine_protocols(spec0.protocols, spec1.protocols)
    functions = combine_dicts(spec0.functions, spec1.functions)
    custom_types = combine_dicts(spec0.custom_types, spec1.custom_types)
    constant_vars = combine_dicts(spec0.constant_vars, spec1.constant_vars)
    preset_dep_constant_vars = combine_dicts(
        spec0.preset_dep_constant_vars, spec1.preset_dep_constant_vars
    )
    preset_vars = combine_dicts(spec0.preset_vars, spec1.preset_vars)
    config_vars = combine_dicts(spec0.config_vars, spec1.config_vars)
    ssz_dep_constants = combine_dicts(spec0.ssz_dep_constants, spec1.ssz_dep_constants)
    func_dep_presets = combine_dicts(spec0.func_dep_presets, spec1.func_dep_presets)
    ssz_objects = combine_ssz_objects(spec0.ssz_objects, spec1.ssz_objects)
    dataclasses = combine_dicts(spec0.dataclasses, spec1.dataclasses)
    return SpecObject(
        functions=functions,
        protocols=protocols,
        custom_types=custom_types,
        constant_vars=constant_vars,
        preset_dep_constant_vars=preset_dep_constant_vars,
        preset_vars=preset_vars,
        config_vars=config_vars,
        ssz_dep_constants=ssz_dep_constants,
        func_dep_presets=func_dep_presets,
        ssz_objects=ssz_objects,
        dataclasses=dataclasses,
    )


def finalized_spec_object(spec_object: SpecObject) -> SpecObject:
    all_config_dependencies = {
        vardef.type_name or vardef.type_hint
        for vardef in (
            spec_object.constant_vars
            | spec_object.preset_dep_constant_vars
            | spec_object.preset_vars
            | spec_object.config_vars
        ).values()
        if (vardef.type_name or vardef.type_hint) is not None
    }

    custom_types = {}
    ssz_objects = spec_object.ssz_objects
    for name, value in spec_object.custom_types.items():
        if any(k in name for k in all_config_dependencies):
            custom_types[name] = value
        else:
            ssz_objects[name] = gen_new_type_definition(name, value)

    return SpecObject(
        functions=spec_object.functions,
        protocols=spec_object.protocols,
        custom_types=custom_types,
        constant_vars=spec_object.constant_vars,
        preset_dep_constant_vars=spec_object.preset_dep_constant_vars,
        preset_vars=spec_object.preset_vars,
        config_vars=spec_object.config_vars,
        ssz_dep_constants=spec_object.ssz_dep_constants,
        func_dep_presets=spec_object.func_dep_presets,
        ssz_objects=ssz_objects,
        dataclasses=spec_object.dataclasses,
    )


def parse_config_vars(conf: dict[str, str]) -> dict[str, str | list[dict[str, str]]]:
    """
    Parses a dict of basic str/int/list types into a dict for insertion into the spec code.
    """
    out: dict[str, str | list[dict[str, str]]] = dict()
    for k, v in conf.items():
        if isinstance(v, list):
            # A special case for list of records
            out[k] = v
        elif isinstance(v, str) and (
            v.startswith("0x") or k == "PRESET_BASE" or k == "CONFIG_NAME"
        ):
            # Represent byte data with string, to avoid misinterpretation as big-endian int.
            # Everything except PRESET_BASE and CONFIG_NAME is either byte data or an integer.
            out[k] = f"'{v}'"
        else:
            out[k] = str(int(v))
    return out
