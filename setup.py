from setuptools import setup, find_packages, Command
from setuptools.command.build_py import build_py
from distutils import dir_util
from distutils.util import convert_path
from pathlib import Path
import os
import string
from typing import Dict, List, Sequence, Optional, Tuple
import ast
import subprocess
import sys
import copy
from collections import OrderedDict
import json
from functools import reduce

from pysetup.constants import (
    # code names
    PHASE0,
    # misc
    ETH2_SPEC_COMMENT_PREFIX,
)
from pysetup.spec_builders import spec_builders
from pysetup.typing import (
    BuildTarget,
    ProtocolDefinition,
    SpecObject,
    VariableDefinition,
)
from pysetup.helpers import (
    combine_spec_objects,
    dependency_order_class_objects,
    objects_to_spec,
    parse_config_vars,
)
from pysetup.md_doc_paths import get_md_doc_paths


# NOTE: have to programmatically include third-party dependencies in `setup.py`.
def installPackage(package: str):
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])

RUAMEL_YAML_VERSION = "ruamel.yaml==0.17.21"
try:
    import ruamel.yaml
except ImportError:
    installPackage(RUAMEL_YAML_VERSION)

from ruamel.yaml import YAML

MARKO_VERSION = "marko==1.0.2"
try:
    import marko
except ImportError:
    installPackage(MARKO_VERSION)

from marko.block import Heading, FencedCode, LinkRefDef, BlankLine
from marko.inline import CodeSpan
from marko.ext.gfm import gfm
from marko.ext.gfm.elements import Table


def _get_name_from_heading(heading: Heading) -> Optional[str]:
    last_child = heading.children[-1]
    if isinstance(last_child, CodeSpan):
        return last_child.children
    return None


def _get_source_from_code_block(block: FencedCode) -> str:
    return block.children[0].children.strip()


def _get_function_name_from_source(source: str) -> str:
    fn = ast.parse(source).body[0]
    return fn.name


def _get_self_type_from_source(source: str) -> Optional[str]:
    fn = ast.parse(source).body[0]
    args = fn.args.args
    if len(args) == 0:
        return None
    if args[0].arg != 'self':
        return None
    if args[0].annotation is None:
        return None
    return args[0].annotation.id


def _get_class_info_from_source(source: str) -> Tuple[str, Optional[str]]:
    class_def = ast.parse(source).body[0]
    base = class_def.bases[0]
    if isinstance(base, ast.Name):
        parent_class = base.id
    elif isinstance(base, ast.Subscript):
        parent_class = base.value.id
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


def _load_kzg_trusted_setups(preset_name):
    trusted_setups_file_path = str(Path(__file__).parent) + '/presets/' + preset_name + '/trusted_setups/trusted_setup_4096.json'

    with open(trusted_setups_file_path, 'r') as f:
        json_data = json.load(f)
        trusted_setup_G1_monomial = json_data['g1_monomial']
        trusted_setup_G1_lagrange = json_data['g1_lagrange']
        trusted_setup_G2_monomial = json_data['g2_monomial']

    return trusted_setup_G1_monomial, trusted_setup_G1_lagrange, trusted_setup_G2_monomial

def _load_curdleproofs_crs(preset_name):
    """
    NOTE: File generated from https://github.com/asn-d6/curdleproofs/blob/8e8bf6d4191fb6a844002f75666fb7009716319b/tests/crs.rs#L53-L67
    """
    file_path = str(Path(__file__).parent) + '/presets/' + preset_name + '/trusted_setups/curdleproofs_crs.json'

    with open(file_path, 'r') as f:
        json_data = json.load(f)

    return json_data


ALL_KZG_SETUPS = {
    'minimal': _load_kzg_trusted_setups('minimal'),
    'mainnet': _load_kzg_trusted_setups('mainnet')
}

ALL_CURDLEPROOFS_CRS = {
    'minimal': _load_curdleproofs_crs('minimal'),
    'mainnet': _load_curdleproofs_crs('mainnet'),
}


def _get_eth2_spec_comment(child: LinkRefDef) -> Optional[str]:
    _, _, title = child._parse_info
    if not (title[0] == "(" and title[len(title)-1] == ")"):
        return None
    title = title[1:len(title)-1]
    if not title.startswith(ETH2_SPEC_COMMENT_PREFIX):
        return None
    return title[len(ETH2_SPEC_COMMENT_PREFIX):].strip()


def _parse_value(name: str, typed_value: str, type_hint: Optional[str] = None) -> VariableDefinition:
    comment = None
    if name in ("ROOT_OF_UNITY_EXTENDED", "ROOTS_OF_UNITY_EXTENDED", "ROOTS_OF_UNITY_REDUCED"):
        comment = "noqa: E501"

    typed_value = typed_value.strip()
    if '(' not in typed_value:
        return VariableDefinition(type_name=None, value=typed_value, comment=comment, type_hint=type_hint)
    i = typed_value.index('(')
    type_name = typed_value[:i]

    return VariableDefinition(type_name=type_name, value=typed_value[i+1:-1], comment=comment, type_hint=type_hint)


def _update_constant_vars_with_kzg_setups(constant_vars, preset_name):
    comment = "noqa: E501"
    kzg_setups = ALL_KZG_SETUPS[preset_name]
    constant_vars['KZG_SETUP_G1_MONOMIAL'] = VariableDefinition(constant_vars['KZG_SETUP_G1_MONOMIAL'].value, str(kzg_setups[0]), comment, None)
    constant_vars['KZG_SETUP_G1_LAGRANGE'] = VariableDefinition(constant_vars['KZG_SETUP_G1_LAGRANGE'].value, str(kzg_setups[1]), comment, None)
    constant_vars['KZG_SETUP_G2_MONOMIAL'] = VariableDefinition(constant_vars['KZG_SETUP_G2_MONOMIAL'].value, str(kzg_setups[2]), comment, None)
    

def get_spec(file_name: Path, preset: Dict[str, str], config: Dict[str, str], preset_name=str) -> SpecObject:
    functions: Dict[str, str] = {}
    protocols: Dict[str, ProtocolDefinition] = {}
    constant_vars: Dict[str, VariableDefinition] = {}
    preset_vars: Dict[str, VariableDefinition] = {}
    config_vars: Dict[str, VariableDefinition] = {}
    ssz_dep_constants: Dict[str, str] = {}
    func_dep_presets: Dict[str, str] = {}
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
                dataclasses[current_name] = "\n".join(line.rstrip() for line in source.splitlines())
            elif source.startswith("class"):
                class_name, parent_class = _get_class_info_from_source(source)
                # check consistency with spec
                assert class_name == current_name
                if parent_class:
                    assert parent_class == "Container"
                # NOTE: trim whitespace from spec
                ssz_objects[current_name] = "\n".join(line.rstrip() for line in source.splitlines())
            else:
                raise Exception("unrecognized python code element: " + source)
        elif isinstance(child, Table):
            for row in child.children:
                cells = row.children
                if len(cells) >= 2:
                    name_cell = cells[0]
                    name = name_cell.children[0].children

                    value_cell = cells[1]
                    value = value_cell.children[0].children

                    description = None
                    if len(cells) >= 3:
                        description_cell = cells[2]
                        if len(description_cell.children) > 0:
                            description = description_cell.children[0].children
                            if isinstance(description, list):
                                # marko parses `**X**` as a list containing a X
                                description = description[0].children

                    if isinstance(value, list):
                        # marko parses `**X**` as a list containing a X
                        value = value[0].children

                    if not _is_constant_id(name):
                        # Check for short type declarations
                        if value.startswith(("uint", "Bytes", "ByteList", "Union", "Vector", "List", "ByteVector")):
                            custom_types[name] = value
                        continue

                    if value.startswith("get_generalized_index"):
                        ssz_dep_constants[name] = value
                        continue

                    if description is not None and description.startswith("<!-- predefined -->"):
                        func_dep_presets[name] = value

                    value_def = _parse_value(name, value)
                    if name in preset:
                        preset_vars[name] = VariableDefinition(value_def.type_name, preset[name], value_def.comment, None)
                    elif name in config:
                        config_vars[name] = VariableDefinition(value_def.type_name, config[name], value_def.comment, None)
                    else:
                        if name in ('ENDIANNESS', 'KZG_ENDIANNESS'):
                            # Deal with mypy Literal typing check
                            value_def = _parse_value(name, value, type_hint='Final')
                        constant_vars[name] = value_def

        elif isinstance(child, LinkRefDef):
            comment = _get_eth2_spec_comment(child)
            if comment == "skip":
                should_skip = True

    # Load KZG trusted setup from files
    if any('KZG_SETUP' in name for name in constant_vars):
        _update_constant_vars_with_kzg_setups(constant_vars, preset_name)

    if any('CURDLEPROOFS_CRS' in name for name in constant_vars):
        constant_vars['CURDLEPROOFS_CRS'] = VariableDefinition(
            None,
            'curdleproofs.CurdleproofsCrs.from_json(json.dumps(' + str(ALL_CURDLEPROOFS_CRS[str(preset_name)]).replace('0x', '') + '))',
            "noqa: E501", None
        )

    return SpecObject(
        functions=functions,
        protocols=protocols,
        custom_types=custom_types,
        constant_vars=constant_vars,
        preset_vars=preset_vars,
        config_vars=config_vars,
        ssz_dep_constants=ssz_dep_constants,
        func_dep_presets=func_dep_presets,
        ssz_objects=ssz_objects,
        dataclasses=dataclasses,
    )


def load_preset(preset_files: Sequence[Path]) -> Dict[str, str]:
    """
    Loads the a directory of preset files, merges the result into one preset.
    """
    preset = {}
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


def build_spec(fork: str,
               preset_name: str,
               source_files: Sequence[Path],
               preset_files: Sequence[Path],
               config_file: Path) -> str:
    preset = load_preset(preset_files)
    config = load_config(config_file)
    all_specs = [get_spec(spec, preset, config, preset_name) for spec in source_files]

    spec_object = all_specs[0]
    for value in all_specs[1:]:
        spec_object = combine_spec_objects(spec_object, value)

    class_objects = {**spec_object.ssz_objects, **spec_object.dataclasses}

    # Ensure it's ordered after multiple forks
    new_objects = {}
    while OrderedDict(new_objects) != OrderedDict(class_objects):
        new_objects = copy.deepcopy(class_objects)
        dependency_order_class_objects(class_objects, spec_object.custom_types)

    return objects_to_spec(preset_name, spec_object, fork, class_objects)


class PySpecCommand(Command):
    """Convert spec markdown files to a spec python file"""

    description = "Convert spec markdown files to a spec python file"

    spec_fork: str
    md_doc_paths: str
    parsed_md_doc_paths: List[str]
    build_targets: str
    parsed_build_targets: List[BuildTarget]
    out_dir: str

    # The format is (long option, short option, description).
    user_options = [
        ('spec-fork=', None, "Spec fork to tag build with. Used to select md-docs defaults."),
        ('md-doc-paths=', None, "List of paths of markdown files to build spec with"),
        ('build-targets=', None, "Names, directory paths of compile-time presets, and default config paths."),
        ('out-dir=', None, "Output directory to write spec package to")
    ]

    def initialize_options(self):
        """Set default values for options."""
        # Each user option must be listed here with their default value.
        self.spec_fork = PHASE0
        self.md_doc_paths = ''
        self.out_dir = 'pyspec_output'
        self.build_targets = """
                minimal:presets/minimal:configs/minimal.yaml
                mainnet:presets/mainnet:configs/mainnet.yaml
        """

    def finalize_options(self):
        """Post-process options."""
        if len(self.md_doc_paths) == 0:
            print("no paths were specified, using default markdown file paths for pyspec"
                  " build (spec fork: %s)" % self.spec_fork)
            self.md_doc_paths = get_md_doc_paths(self.spec_fork)
            if len(self.md_doc_paths) == 0:
                raise Exception('no markdown files specified, and spec fork "%s" is unknown', self.spec_fork)

        self.parsed_md_doc_paths = self.md_doc_paths.split()

        for filename in self.parsed_md_doc_paths:
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

    def run(self):
        if not self.dry_run:
            dir_util.mkpath(self.out_dir)

        for (name, preset_paths, config_path) in self.parsed_build_targets:
            spec_str = build_spec(
                spec_builders[self.spec_fork].fork,
                name,
                self.parsed_md_doc_paths,
                preset_paths,
                config_path,
            )
            if self.dry_run:
                self.announce('dry run successfully prepared contents for spec.'
                              f' out dir: "{self.out_dir}", spec fork: "{self.spec_fork}", build target: "{name}"')
                self.debug_print(spec_str)
            else:
                with open(os.path.join(self.out_dir, name+'.py'), 'w') as out:
                    out.write(spec_str)

        if not self.dry_run:
            with open(os.path.join(self.out_dir, '__init__.py'), 'w') as out:
                # `mainnet` is the default spec.
                out.write("from . import mainnet as spec  # noqa:F401\n")


class BuildPyCommand(build_py):
    """Customize the build command to run the spec-builder on setup.py build"""

    def initialize_options(self):
        super(BuildPyCommand, self).initialize_options()

    def run_pyspec_cmd(self, spec_fork: str, **opts):
        cmd_obj: PySpecCommand = self.distribution.reinitialize_command("pyspec")
        cmd_obj.spec_fork = spec_fork
        cmd_obj.out_dir = os.path.join(self.build_lib, 'eth2spec', spec_fork)
        for k, v in opts.items():
            setattr(cmd_obj, k, v)
        self.run_command('pyspec')

    def run(self):
        for spec_fork in spec_builders:
            self.run_pyspec_cmd(spec_fork=spec_fork)

        super(BuildPyCommand, self).run()


class PyspecDevCommand(Command):
    """Build the markdown files in-place to their source location for testing."""
    description = "Build the markdown files in-place to their source location for testing."
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run_pyspec_cmd(self, spec_fork: str, **opts):
        cmd_obj: PySpecCommand = self.distribution.reinitialize_command("pyspec")
        cmd_obj.spec_fork = spec_fork
        eth2spec_dir = convert_path(self.distribution.package_dir['eth2spec'])
        cmd_obj.out_dir = os.path.join(eth2spec_dir, spec_fork)
        for k, v in opts.items():
            setattr(cmd_obj, k, v)
        self.run_command('pyspec')

    def run(self):
        print("running build_py command")
        for spec_fork in spec_builders:
            self.run_pyspec_cmd(spec_fork=spec_fork)


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
    python_requires=">=3.9, <4",
    extras_require={
        "test": ["pytest>=4.4", "pytest-cov", "pytest-xdist"],
        "lint": ["flake8==5.0.4", "mypy==0.981", "pylint==2.15.3"],
        "generator": ["python-snappy==0.6.1", "filelock", "pathos==0.3.0"],
        "docs": ["mkdocs==1.4.2", "mkdocs-material==9.1.5", "mdx-truly-sane-lists==1.3",  "mkdocs-awesome-pages-plugin==2.8.0"]
    },
    install_requires=[
        "eth-utils>=2.0.0,<3",
        "eth-typing>=3.2.0,<4.0.0",
        "pycryptodome==3.15.0",
        "py_ecc==6.0.0",
        "milagro_bls_binding==1.9.0",
        "remerkleable==0.1.27",
        "trie==2.0.2",
        RUAMEL_YAML_VERSION,
        "lru-dict==1.2.0",
        MARKO_VERSION,
        "py_arkworks_bls12381==0.3.4",
        "curdleproofs==0.1.1",
    ]
)
