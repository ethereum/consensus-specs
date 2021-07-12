from setuptools import setup, find_packages, Command
from setuptools.command.build_py import build_py
from distutils import dir_util
from distutils.util import convert_path
from pathlib import Path
import os
import re
import string
import textwrap
from typing import Dict, NamedTuple, List, Sequence, Optional, TypeVar, Tuple
import ast


# NOTE: have to programmatically include third-party dependencies in `setup.py`.
RUAMEL_YAML_VERSION = "ruamel.yaml==0.16.5"
try:
    import ruamel.yaml  # noqa: F401
except ImportError:
    import pip
    pip.main(["install", RUAMEL_YAML_VERSION])

from ruamel.yaml import YAML

MARKO_VERSION = "marko==1.0.2"
try:
    import marko  # noqa: F401
except ImportError:
    import pip
    pip.main(["install", MARKO_VERSION])

from marko.block import Heading, FencedCode, LinkRefDef, BlankLine
from marko.inline import CodeSpan
from marko.ext.gfm import gfm
from marko.ext.gfm.elements import Table


# Definitions in context.py
PHASE0 = 'phase0'
ALTAIR = 'altair'
MERGE = 'merge'

specs = [PHASE0, ALTAIR, MERGE]


class ProtocolDefinition(NamedTuple):
    # just function definitions currently. May expand with configuration vars in future.
    functions: Dict[str, str]


class VariableDefinition(NamedTuple):
    type_name: Optional[str]
    value: str
    comment: Optional[str]  # e.g. "noqa: E501"


class SpecObject(NamedTuple):
    functions: Dict[str, str]
    protocols: Dict[str, ProtocolDefinition]
    custom_types: Dict[str, str]
    config_vars: Dict[str, VariableDefinition]
    vars: Dict[str, VariableDefinition]
    ssz_objects: Dict[str, str]
    dataclasses: Dict[str, str]


def _get_name_from_heading(heading: Heading) -> Optional[str]:
    last_child = heading.children[-1]
    if isinstance(last_child, CodeSpan):
        return last_child.children
    return None


def _get_source_from_code_block(block: FencedCode) -> str:
    return block.children[0].children.strip()


def _get_function_name_from_source(source: str) -> str:
    fn = ast.parse(source).body[0]
    assert isinstance(fn, ast.FunctionDef)
    return fn.name


def _get_self_type_from_source(source: str) -> Optional[str]:
    fn = ast.parse(source).body[0]
    assert isinstance(fn, ast.FunctionDef)
    args = fn.args.args
    if len(args) == 0:
        return None
    if args[0].arg != 'self':
        return None
    if args[0].annotation is None:
        return None
    assert isinstance(args[0].annotation, ast.Name)
    return args[0].annotation.id


def _get_class_info_from_source(source: str) -> Tuple[str, Optional[str]]:
    class_def = ast.parse(source).body[0]
    assert isinstance(class_def, ast.ClassDef)
    base = class_def.bases[0]
    if isinstance(base, ast.Name):
        parent_class: Optional[str] = base.id
    else:
        # NOTE: SSZ definition derives from earlier phase...
        # e.g. `phase0.SignedBeaconBlock`
        # TODO: check for consistency with other phases
        parent_class = None
    return class_def.name, parent_class


def _is_constant_id(name: str) -> bool:
    if name[0] not in string.ascii_uppercase + '_':
        return False
    return all(map(lambda c: c in string.ascii_uppercase + '_' + string.digits, name[1:]))


ETH2_SPEC_COMMENT_PREFIX = "eth2spec:"


def _get_eth2_spec_comment(child: LinkRefDef) -> Optional[str]:
    _, _, title = child._parse_info
    if not (title[0] == "(" and title[len(title) - 1] == ")"):
        return None
    title = title[1:len(title) - 1]
    if not title.startswith(ETH2_SPEC_COMMENT_PREFIX):
        return None
    return title[len(ETH2_SPEC_COMMENT_PREFIX):].strip()


def _parse_value(name: str, typed_value: str) -> VariableDefinition:
    comment = None
    if name == "BLS12_381_Q":
        comment = "noqa: E501"

    typed_value = typed_value.strip()
    if '(' not in typed_value or typed_value.startswith("get_generalized_index"):
        return VariableDefinition(type_name=None, value=typed_value, comment=comment)
    i = typed_value.index('(')
    type_name = typed_value[:i]

    return VariableDefinition(type_name=type_name, value=typed_value[i + 1:-1], comment=comment)


def get_spec(file_name: Path, preset: Dict[str, str], config: Dict[str, str]) -> SpecObject:
    functions: Dict[str, str] = {}
    protocols: Dict[str, ProtocolDefinition] = {}
    config_vars: Dict[str, VariableDefinition] = {}
    vars: Dict[str, VariableDefinition] = {}
    ssz_objects: Dict[str, str] = {}
    dataclasses: Dict[str, str] = {}
    custom_types: Dict[str, str] = {}

    with open(file_name) as source_file:
        document = gfm.parse(source_file.read())

    current_name = None
    should_skip = False
    for child in document.children:
        if isinstance(child, BlankLine):
            continue
        if should_skip:
            should_skip = False
            continue
        if isinstance(child, Heading):
            current_name = _get_name_from_heading(child)
        elif isinstance(child, FencedCode):
            if child.lang != "python":
                continue
            source = _get_source_from_code_block(child)
            if source.startswith("def"):
                current_name = _get_function_name_from_source(source)
                self_type_name = _get_self_type_from_source(source)
                function_def = "\n".join(line.rstrip() for line in source.splitlines())
                if self_type_name is None:
                    functions[current_name] = function_def
                else:
                    if self_type_name not in protocols:
                        protocols[self_type_name] = ProtocolDefinition(functions={})
                    protocols[self_type_name].functions[current_name] = function_def
            elif source.startswith("@dataclass"):
                class_name, _ = _get_class_info_from_source(source)
                assert class_name == current_name
                dataclasses[class_name] = "\n".join(line.rstrip() for line in source.splitlines())
            elif source.startswith("class"):
                class_name, parent_class = _get_class_info_from_source(source)
                # check consistency with spec
                assert class_name == current_name
                if parent_class:
                    assert parent_class == "Container"
                # NOTE: trim whitespace from spec
                ssz_objects[current_name] = "\n".join(line.rstrip() for line in source.splitlines())
            else:
                raise Exception("unrecognized python code element")
        elif isinstance(child, Table):
            for row in child.children:
                cells = row.children
                if len(cells) >= 2:
                    name_cell = cells[0]
                    name = name_cell.children[0].children

                    value_cell = cells[1]
                    value = value_cell.children[0].children
                    if isinstance(value, list):
                        # marko parses `**X**` as a list containing a X
                        value = value[0].children

                    if not _is_constant_id(name):
                        # Check for short type declarations
                        if (value.startswith("uint") or value.startswith("Bytes")
                                or value.startswith("ByteList") or value.startswith("Union")):
                            custom_types[name] = value
                        continue

                    value_def = _parse_value(name, value)
                    if name in preset:
                        vars[name] = VariableDefinition(value_def.type_name, preset[name], value_def.comment)
                    elif name in config:
                        config_vars[name] = VariableDefinition(value_def.type_name, config[name], value_def.comment)
                    else:
                        vars[name] = value_def

        elif isinstance(child, LinkRefDef):
            comment = _get_eth2_spec_comment(child)
            if comment == "skip":
                should_skip = True

    return SpecObject(
        functions=functions,
        protocols=protocols,
        custom_types=custom_types,
        config_vars=config_vars,
        vars=vars,
        ssz_objects=ssz_objects,
        dataclasses=dataclasses,
    )


def is_spec_defined_type(value: str) -> bool:
    return value.startswith('ByteList') or value.startswith('Union')


def objects_to_spec(preset_name: str,
                    spec_object: SpecObject,
                    fork: str,
                    ordered_class_objects: Dict[str, str],
                    spec_dot_yaml: Dict,
                    python_prefixes: List[str],
                    python_suffixes: List[str]) -> str:
    """
    Given all the objects that constitute a spec, combine them into a single pyfile.
    """
    new_type_definitions = (
        '\n\n'.join(
            [
                f"class {key}({value}):\n    pass\n"
                for key, value in spec_object.custom_types.items()
                if not is_spec_defined_type(value)
            ]
        )
        + ('\n\n' if len([key for key, value in spec_object.custom_types.items()
                          if is_spec_defined_type(value)]) > 0 else '')
        + '\n\n'.join(
            [
                f"{key} = {value}\n"
                for key, value in spec_object.custom_types.items()
                if is_spec_defined_type(value)
            ]
        )
    )

    def format_protocol(protocol_name: str, protocol_def: ProtocolDefinition) -> str:
        protocol = f"class {protocol_name}(Protocol):"
        for fn_source in protocol_def.functions.values():
            fn_source = fn_source.replace("self: " + protocol_name, "self")
            protocol += "\n\n" + textwrap.indent(fn_source, "    ")
        return protocol

    protocols_spec = '\n\n\n'.join(format_protocol(k, v) for k, v in spec_object.protocols.items())
    functions_spec = '\n\n\n'.join(spec_object.functions.values())

    # Access global dict of config vars for runtime configurables
    for name in spec_object.config_vars.keys():
        functions_spec = functions_spec.replace(name, 'config.' + name)

    def format_config_var(name: str, vardef: VariableDefinition) -> str:
        if vardef.type_name is None:
            out = f'{name}={vardef.value},'
        else:
            out = f'{name}={vardef.type_name}({vardef.value}),'
        if vardef.comment is not None:
            out += f'  # {vardef.comment}'
        return out

    config_spec = 'class Configuration(NamedTuple):\n'
    config_spec += '    PRESET_BASE: str\n'
    config_spec += '\n'.join(f'    {k}: {v.type_name if v.type_name is not None else "int"}'
                             for k, v in spec_object.config_vars.items())
    config_spec += '\n\n\nconfig = Configuration(\n'
    config_spec += f'    PRESET_BASE="{preset_name}",\n'
    config_spec += '\n'.join('    ' + format_config_var(k, v) for k, v in spec_object.config_vars.items())
    config_spec += '\n)\n'

    def format_constant(name: str, vardef: VariableDefinition) -> str:
        if vardef.type_name is None:
            out = f'{name} = {vardef.value}'
        else:
            out = f'{name} = {vardef.type_name}({vardef.value})'
        if vardef.comment is not None:
            out += f'  # {vardef.comment}'
        return out

    predefined_vars = spec_dot_yaml.get("predefined_vars", {})

    vars_spec = '\n'.join(format_constant(k, v) for k, v in spec_object.vars.items() if k not in predefined_vars)
    predefined_vars_spec = '\n'.join(f'{k} = {v}' for k, v in predefined_vars.items())
    predefined_vars_check = '\n'.join(map(lambda x: 'assert %s == %s' % (x, spec_object.vars[x].value),
                                      predefined_vars.keys()))
    ordered_class_objects_spec = '\n\n\n'.join(ordered_class_objects.values())
    spec = (f'PRESET_NAME = "{preset_name}"\n\n'
            + '\n\n'.join(python_prefixes)
            + '\n\n' + f"fork = \'{fork}\'"
            + ('\n\n' + predefined_vars_spec if predefined_vars_spec != '' else '')
            + '\n\n\n' + new_type_definitions
            + '\n\n' + vars_spec
            + '\n\n\n' + config_spec
            + '\n\n' + ordered_class_objects_spec
            + ('\n\n\n' + protocols_spec if protocols_spec != '' else '')
            + '\n\n\n' + functions_spec
            + ('\n\n\n' + predefined_vars_check if predefined_vars_check != '' else '')
            + '\n\n\n' + '\n\n'.join(python_suffixes)
            )
    return spec


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
    'Bytes1', 'Bytes4', 'Bytes20', 'Bytes32', 'Bytes48', 'Bytes96', 'Bitlist', 'Bitvector',
    'uint8', 'uint16', 'uint32', 'uint64', 'uint128', 'uint256',
    'bytes', 'byte', 'ByteList', 'ByteVector',
    'Dict', 'dict', 'field', 'ceillog2', 'floorlog2', 'Set',
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
        dependencies = list(filter(lambda x: '_' not in x and x.upper() != x, dependencies))  # filter out constants
        dependencies = list(filter(lambda x: x not in ignored_dependencies, dependencies))
        dependencies = list(filter(lambda x: x not in custom_types, dependencies))
        for dep in dependencies:
            key_list = list(objects.keys())
            for item in [dep, key] + key_list[key_list.index(dep) + 1:]:
                objects[item] = objects.pop(item)


def combine_spec_objects(spec0: SpecObject, spec1: SpecObject) -> SpecObject:
    """
    Takes in two spec variants (as tuples of their objects) and combines them using the appropriate combiner function.
    """
    protocols = combine_protocols(spec0.protocols, spec1.protocols)
    functions = combine_dicts(spec0.functions, spec1.functions)
    custom_types = combine_dicts(spec0.custom_types, spec1.custom_types)
    vars = combine_dicts(spec0.vars, spec1.vars)
    config_vars = combine_dicts(spec0.config_vars, spec1.config_vars)
    ssz_objects = combine_dicts(spec0.ssz_objects, spec1.ssz_objects)
    dataclasses = combine_dicts(spec0.dataclasses, spec1.dataclasses)
    return SpecObject(
        functions=functions,
        protocols=protocols,
        custom_types=custom_types,
        vars=vars,
        config_vars=config_vars,
        ssz_objects=ssz_objects,
        dataclasses=dataclasses,
    )


def parse_config_vars(conf: Dict[str, str]) -> Dict[str, str]:
    """
    Parses a dict of basic str/int/list types into a dict for insertion into the spec code.
    """
    out: Dict[str, str] = dict()
    for k, v in conf.items():
        if isinstance(v, str) and (v.startswith("0x") or k == 'PRESET_BASE'):
            # Represent byte data with string, to avoid misinterpretation as big-endian int.
            # Everything is either byte data or an integer, with PRESET_BASE as one exception.
            out[k] = f"'{v}'"
        else:
            out[k] = str(int(v))
    return out


def load_preset(preset_files: Sequence[Path]) -> Dict[str, str]:
    """
    Loads the a directory of preset files, merges the result into one preset.
    """
    preset: Dict[str, str] = {}
    for fork_file in preset_files:
        yaml = YAML(typ='base')
        fork_preset: dict = yaml.load(fork_file)
        if fork_preset is None:  # for empty YAML files
            continue
        if not set(fork_preset.keys()).isdisjoint(preset.keys()):
            duplicates = set(fork_preset.keys()).intersection(set(preset.keys()))
            raise Exception(f"duplicate config var(s) in preset files: {', '.join(duplicates)}")
        preset.update(fork_preset)
    assert preset != {}
    return parse_config_vars(preset)


def load_config(config_path: Path) -> Dict[str, str]:
    """
    Loads the given configuration file.
    """
    yaml = YAML(typ='base')
    config_data = yaml.load(config_path)
    return parse_config_vars(config_data)


def build_spec(preset_name: str, fork: str, source_files: Sequence[Path], preset_files: Sequence[Path],
               config_file: Path, spec_dir: Path, spec_dot_yaml: Dict) -> str:
    preset = load_preset(preset_files)
    config = load_config(config_file)
    all_specs = [get_spec(spec, preset, config) for spec in source_files]

    python_prefixes = []
    for path in spec_dot_yaml.get("py_prefix", []):
        with open(os.path.join(spec_dir, path)) as file:
            python_prefixes.append(file.read())

    python_suffixes = []
    for path in spec_dot_yaml.get("py_suffix", []):
        with open(os.path.join(spec_dir, path)) as file:
            python_suffixes.append(file.read())

    spec_object = SpecObject(
        functions={},
        protocols={},
        custom_types={},
        vars={},
        config_vars={},
        ssz_objects={},
        dataclasses={},
    )
    for value in all_specs:
        spec_object = combine_spec_objects(spec_object, value)

    for function in spec_dot_yaml.get("overridden_functions", []):
        if function in spec_object.functions:
            del spec_object.functions[function]

    class_objects = {**spec_object.ssz_objects, **spec_object.dataclasses}
    dependency_order_class_objects(class_objects, spec_object.custom_types)

    return objects_to_spec(preset_name, spec_object, fork, class_objects, spec_dot_yaml,
                           python_prefixes, python_suffixes)


class BuildTarget(NamedTuple):
    name: str
    preset_paths: List[Path]
    config_path: Path


class PySpecCommand(Command):
    """Convert spec markdown files to a spec python file"""

    description = "Convert spec markdown files to a spec python file"

    spec_fork: str
    md_doc_paths: List[Path]
    parsed_md_doc_paths: List[str]
    build_targets: str
    parsed_build_targets: List[BuildTarget]
    out_dir: str
    spec_dir: Optional[Path]

    # The format is (long option, short option, description).
    user_options = [
        ('spec-fork=', None, "Spec fork to tag build with. Used to select spec-dir default."),
        ('build-targets=', None, "Names, directory paths of compile-time presets, and default config paths."),
        ('out-dir=', None, "Output directory to write spec package to"),
        ('spec-dir=', None, "Directory to find specification in")
    ]

    def initialize_options(self) -> None:
        """Set default values for options."""
        # Each user option must be listed here with their default value.
        self.spec_fork = PHASE0
        self.out_dir = 'pyspec_output'
        self.build_targets = """
                minimal:presets/minimal:configs/minimal.yaml
                mainnet:presets/mainnet:configs/mainnet.yaml
        """
        self.spec_dir = None

    def finalize_options(self) -> None:
        """Post-process options."""
        if self.spec_dir is None:
            if self.spec_fork == PHASE0:
                self.spec_dir = Path("specs/phase0/")
            elif self.spec_fork == ALTAIR:
                self.spec_dir = Path("specs/altair/")
            elif self.spec_fork == MERGE:
                self.spec_dir = Path("specs/merge/")
            else:
                raise Exception('spec dir not specified and spec fork "%s" is unknown', self.spec_fork)
        yaml = YAML(typ='base')
        self.spec_dot_yaml = yaml.load(self.spec_dir / "spec.yaml")
        self.md_doc_paths = [self.spec_dir / path for path in self.spec_dot_yaml["md_files"]]

        for filename in self.md_doc_paths:
            if not os.path.exists(filename):
                raise Exception('Pyspec markdown input file "%s" does not exist.' % filename)

        self.parsed_build_targets = []
        for target in self.build_targets.split():
            target = target.strip()
            data = target.split(':')
            if len(data) != 3:
                raise Exception('invalid target, expected "name:preset_dir:config_file" format, but got: %s' % target)
            name, preset_dir_path, config_path = data
            if any((c not in string.digits + string.ascii_letters) for c in name):
                raise Exception('invalid target name: "%s"' % name)
            if not os.path.exists(preset_dir_path):
                raise Exception('Preset dir "%s" does not exist' % preset_dir_path)
            _, _, preset_file_names = next(os.walk(preset_dir_path))
            preset_paths = [(Path(preset_dir_path) / name) for name in preset_file_names]

            if not os.path.exists(config_path):
                raise Exception('Config file "%s" does not exist' % config_path)
            self.parsed_build_targets.append(BuildTarget(name, preset_paths, Path(config_path)))

    def run(self) -> None:
        if not self.dry_run:
            dir_util.mkpath(self.out_dir)

        for (name, preset_paths, config_path) in self.parsed_build_targets:
            assert self.spec_dir is not None
            spec_str = build_spec(name, self.spec_fork, self.md_doc_paths, preset_paths,
                                  config_path, self.spec_dir, self.spec_dot_yaml)
            if self.dry_run:
                self.announce('dry run successfully prepared contents for spec.'
                              f' out dir: "{self.out_dir}", spec fork: "{self.spec_fork}", build target: "{name}"')
                self.debug_print(spec_str)
            else:
                with open(os.path.join(self.out_dir, name + '.py'), 'w') as out:
                    out.write(spec_str)

        if not self.dry_run:
            with open(os.path.join(self.out_dir, '__init__.py'), 'w') as out:
                # `mainnet` is the default spec.
                out.write("from . import mainnet as spec  # noqa:F401\n")


class BuildPyCommand(build_py):
    """Customize the build command to run the spec-builder on setup.py build"""

    def initialize_options(self) -> None:
        super(BuildPyCommand, self).initialize_options()

    def run_pyspec_cmd(self, spec_fork: str, **opts: Dict) -> None:
        cmd_obj: PySpecCommand = self.distribution.reinitialize_command("pyspec")
        cmd_obj.spec_fork = spec_fork
        cmd_obj.out_dir = os.path.join(self.build_lib, 'eth2spec', spec_fork)
        for k, v in opts.items():
            setattr(cmd_obj, k, v)
        self.run_command('pyspec')

    def run(self) -> None:
        for fork in specs:
            self.run_pyspec_cmd(spec_fork=fork)

        super(BuildPyCommand, self).run()


class PyspecDevCommand(Command):
    """Build the markdown files in-place to their source location for testing."""
    description = "Build the markdown files in-place to their source location for testing."
    user_options: List[Tuple[str, Optional[str], str]] = []

    def initialize_options(self) -> None:
        pass

    def finalize_options(self) -> None:
        pass

    def run_pyspec_cmd(self, spec_fork: str, **opts: Dict) -> None:
        cmd_obj: PySpecCommand = self.distribution.reinitialize_command("pyspec")
        cmd_obj.spec_fork = spec_fork
        eth2spec_dir = convert_path(self.distribution.package_dir['eth2spec'])
        cmd_obj.out_dir = os.path.join(eth2spec_dir, spec_fork)
        for k, v in opts.items():
            setattr(cmd_obj, k, v)
        self.run_command('pyspec')

    def run(self) -> None:
        print("running build_py command")
        for fork in specs:
            self.run_pyspec_cmd(spec_fork=fork)


commands = {
    'pyspec': PySpecCommand,
    'build_py': BuildPyCommand,
    'pyspecdev': PyspecDevCommand,
}

with open("README.md", "rt", encoding="utf8") as f:
    readme = f.read()

# How to use "VERSION.txt" file:
# - dev branch contains "X.Y.Z.dev", where "X.Y.Z" is the target version to release dev into.
#    -> Changed as part of 'master' backport to 'dev'
# - master branch contains "X.Y.Z", where "X.Y.Z" is the current version.
#    -> Changed as part of 'dev' release (or other branch) into 'master'
#    -> In case of a commit on master without git tag, target the next version
#        with ".postN" (release candidate, numbered) suffixed.
# See https://www.python.org/dev/peps/pep-0440/#public-version-identifiers
with open(os.path.join('tests', 'core', 'pyspec', 'eth2spec', 'VERSION.txt')) as f:
    spec_version = f.read().strip()

setup(
    name='eth2spec',
    version=spec_version,
    description="Eth2 spec, provided as Python package for tooling and testing",
    long_description=readme,
    long_description_content_type="text/markdown",
    author="ethereum",
    url="https://github.com/ethereum/eth2.0-specs",
    include_package_data=False,
    package_data={'configs': ['*.yaml'],
                  'presets': ['*.yaml'],
                  'specs': ['**/*.md'],
                  'eth2spec': ['VERSION.txt']},
    package_dir={
        "eth2spec": "tests/core/pyspec/eth2spec",
        "configs": "configs",
        "presets": "presets",
        "specs": "specs",
    },
    packages=find_packages(where='tests/core/pyspec') + ['configs', 'specs'],
    py_modules=["eth2spec"],
    cmdclass=commands,
    python_requires=">=3.8, <4",
    extras_require={
        "test": ["pytest>=4.4", "pytest-cov", "pytest-xdist"],
        "lint": ["flake8==3.7.7", "mypy==0.812"],
        "generator": ["python-snappy==0.5.4"],
    },
    install_requires=[
        "eth-utils>=1.3.0,<2",
        "eth-typing>=2.1.0,<3.0.0",
        "pycryptodome==3.9.4",
        "py_ecc==5.2.0",
        "milagro_bls_binding==1.6.3",
        "dataclasses==0.6",
        "remerkleable==0.1.21",
        RUAMEL_YAML_VERSION,
        "lru-dict==1.1.6",
        MARKO_VERSION,
    ]
)
