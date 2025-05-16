import ast
import json
from pathlib import Path
import string
from typing import Dict, Optional, Tuple
import re
from functools import lru_cache


from marko.block import BlankLine, Heading, FencedCode, HTMLBlock
from marko.ext.gfm import gfm
from marko.ext.gfm.elements import Table
from marko.inline import CodeSpan

from .typing import ProtocolDefinition, VariableDefinition, SpecObject

class MarkdownToSpec:
    def __init__(self, file_name: Path, preset: Dict[str, str], config: Dict[str, str], preset_name: str):
        self.file_name = file_name
        self.preset = preset
        self.config = config
        self.preset_name = preset_name

        self.functions: Dict[str, str] = {}
        self.protocols: Dict[str, ProtocolDefinition] = {}
        self.constant_vars: Dict[str, VariableDefinition] = {}
        self.preset_dep_constant_vars: Dict[str, VariableDefinition] = {}
        self.preset_vars: Dict[str, VariableDefinition] = {}
        self.config_vars: Dict[str, VariableDefinition] = {}
        self.ssz_dep_constants: Dict[str, str] = {}
        self.func_dep_presets: Dict[str, str] = {}
        self.ssz_objects: Dict[str, str] = {}
        self.dataclasses: Dict[str, str] = {}
        self.all_custom_types: Dict[str, str] = {}
        self.custom_types: Dict[str, str] = {}
        self.preset_dep_custom_types: Dict[str, str] = {}

        self.document = None
        self.document_iterator = None
        self.current_name = None
        self.should_skip = False
        self.list_of_records = None
        self.list_of_records_name = None

    def run(self) -> SpecObject:
        """
        Orchestrates the parsing and processing of the markdown spec file.
        - Calls _parse_document()
        - Iterates over self.document.children and processes each child
        - Calls _finalize_types() and _build_spec_object() after processing
        Returns:
            SpecObject: The constructed specification object.
        """
        self._parse_document()
        # self.document_iterator = iter(self.document.children)
        # while (child := self._get_next_element()) is not None:
        for child in self.document.children:
            self._process_child(child)
        self._finalize_types()
        return self._build_spec_object()

    def _get_next_element(self):
        """
        Returns the next element in the document.
        If the end of the document is reached, returns None.
        """

        try:
            # while isinstance(result := next(self.document_iterator), BlankLine):
            #     pass
            # return result
            next(self.document_iterator)
        except StopIteration:
            return None

    def _finalize_types(self):
        """
        Processes all_custom_types into custom_types and preset_dep_custom_types.
        Calls helper functions to update KZG and CURDLEPROOFS setups if needed.
        """
        # Update KZG trusted setup if needed
        if any('KZG_SETUP' in name for name in self.constant_vars):
            _update_constant_vars_with_kzg_setups(
                self.constant_vars, self.preset_dep_constant_vars, self.preset_name
            )

        # Update CURDLEPROOFS CRS if needed
        if any('CURDLEPROOFS_CRS' in name for name in self.constant_vars):
            _update_constant_vars_with_curdleproofs_crs(
                self.constant_vars, self.preset_dep_constant_vars, self.preset_name
            )

        # Split all_custom_types into custom_types and preset_dep_custom_types
        self.custom_types = {}
        self.preset_dep_custom_types = {}
        for name, value in self.all_custom_types.items():
            if any(k in value for k in self.preset) or any(k in value for k in self.preset_dep_constant_vars):
                self.preset_dep_custom_types[name] = value
            else:
                self.custom_types[name] = value

    def _parse_document(self):
        """
        Opens the markdown file, parses its content into a document object using _parse_markdown,
        and stores the parsed document in self.document.
        """
        with open(self.file_name) as source_file:
            self.document = parse_markdown(source_file.read())

    def _process_child(self, child):
        # Skip blank lines
        if isinstance(child, BlankLine):
            return

        if self.should_skip:
            self.should_skip = False
            return

            # Dispatch to the correct handler
        if isinstance(child, Heading):
            self._process_heading(child)
        elif isinstance(child, FencedCode):
            self._process_code_block(child)
        elif isinstance(child, Table):
            # Handler for list-of-records is managed by state in _process_html_block
            if self.list_of_records is not None:
                self._process_list_of_records_table(child)
            else:
                self._process_table(child)
        elif isinstance(child, HTMLBlock):
            self._process_html_block(child)

    def _process_heading(self, child):
        """
        Extracts the section name from the heading and updates current_name for context.
        """
        if not isinstance(child, Heading):
            return
        self.current_name = _get_name_from_heading(child)
        # else: skip unknown types

    def _process_code_block(self, child):
        """
        Processes a FencedCode block:
        - Checks if the code block is Python.
        - Extracts source code and determines if it is a function, dataclass, or class.
        - Updates the appropriate dictionary (functions, protocols, dataclasses, ssz_objects).
        """
        if child.lang != "python":
            return

        source = _get_source_from_code_block(child)

        if source.startswith("def"):
            self._process_code_def(source)
        elif source.startswith("@dataclass"):
            self._process_code_dataclass(source)
        elif source.startswith("class"):
            self._process_code_class(source)
        else:
            raise Exception("unrecognized python code element: " + source)

    def _process_code_def(self, source):
        self.current_name = _get_function_name_from_source(source)
        self_type_name = _get_self_type_from_source(source)
        function_def = "\n".join(line.rstrip() for line in source.splitlines())
        if self_type_name is None:
            self.functions[self.current_name] = function_def
        else:
            if self_type_name not in self.protocols:
                self.protocols[self_type_name] = ProtocolDefinition(
                    functions={})
            self.protocols[self_type_name].functions[self.current_name] = function_def

    def _process_code_dataclass(self, source):
        """ if self.current_name is None:
            raise Exception(f"found @dataclass without a name: {source}")"""
        self.dataclasses[self.current_name] = "\n".join(
            line.rstrip() for line in source.splitlines())

    def _process_code_class(self, source):
        class_name, parent_class = _get_class_info_from_source(source)
        # check consistency with spec
        if class_name != self.current_name:
            raise Exception(
                f"class_name {class_name} != current_name {self.current_name}")

        if parent_class:
            assert parent_class == "Container"
        self.ssz_objects[self.current_name] = "\n".join(
            line.rstrip() for line in source.splitlines())

    def _process_table(self, child):
        """
        Handles standard tables (not list-of-records).
        Iterates over rows, extracting variable names, values, and descriptions.
        Determines if the variable is a constant, preset, config, or custom type.
        Updates the corresponding dictionaries.
        Handles special cases for predefined types and function-dependent presets.
        """

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
                            description = description[0].children

                if isinstance(name, list):
                    name = name[0].children
                if isinstance(value, list):
                    value = value[0].children

                # Skip types that have been defined elsewhere
                if description is not None and description.startswith("<!-- predefined-type -->"):
                    continue

                if not _is_constant_id(name):
                    # Check for short type declarations
                    if value.startswith(("uint", "Bytes", "ByteList", "Union", "Vector", "List", "ByteVector")):
                        self.all_custom_types[name] = value
                    continue

                if value.startswith("get_generalized_index"):
                    self.ssz_dep_constants[name] = value
                    continue

                if description is not None and description.startswith("<!-- predefined -->"):
                    self.func_dep_presets[name] = value

                value_def = _parse_value(name, value)
                if name in self.preset:
                    if self.preset_name == "mainnet":
                        check_yaml_matches_spec(
                            name, self.preset, value_def)
                    self.preset_vars[name] = VariableDefinition(
                        value_def.type_name, self.preset[name], value_def.comment, None)
                elif name in self.config:
                    if self.preset_name == "mainnet":
                        check_yaml_matches_spec(
                            name, self.config, value_def)
                    self.config_vars[name] = VariableDefinition(
                        value_def.type_name, self.config[name], value_def.comment, None)
                else:
                    if name in ('ENDIANNESS', 'KZG_ENDIANNESS'):
                        # Deal with mypy Literal typing check
                        value_def = _parse_value(
                            name, value, type_hint='Final')
                    if any(k in value for k in self.preset) or any(k in value for k in self.preset_dep_constant_vars):
                        self.preset_dep_constant_vars[name] = value_def
                    else:
                        self.constant_vars[name] = value_def

    def _process_list_of_records_table(self, child):
        """
        Handles tables marked as 'list-of-records'.
        Extracts headers and rows, mapping field names and types.
        Applies type mapping to config entries.
        Validates or updates the config variable as needed based on preset_name.
        Updates config_vars with the processed list.
        """

        list_of_records_header = None
        for i, row in enumerate(child.children):
            if i == 0:
                # Save the table header, used for field names (skip last item: description)
                list_of_records_header = [
                    re.sub(r'\s+', '_', value.children[0].children.upper())
                    for value in row.children[:-1]
                ]
            else:
                # Add the row entry to our list of records
                self.list_of_records.append({
                    list_of_records_header[j]: value.children[0].children
                    for j, value in enumerate(row.children[:-1])
                })

        # Make a type map from the spec definition
        type_map: dict[str, str] = {}
        pattern = re.compile(r'^(\w+)\(.*\)$')
        for entry in self.list_of_records:
            for k, v in entry.items():
                m = pattern.match(v)
                if m:
                    type_map[k] = m.group(1)

        # Apply the types to the file config
        list_of_records_config: list[dict[str, str]] = []
        for entry in self.config[self.list_of_records_name]:
            new_entry = {}
            for k, v in entry.items():
                ctor = type_map.get(k)
                if ctor:
                    new_entry[k] = f"{ctor}({v})"
                else:
                    new_entry[k] = v
            list_of_records_config.append(new_entry)

        # For mainnet, check that the spec config & file config are the same
        if self.preset_name == "mainnet":
            assert self.list_of_records == list_of_records_config, \
                f"list of records mismatch: {self.list_of_records} vs {list_of_records_config}"
        elif self.preset_name == "minimal":
            self.list_of_records = list_of_records_config

        # Set the config variable and reset the state
        self.config_vars[self.list_of_records_name] = self.list_of_records
        self.list_of_records = None

    def _process_html_block(self, child):
        """
        Handles HTML comments for skip logic and list-of-records detection.
        Sets flags or state variables for the next iteration.
        """

        body = child.body.strip()
        if body == "<!-- eth2spec: skip -->":
            self.should_skip = True
        # Handle list-of-records tables
        match = re.match(
            r"<!--\s*list-of-records:([a-zA-Z0-9_-]+)\s*-->", body)
        if match:
            self.list_of_records = []
            self.list_of_records_name = match.group(1).upper()

    def _build_spec_object(self):
        """
        Constructs and returns the SpecObject using all collected data.
        """
        return SpecObject(
            functions=self.functions,
            protocols=self.protocols,
            custom_types=self.custom_types,
            preset_dep_custom_types=self.preset_dep_custom_types,
            constant_vars=self.constant_vars,
            preset_dep_constant_vars=self.preset_dep_constant_vars,
            preset_vars=self.preset_vars,
            config_vars=self.config_vars,
            ssz_dep_constants=self.ssz_dep_constants,
            func_dep_presets=self.func_dep_presets,
            ssz_objects=self.ssz_objects,
            dataclasses=self.dataclasses,
        )

@lru_cache(maxsize=None)
def _get_name_from_heading(heading: Heading) -> Optional[str]:
    last_child = heading.children[-1]
    if isinstance(last_child, CodeSpan):
        return last_child.children
    return None


@lru_cache(maxsize=None)
def _get_source_from_code_block(block: FencedCode) -> str:
    return block.children[0].children.strip()


@lru_cache(maxsize=None)
def _get_function_name_from_source(source: str) -> str:
    fn = ast.parse(source).body[0]
    return fn.name


@lru_cache(maxsize=None)
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


@lru_cache(maxsize=None)
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


@lru_cache(maxsize=None)
def _is_constant_id(name: str) -> bool:
    if name[0] not in string.ascii_uppercase + '_':
        return False
    return all(map(lambda c: c in string.ascii_uppercase + '_' + string.digits, name[1:]))

@lru_cache(maxsize=None)
def _load_kzg_trusted_setups(preset_name):
    trusted_setups_file_path = str(Path(__file__).parent.parent) + '/presets/' + preset_name + '/trusted_setups/trusted_setup_4096.json'

    with open(trusted_setups_file_path, 'r') as f:
        json_data = json.load(f)
        trusted_setup_G1_monomial = json_data['g1_monomial']
        trusted_setup_G1_lagrange = json_data['g1_lagrange']
        trusted_setup_G2_monomial = json_data['g2_monomial']

    return trusted_setup_G1_monomial, trusted_setup_G1_lagrange, trusted_setup_G2_monomial

@lru_cache(maxsize=None)
def _load_curdleproofs_crs(preset_name):
    """
    NOTE: File generated from https://github.com/asn-d6/curdleproofs/blob/8e8bf6d4191fb6a844002f75666fb7009716319b/tests/crs.rs#L53-L67
    """
    file_path = str(Path(__file__).parent.parent) + '/presets/' + preset_name + '/trusted_setups/curdleproofs_crs.json'

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

@lru_cache(maxsize=None)
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


def _update_constant_vars_with_kzg_setups(constant_vars, preset_dep_constant_vars, preset_name):
    comment = "noqa: E501"
    kzg_setups = ALL_KZG_SETUPS[preset_name]
    preset_dep_constant_vars['KZG_SETUP_G1_MONOMIAL'] = VariableDefinition(
        preset_dep_constant_vars['KZG_SETUP_G1_MONOMIAL'].value,
        str(kzg_setups[0]),
        comment, None
    )
    preset_dep_constant_vars['KZG_SETUP_G1_LAGRANGE'] = VariableDefinition(
        preset_dep_constant_vars['KZG_SETUP_G1_LAGRANGE'].value,
        str(kzg_setups[1]),
        comment, None
    )
    constant_vars['KZG_SETUP_G2_MONOMIAL'] = VariableDefinition(
        constant_vars['KZG_SETUP_G2_MONOMIAL'].value,
        str(kzg_setups[2]),
        comment, None
    )


def _update_constant_vars_with_curdleproofs_crs(constant_vars, preset_dep_constant_vars, preset_name):
    comment = "noqa: E501"
    constant_vars['CURDLEPROOFS_CRS'] = VariableDefinition(
        None,
        'curdleproofs.CurdleproofsCrs.from_json(json.dumps(' + str(ALL_CURDLEPROOFS_CRS[str(preset_name)]).replace('0x', '') + '))',
        comment, None
    )


@lru_cache(maxsize=None)
def parse_markdown(content: str):
    return gfm.parse(content)


def check_yaml_matches_spec(var_name, yaml, value_def):
    """
    This function performs a sanity check for presets & configs. To a certain degree, it ensures
    that the values in the specifications match those in the yaml files.
    """
    if var_name == "TERMINAL_BLOCK_HASH":
        # This is just Hash32() in the specs, that's fine
        return

    # We use a var in the definition of a new var, replace usages
    # Reverse sort so that overridden values come first
    updated_value = value_def.value
    for var in sorted(yaml.keys(), reverse=True):
        if var in updated_value:
            updated_value = updated_value.replace(var, yaml[var])
    try:
        assert yaml[var_name] == repr(eval(updated_value)), \
            f"mismatch for {var_name}: {yaml[var_name]} vs {eval(updated_value)}"
    except NameError:
        # Okay it's probably something more serious, let's ignore
        pass
