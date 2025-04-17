import re
from typing import TypeVar, Dict, Union, List
import textwrap
from functools import reduce

from .constants import CONSTANT_DEP_SUNDRY_CONSTANTS_FUNCTIONS
from .spec_builders import spec_builders
from .md_doc_paths import PREVIOUS_FORK_OF
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
        value.startswith(('ByteVector'))
        or (value.startswith(('Vector')) and any(k in value for k in ['ceillog2', 'floorlog2']))
    )


def make_function_abstract(protocol_def: ProtocolDefinition, key: str):
    function = protocol_def.functions[key].split('"""')
    protocol_def.functions[key] = function[0] + "..."


def objects_to_spec(preset_name: str,
                    spec_object: SpecObject,
                    fork: str,
                    ordered_class_objects: Dict[str, str]) -> str:
    """
    Given all the objects that constitute a spec, combine them into a single pyfile.
    """
    def gen_new_type_definitions(custom_types: Dict[str, str]) -> str:
        return (
            '\n\n'.join(
                [
                    f"class {key}({value}):\n    pass\n" if not requires_mypy_type_ignore(value)
                    else f"class {key}({value}):  # type: ignore\n    pass\n"
                    for key, value in custom_types.items()
                ]
            )
        )

    new_type_definitions = gen_new_type_definitions(spec_object.custom_types)
    preset_dep_new_type_definitions = gen_new_type_definitions(spec_object.preset_dep_custom_types)

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
            fn_source = fn_source.replace("self: "+protocol_name, "self")
            protocol += "\n\n" + textwrap.indent(fn_source, "    ")
        return protocol

    protocols_spec = '\n\n\n'.join(format_protocol(k, v) for k, v in spec_object.protocols.items())
    for k in list(spec_object.functions):
        if k in [
            "ceillog2",
            "floorlog2",
            "compute_merkle_proof",
        ]:
            del spec_object.functions[k]

    functions = reduce(lambda fns, builder: builder.implement_optimizations(fns), builders, spec_object.functions)
    functions_spec = '\n\n\n'.join(functions.values())

    # Access global dict of config vars for runtime configurables
    # Ignore variable between quotes and doubles quotes
    for name in spec_object.config_vars.keys():
        functions_spec = re.sub(r"(?<!['\"])\b%s\b(?!['\"])" % name, "config." + name, functions_spec)

    def format_config_var(name: str, vardef) -> str:
        if isinstance(vardef, list):
            # A special case for list of records.
            indent = " " * 4
            lines = [f"{name}=("]
            for d in vardef:
                line = indent*2 + "frozendict({\n"
                for k, v in d.items():
                    line += indent * 3 + f'"{k}": {v},\n'
                line += indent*2 + "}),"
                lines.append(line)
            lines.append(indent + "),")
            return "\n".join(lines)
        elif vardef.type_name is None:
            out = f'{name}={vardef.value},'
        else:
            out = f'{name}={vardef.type_name}({vardef.value}),'
        if vardef.comment is not None:
            out += f'  # {vardef.comment}'
        return out

    def format_config_var_param(value):
        if isinstance(value, list):
            # A special case for list of records.
            return "tuple[frozendict[str, Any], ...]"
        elif isinstance(value, VariableDefinition):
            return value.type_name if value.type_name is not None else "int"

    config_spec = 'class Configuration(NamedTuple):\n'
    config_spec += '    PRESET_BASE: str\n'
    config_spec += '\n'.join(f'    {k}: {format_config_var_param(v)}' for k, v in spec_object.config_vars.items())
    config_spec += '\n\n\nconfig = Configuration(\n'
    config_spec += f'    PRESET_BASE="{preset_name}",\n'
    config_spec += '\n'.join('    ' + format_config_var(k, v) for k, v in spec_object.config_vars.items())
    config_spec += '\n)\n'

    def format_constant(name: str, vardef: VariableDefinition) -> str:
        if vardef.type_name is None:
            if vardef.type_hint is None:
                out = f'{name} = {vardef.value}'
            else:
                out = f'{name}: {vardef.type_hint} = {vardef.value}'
        else:
            out = f'{name} = {vardef.type_name}({vardef.value})'
        if vardef.comment is not None:
            out += f'  # {vardef.comment}'
        return out

    # Merge all constant objects
    hardcoded_ssz_dep_constants =         reduce(lambda obj, builder: {**obj, **builder.hardcoded_ssz_dep_constants()}, builders, {})
    hardcoded_func_dep_presets = reduce(lambda obj, builder: {**obj, **builder.hardcoded_func_dep_presets(spec_object)}, builders, {})
    # Concatenate all strings
    imports =              reduce(lambda txt, builder: (txt + "\n\n" + builder.imports(preset_name)  ).strip("\n"), builders, "")
    classes =              reduce(lambda txt, builder: (txt + "\n\n" + builder.classes()             ).strip("\n"), builders, "")
    preparations =         reduce(lambda txt, builder: (txt + "\n\n" + builder.preparations()        ).strip("\n"), builders, "")
    sundry_functions =     reduce(lambda txt, builder: (txt + "\n\n" + builder.sundry_functions()    ).strip("\n"), builders, "")
    # Keep engine from the most recent fork
    execution_engine_cls = reduce(lambda txt, builder: builder.execution_engine_cls() or txt, builders, "")

    # Remove deprecated constants
    deprecate_constants = reduce(lambda obj, builder: obj.union(builder.deprecate_constants()), builders, set())
    # constant_vars = {k: v for k, v in spec_object.constant_vars.items() if k not in deprecate_constants}
    filtered_ssz_dep_constants = {k: v for k, v in hardcoded_ssz_dep_constants.items() if k not in deprecate_constants}
    # Remove deprecated presets
    deprecate_presets = reduce(lambda obj, builder: obj.union(builder.deprecate_presets()), builders, set())
    # preset_vars = {k: v for k, v in spec_object.constant_vars.items() if k not in deprecate_constants}
    filtered_hardcoded_func_dep_presets = {k: v for k, v in hardcoded_func_dep_presets.items() if k not in deprecate_presets}

    constant_vars_spec = '# Constant vars\n' + '\n'.join(format_constant(k, v) for k, v in spec_object.constant_vars.items())
    preset_dep_constant_vars_spec = '# Preset computed constants\n' + '\n'.join(format_constant(k, v) for k, v in spec_object.preset_dep_constant_vars.items())
    preset_vars_spec = '# Preset vars\n' + '\n'.join(format_constant(k, v) for k, v in spec_object.preset_vars.items())
    ordered_class_objects_spec = '\n\n\n'.join(ordered_class_objects.values())
    ssz_dep_constants = '\n'.join(map(lambda x: '%s = %s' % (x, hardcoded_ssz_dep_constants[x]), hardcoded_ssz_dep_constants))
    ssz_dep_constants_verification = '\n'.join(map(lambda x: 'assert %s == %s' % (x, spec_object.ssz_dep_constants[x]), filtered_ssz_dep_constants))
    func_dep_presets_verification = '\n'.join(map(lambda x: 'assert %s == %s  # noqa: E501' % (x, spec_object.func_dep_presets[x]), filtered_hardcoded_func_dep_presets))
    spec_strs = [
        imports,
        preparations,
        f"fork = \'{fork}\'\n",
        # The helper functions that some SSZ containers require. Need to be defined before `custom_type_dep_constants`
        CONSTANT_DEP_SUNDRY_CONSTANTS_FUNCTIONS,
        # The constants that some SSZ containers require. Need to be defined before `constants_spec`
        ssz_dep_constants,
        new_type_definitions,
        constant_vars_spec,
        # The presets that some SSZ types require. Need to be defined before `preset_dep_new_type_definitions`
        preset_vars_spec,
        preset_dep_constant_vars_spec,
        preset_dep_new_type_definitions,
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
    return "\n\n\n".join([str.strip("\n") for str in spec_strs if str]) +  "\n"


def combine_protocols(old_protocols: Dict[str, ProtocolDefinition],
                      new_protocols: Dict[str, ProtocolDefinition]) -> Dict[str, ProtocolDefinition]:
    for key, value in new_protocols.items():
        if key not in old_protocols:
            old_protocols[key] = value
        else:
            functions = combine_dicts(old_protocols[key].functions, value.functions)
            old_protocols[key] = ProtocolDefinition(functions=functions)
    return old_protocols


T = TypeVar('T')


def combine_dicts(old_dict: Dict[str, T], new_dict: Dict[str, T]) -> Dict[str, T]:
    return {**old_dict, **new_dict}


ignored_dependencies = [
    'bit', 'boolean', 'Vector', 'List', 'Container', 'BLSPubkey', 'BLSSignature',
    'Bytes1', 'Bytes4', 'Bytes8', 'Bytes20', 'Bytes31', 'Bytes32', 'Bytes48', 'Bytes96', 'Bitlist', 'Bitvector',
    'uint8', 'uint16', 'uint32', 'uint64', 'uint128', 'uint256',
    'bytes', 'byte', 'ByteList', 'ByteVector',
    'Dict', 'dict', 'field', 'ceillog2', 'floorlog2', 'Set',
    'Optional', 'Sequence', 'Tuple',
]


def dependency_order_class_objects(objects: Dict[str, str], custom_types: Dict[str, str]) -> None:
    """
    Determines which SSZ Object is dependent on which other and orders them appropriately
    """
    items = list(objects.items())
    for key, value in items:
        dependencies = []
        for line in value.split('\n'):
            if not re.match(r'\s+\w+: .+', line):
                continue  # skip whitespace etc.
            line = line[line.index(':') + 1:]  # strip of field name
            if '#' in line:
                line = line[:line.index('#')]  # strip of comment
            dependencies.extend(re.findall(r'(\w+)', line))  # catch all legible words, potential dependencies
        dependencies = filter(lambda x: '_' not in x and x.upper() != x, dependencies)  # filter out constants
        dependencies = filter(lambda x: x not in ignored_dependencies, dependencies)
        dependencies = filter(lambda x: x not in custom_types, dependencies)
        for dep in dependencies:
            key_list = list(objects.keys())
            for item in [dep, key] + key_list[key_list.index(dep)+1:]:
                objects[item] = objects.pop(item)

def combine_ssz_objects(old_objects: Dict[str, str], new_objects: Dict[str, str]) -> Dict[str, str]:
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
    preset_dep_custom_types = combine_dicts(spec0.preset_dep_custom_types, spec1.preset_dep_custom_types)
    constant_vars = combine_dicts(spec0.constant_vars, spec1.constant_vars)
    preset_dep_constant_vars = combine_dicts(spec0.preset_dep_constant_vars, spec1.preset_dep_constant_vars)
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
        preset_dep_custom_types=preset_dep_custom_types,
        constant_vars=constant_vars,
        preset_dep_constant_vars=preset_dep_constant_vars,
        preset_vars=preset_vars,
        config_vars=config_vars,
        ssz_dep_constants=ssz_dep_constants,
        func_dep_presets=func_dep_presets,
        ssz_objects=ssz_objects,
        dataclasses=dataclasses,
    )


def parse_config_vars(conf: Dict[str, str]) -> Dict[str, Union[str, List[Dict[str, str]]]]:
    """
    Parses a dict of basic str/int/list types into a dict for insertion into the spec code.
    """
    out: Dict[str, Union[str, List[Dict[str, str]]]] = dict()
    for k, v in conf.items():
        if isinstance(v, list):
            # A special case for list of records
            out[k] = v
        elif isinstance(v, str) and (v.startswith("0x") or k == "PRESET_BASE" or k == "CONFIG_NAME"):
            # Represent byte data with string, to avoid misinterpretation as big-endian int.
            # Everything except PRESET_BASE and CONFIG_NAME is either byte data or an integer.
            out[k] = f"'{v}'"
        else:
            out[k] = str(int(v))
    return out
