import ast
import json
import re
import string
from functools import lru_cache
from pathlib import Path
from typing import cast, Dict, Iterator, Mapping, Optional, Tuple

from marko.block import BlankLine, Document, FencedCode, Heading, HTMLBlock
from marko.element import Element
from marko.ext.gfm import gfm
from marko.ext.gfm.elements import Table, TableCell, TableRow
from marko.inline import CodeSpan

from .typing import ProtocolDefinition, SpecObject, VariableDefinition


class MarkdownToSpec:
    def __init__(
        self,
        file_name: Path,
        preset: dict[str, str],
        config: dict[str, str | list[dict[str, str]]],
        preset_name: str,
    ):
        """
        Initializes the MarkdownToSpec instance.
        """
        self.preset = preset
        self.config = config
        self.preset_name = preset_name

        self.document_iterator: Iterator[Element] = self._parse_document(file_name)
        self.all_custom_types: Dict[str, str] = {}
        self.current_heading_name: str | None = None

        # Use a single dict to hold all SpecObject fields
        self.spec: dict[str, dict] = {
            "config_vars": {},
            "constant_vars": {},
            "custom_types": {},
            "dataclasses": {},
            "func_dep_presets": {},
            "functions": {},
            "preset_dep_constant_vars": {},
            "preset_dep_custom_types": {},
            "preset_vars": {},
            "protocols": {},
            "ssz_dep_constants": {},
            "ssz_objects": {},
        }

    def run(self) -> SpecObject:
        """
        Parses the markdown spec file and returns the SpecObject.
        """
        while (child := self._get_next_element()) is not None:
            self._process_child(child)
        self._finalize_types()
        return self._build_spec_object()

    def _get_next_element(self) -> Optional[Element]:
        """
        Returns the next non-blank element in the document.
        """
        try:
            while isinstance(result := next(self.document_iterator), BlankLine):
                pass
            return result
        except StopIteration:
            return None

    def _skip_element(self) -> None:
        """
        Skips the current element in the document.
        """
        self._get_next_element()

    def _parse_document(self, file_name: Path) -> Iterator[Element]:
        """
        Parses the markdown file into document elements.
        """
        with open(file_name) as source_file:
            document = parse_markdown(source_file.read())
            return iter(document.children)

    def _process_child(self, child: Element) -> None:
        """Processes a child Markdown element by dispatching to the appropriate handler based on its type."""

        # Skip blank lines
        if isinstance(child, BlankLine):
            return

        # Dispatch to the correct handler
        match child:
            case Heading():
                self._process_heading(child)
            case FencedCode():
                self._process_code_block(child)
            case Table():
                self._process_table(child)
            case HTMLBlock():
                self._process_html_block(child)

    def _process_heading(self, heading: Heading) -> None:
        """
        Extracts the section name from the heading and updates current_heading_name for context.
        """
        self.current_heading_name = _get_name_from_heading(heading)

    def _process_code_block(self, code_block: FencedCode) -> None:
        """
        Processes a FencedCode block, ignoring non-Python code.
        - Extracts source code and determines if it is a function, dataclass, or class.
        """
        if code_block.lang != "python":
            return

        source = _get_source_from_code_block(code_block)
        module = ast.parse(source)

        # AST element for each top level definition of the module
        for element in module.body:
            element_source = ast.unparse(element)
            clean_source = "\n".join(line.rstrip() for line in element_source.splitlines())

            if isinstance(element, ast.FunctionDef):
                self._process_code_def(clean_source, element)
            elif isinstance(element, ast.ClassDef) and _has_decorator(element, "dataclass"):
                self._add_dataclass(clean_source, element)
            elif isinstance(element, ast.ClassDef):
                self._process_code_class(clean_source, element)
            else:
                raise Exception("unrecognized python code element: " + source)

    def _process_code_def(self, source: str, fn: ast.FunctionDef) -> None:
        """
        Processes a function definition and stores it in the spec.
        """
        self_type_name = _get_self_type_from_source(fn)

        if self_type_name is None:
            self.spec["functions"][fn.name] = source
        else:
            self._add_protocol_function(self_type_name, fn.name, source)

    def _add_protocol_function(
        self, protocol_name: str, function_name: str, function_def: str
    ) -> None:
        """
        Adds a function definition to the protocol functions dictionary.
        """
        if protocol_name not in self.spec["protocols"]:
            self.spec["protocols"][protocol_name] = ProtocolDefinition(functions={})
        self.spec["protocols"][protocol_name].functions[function_name] = function_def

    def _add_dataclass(self, source: str, cls: ast.ClassDef) -> None:
        self.spec["dataclasses"][cls.name] = source

    def _process_code_class(self, source: str, cls: ast.ClassDef) -> None:
        """
        Processes a class definition and updates the spec.
        """
        class_name, parent_class = _get_class_info_from_ast(cls)

        # check consistency with spec
        if class_name != self.current_heading_name:
            raise Exception(f"class_name {class_name} != current_name {self.current_heading_name}")

        if parent_class:
            assert parent_class == "Container"
        self.spec["ssz_objects"][class_name] = source

    def _process_table(self, table: Table) -> None:
        """
        Processes a table and updates the spec with its data.
        """
        for row in cast(list[TableRow], table.children):
            if len(row.children) < 2:
                continue

            name, value, description = self._get_table_row_fields(row)

            # Skip types that have been defined elsewhere
            if description is not None and description.startswith("<!-- predefined-type -->"):
                continue

            # If it is not a constant, check if it is a custom type
            if not _is_constant_id(name):
                # Check for short type declarations
                if value.startswith(
                    ("uint", "Bytes", "ByteList", "Union", "Vector", "List", "ByteVector")
                ):
                    self.all_custom_types[name] = value
                continue

            # It is a constant name and a generalized index
            if value.startswith("get_generalized_index"):
                self.spec["ssz_dep_constants"][name] = value
                continue

            # It is a constant and not a generalized index, and a function-dependent preset
            if description is not None and description.startswith("<!-- predefined -->"):
                self.spec["func_dep_presets"][name] = value

            # It is a constant and not a generalized index, and not a function-dependent preset
            value_def = _parse_value(name, value)
            # It is a preset
            if name in self.preset:
                if self.preset_name == "mainnet":
                    check_yaml_matches_spec(name, self.preset, value_def)

                self.spec["preset_vars"][name] = VariableDefinition(
                    value_def.type_name, self.preset[name], value_def.comment, None
                )

            # It is a config variable
            elif name in self.config:
                if self.preset_name == "mainnet":
                    check_yaml_matches_spec(name, self.config, value_def)

                config_value = self.config[name]
                if isinstance(config_value, str):
                    self.spec["config_vars"][name] = VariableDefinition(
                        value_def.type_name, config_value, value_def.comment, None
                    )
                else:
                    raise ValueError(f"Variable {name} should be a string in the config file.")

            # It is a constant variable or a preset_dep_constant_vars
            else:
                if name in ("ENDIANNESS", "KZG_ENDIANNESS"):
                    # Deal with mypy Literal typing check
                    value_def = _parse_value(name, value, type_hint="Final")
                if any(k in value for k in self.preset) or any(
                    k in value for k in self.spec["preset_dep_constant_vars"]
                ):
                    self.spec["preset_dep_constant_vars"][name] = value_def
                else:
                    self.spec["constant_vars"][name] = value_def

    @staticmethod
    def _get_table_row_fields(row: TableRow) -> tuple[str, str, Optional[str]]:
        """
        Extracts the name, value, and description fields from a table row element.
        """
        cells = cast(list[TableCell], row.children)
        name_cell = cells[0]
        name = name_cell.children[0].children

        value_cell = cells[1]
        value = value_cell.children[0].children

        if isinstance(name, list):
            name = name[0].children
        if isinstance(value, list):
            value = value[0].children

        description = None
        if len(cells) >= 3:
            description_cell = cells[2]
            if len(description_cell.children) > 0:
                description = description_cell.children[0].children
                if isinstance(description, list):
                    description = description[0].children

        return name, value, description

    def _process_list_of_records_table(self, table: Table, list_of_records_name: str) -> None:
        """
        Handles tables marked as 'list-of-records'.
        Updates config_vars with the processed list.

        Example of input:
            | Name   | Calories      | Description   |
            | ------ | ------------- | ------------- |
            | Apple  | `uint64(96)`  | 5.3oz serving |
            | Orange | `uint64(75)`  | 5.6oz serving |
            | Banana | `uint64(111)` | 4.4oz serving |

        The method _process_html_block calls this method when it encounters a comment
        of the form `<!-- list-of-records:name -->`.
        """
        list_of_records_spec = self._extract_list_of_records_spec(table)

        # Make a type map from the spec definition
        type_map = self._make_list_of_records_type_map(list_of_records_spec)

        # Apply the types to the file config
        list_of_records_config_file = self._extract_typed_records_config(
            list_of_records_name, type_map
        )

        # For mainnet, check that the spec config & file config are the same
        # For minimal, we expect this to be different; just use the file config
        if self.preset_name == "mainnet":
            assert list_of_records_spec == list_of_records_config_file, (
                f"list of records mismatch: {list_of_records_spec} vs {list_of_records_config_file}"
            )

        # Set the config variable
        self.spec["config_vars"][list_of_records_name] = list_of_records_config_file

    @staticmethod
    def _make_list_of_records_type_map(list_of_records: list[dict[str, str]]) -> dict[str, str]:
        """
        Given a list of records (each a dict of field name to value), extract a mapping
        from field name to type name, based on values of the form 'TypeName(...)'.
        """
        type_map: dict[str, str] = {}
        pattern = re.compile(r"^(\w+)\(.*\)$")
        for entry in list_of_records:
            for k, v in entry.items():
                m = pattern.match(v)
                if m:
                    type_map[k] = m.group(1)
        return type_map

    @staticmethod
    def _extract_list_of_records_spec(table: Table) -> list[dict[str, str]]:
        """
        Extracts the list of records from a table element.
        Returns a list of dicts, each representing a row with field names as keys.
        """

        # Save the table header, used for field names (skip last item: description)
        header_row = cast(TableRow, table.children[0])
        list_of_records_spec_header = [
            re.sub(r"\s+", "_", value.children[0].children.upper())
            for value in header_row.children[:-1]
        ]

        # Process the remaining rows
        list_of_records_spec: list[dict[str, str]] = [
            {
                list_of_records_spec_header[j]: value.children[0].children
                for j, value in enumerate(row.children[:-1])
            }
            for row in table.children[1:]
        ]

        return list_of_records_spec

    def _extract_typed_records_config(
        self, list_of_records_name: str, type_map: dict[str, str]
    ) -> list[dict[str, str]]:
        """
        Applies type constructors to config entries based on the type map.
        Returns a new list of dicts with types applied.
        """
        list_of_records_config_file: list[dict[str, str]] = []
        entries = self.config[list_of_records_name]
        if not isinstance(entries, list):
            raise ValueError(f"Expected a dict for {list_of_records_name} in config file")

        for entry in entries:
            new_entry = {}
            for k, v in entry.items():
                ctor = type_map.get(k)
                if ctor:
                    new_entry[k] = f"{ctor}({v})"
                else:
                    new_entry[k] = v
            list_of_records_config_file.append(new_entry)
        return list_of_records_config_file

    def _process_html_block(self, html: HTMLBlock) -> None:
        """
        Handles HTML comments for skip logic and list-of-records detection.
        Sets flags or state variables for the next iteration.
        """
        body = html.body.strip()

        # This comment marks that we should skip the next element
        if body == "<!-- eth2spec: skip -->":
            self._skip_element()

        # Handle list-of-records tables
        # This comment marks that the next table is a list-of-records
        # e.g. <!-- list-of-records: <name> -->
        match = re.match(r"<!--\s*list-of-records:([a-zA-Z0-9_-]+)\s*-->", body)
        if match:
            table_element = self._get_next_element()
            if not isinstance(table_element, Table):
                raise Exception(
                    f"expected table after list-of-records comment, got {type(table_element)}"
                )
            self._process_list_of_records_table(table_element, match.group(1).upper())

    def _finalize_types(self) -> None:
        """
        Processes all_custom_types into custom_types and preset_dep_custom_types.
        Calls helper functions to update KZG and CURDLEPROOFS setups if needed.
        """
        # Update KZG trusted setup if needed
        if any("KZG_SETUP" in name for name in self.spec["constant_vars"]):
            _update_constant_vars_with_kzg_setups(
                self.spec["constant_vars"], self.spec["preset_dep_constant_vars"], self.preset_name
            )

        # Update CURDLEPROOFS CRS if needed
        if any("CURDLEPROOFS_CRS" in name for name in self.spec["constant_vars"]):
            _update_constant_vars_with_curdleproofs_crs(
                self.spec["constant_vars"], self.preset_name
            )

        # Split all_custom_types into custom_types and preset_dep_custom_types
        self.spec["custom_types"] = {}
        self.spec["preset_dep_custom_types"] = {}
        for name, value in self.all_custom_types.items():
            if any(k in value for k in self.preset) or any(
                k in value for k in self.spec["preset_dep_constant_vars"]
            ):
                self.spec["preset_dep_custom_types"][name] = value
            else:
                self.spec["custom_types"][name] = value

    def _build_spec_object(self) -> SpecObject:
        """
        Returns the SpecObject using all collected data.
        """
        return SpecObject(
            config_vars=self.spec["config_vars"],
            constant_vars=self.spec["constant_vars"],
            custom_types=self.spec["custom_types"],
            dataclasses=self.spec["dataclasses"],
            func_dep_presets=self.spec["func_dep_presets"],
            functions=self.spec["functions"],
            preset_dep_constant_vars=self.spec["preset_dep_constant_vars"],
            preset_dep_custom_types=self.spec["preset_dep_custom_types"],
            preset_vars=self.spec["preset_vars"],
            protocols=self.spec["protocols"],
            ssz_dep_constants=self.spec["ssz_dep_constants"],
            ssz_objects=self.spec["ssz_objects"],
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
def _get_self_type_from_source(fn: ast.FunctionDef) -> Optional[str]:
    args = fn.args.args
    if len(args) == 0:
        return None
    if args[0].arg != "self":
        return None
    if args[0].annotation is None:
        return None
    return args[0].annotation.id


@lru_cache(maxsize=None)
def _get_class_info_from_ast(cls: ast.ClassDef) -> Tuple[str, Optional[str]]:
    base = cls.bases[0]
    if isinstance(base, ast.Name):
        parent_class = base.id
    elif isinstance(base, ast.Subscript):
        parent_class = base.value.id
    else:
        # NOTE: SSZ definition derives from earlier phase...
        # e.g. `phase0.SignedBeaconBlock`
        # TODO: check for consistency with other phases
        parent_class = None
    return cls.name, parent_class


@lru_cache(maxsize=None)
def _is_constant_id(name: str) -> bool:
    """
    Checks if the given name follows the convention for constant identifiers.
    """
    if name[0] not in string.ascii_uppercase + "_":
        return False
    return all(map(lambda c: c in string.ascii_uppercase + "_" + string.digits, name[1:]))


@lru_cache(maxsize=None)
def _load_kzg_trusted_setups(preset_name: str) -> Tuple[list[str], list[str], list[str]]:
    trusted_setups_file_path = (
        str(Path(__file__).parent.parent)
        + "/presets/"
        + preset_name
        + "/trusted_setups/trusted_setup_4096.json"
    )

    with open(trusted_setups_file_path, "r") as f:
        json_data = json.load(f)
        trusted_setup_G1_monomial = json_data["g1_monomial"]
        trusted_setup_G1_lagrange = json_data["g1_lagrange"]
        trusted_setup_G2_monomial = json_data["g2_monomial"]

    return trusted_setup_G1_monomial, trusted_setup_G1_lagrange, trusted_setup_G2_monomial


@lru_cache(maxsize=None)
def _load_curdleproofs_crs(preset_name: str) -> Dict[str, list[str]]:
    """
    NOTE: File generated from https://github.com/asn-d6/curdleproofs/blob/8e8bf6d4191fb6a844002f75666fb7009716319b/tests/crs.rs#L53-L67
    """
    file_path = (
        str(Path(__file__).parent.parent)
        + "/presets/"
        + preset_name
        + "/trusted_setups/curdleproofs_crs.json"
    )

    with open(file_path, "r") as f:
        json_data = json.load(f)

    return json_data


ALL_KZG_SETUPS = {
    "minimal": _load_kzg_trusted_setups("minimal"),
    "mainnet": _load_kzg_trusted_setups("mainnet"),
}

ALL_CURDLEPROOFS_CRS = {
    "minimal": _load_curdleproofs_crs("minimal"),
    "mainnet": _load_curdleproofs_crs("mainnet"),
}


@lru_cache(maxsize=None)
def _parse_value(
    name: str, typed_value: str, type_hint: Optional[str] = None
) -> VariableDefinition:
    comment = None
    if name in ("ROOT_OF_UNITY_EXTENDED", "ROOTS_OF_UNITY_EXTENDED", "ROOTS_OF_UNITY_REDUCED"):
        comment = "noqa: E501"

    typed_value = typed_value.strip()
    if "(" not in typed_value:
        return VariableDefinition(
            type_name=None, value=typed_value, comment=comment, type_hint=type_hint
        )
    i = typed_value.index("(")
    type_name = typed_value[:i]

    return VariableDefinition(
        type_name=type_name, value=typed_value[i + 1 : -1], comment=comment, type_hint=type_hint
    )


def _update_constant_vars_with_kzg_setups(
    constant_vars: dict[str, VariableDefinition],
    preset_dep_constant_vars: dict[str, VariableDefinition],
    preset_name: str,
) -> None:
    comment = "noqa: E501"
    kzg_setups = ALL_KZG_SETUPS[preset_name]
    preset_dep_constant_vars["KZG_SETUP_G1_MONOMIAL"] = VariableDefinition(
        preset_dep_constant_vars["KZG_SETUP_G1_MONOMIAL"].value, str(kzg_setups[0]), comment, None
    )
    preset_dep_constant_vars["KZG_SETUP_G1_LAGRANGE"] = VariableDefinition(
        preset_dep_constant_vars["KZG_SETUP_G1_LAGRANGE"].value, str(kzg_setups[1]), comment, None
    )
    constant_vars["KZG_SETUP_G2_MONOMIAL"] = VariableDefinition(
        constant_vars["KZG_SETUP_G2_MONOMIAL"].value, str(kzg_setups[2]), comment, None
    )


def _update_constant_vars_with_curdleproofs_crs(
    constant_vars: dict[str, VariableDefinition], preset_name: str
) -> None:
    comment = "noqa: E501"
    constant_vars["CURDLEPROOFS_CRS"] = VariableDefinition(
        None,
        "curdleproofs.CurdleproofsCrs.from_json(json.dumps("
        + str(ALL_CURDLEPROOFS_CRS[str(preset_name)]).replace("0x", "")
        + "))",
        comment,
        None,
    )


@lru_cache(maxsize=None)
def parse_markdown(content: str) -> Document:
    return gfm.parse(content)


def check_yaml_matches_spec(
    var_name: str, yaml: Mapping[str, str | list[dict[str, str]]], value_def: VariableDefinition
) -> None:
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
            value = yaml[var]
            if isinstance(value, str):
                updated_value = updated_value.replace(var, value)

            else:
                raise ValueError(f"Variable {var} should be a string in the yaml file.")
    try:
        assert yaml[var_name] == repr(eval(updated_value)), (
            f"mismatch for {var_name}: {yaml[var_name]} vs {eval(updated_value)}"
        )
    except NameError:
        # Okay it's probably something more serious, let's ignore
        pass


def _has_decorator(decorateable: ast.ClassDef | ast.FunctionDef, name: str) -> bool:
    return any(_is_decorator(d, name) for d in decorateable.decorator_list)


def _is_decorator(decorator: ast.expr, name: str) -> bool:
    return (
        (isinstance(decorator, ast.Name) and decorator.id == name)
        or (isinstance(decorator, ast.Attribute) and decorator.attr == name)
        or (isinstance(decorator, ast.Call) and decorator.func.id == name)
        or (isinstance(decorator, ast.Subscript) and decorator.value.id == name)
    )
