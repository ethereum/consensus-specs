from pathlib import Path

import pytest

from pysetup.mk_to_spec import MarkdownToSpec


@pytest.fixture
def dummy_preset():
    return {"EXAMPLE": "1"}


@pytest.fixture
def dummy_config():
    return {"CONFIG": "2"}


@pytest.fixture
def dummy_file(tmp_path):
    file = tmp_path / "dummy.md"
    file.write_text("# Dummy\n")
    return file


def test_constructor_initializes_fields(dummy_file, dummy_preset, dummy_config):
    preset_name = "mainnet"
    m2s = MarkdownToSpec(
        file_name=Path(dummy_file),
        preset=dummy_preset,
        config=dummy_config,
        preset_name=preset_name,
    )
    assert m2s.preset == dummy_preset
    assert m2s.config == dummy_config
    assert m2s.preset_name == preset_name
    assert isinstance(m2s.spec, dict)
    assert isinstance(m2s.all_custom_types, dict)
    assert hasattr(m2s, "document_iterator")
    assert m2s.current_heading_name is None


def test_run_returns_spec_object(dummy_file, dummy_preset, dummy_config):
    preset_name = "mainnet"
    m2s = MarkdownToSpec(
        file_name=Path(dummy_file),
        preset=dummy_preset,
        config=dummy_config,
        preset_name=preset_name,
    )
    spec_obj = m2s.run()
    # Check that the result is of the expected type
    from pysetup.typing import SpecObject

    assert isinstance(spec_obj, SpecObject)


def test_run_includes_table_in_specobject(tmp_path, dummy_preset, dummy_config):
    # Create a markdown file with a simple markdown table
    md_content = """
# Example

| Name    | Value        | Description       |
|---------|--------------|------------------|
| CONST_A | uint64(42)   | Example constant |
| CONST_B | Bytes32(0x01)| Another constant |
"""
    file = tmp_path / "table.md"
    file.write_text(md_content)
    m2s = MarkdownToSpec(
        file_name=Path(file),
        preset=dummy_preset,
        config=dummy_config,
        preset_name="mainnet",
    )
    spec_obj = m2s.run()
    # The constant should be present in the SpecObject's constant_vars
    assert "CONST_A" in spec_obj.constant_vars
    assert spec_obj.constant_vars["CONST_A"].type_name == "uint64"
    assert spec_obj.constant_vars["CONST_A"].value == "42"
    assert "CONST_B" in spec_obj.constant_vars
    assert spec_obj.constant_vars["CONST_B"].type_name == "Bytes32"
    assert spec_obj.constant_vars["CONST_B"].value == "0x01"


def test_run_includes_list_of_records_table(tmp_path, dummy_preset, dummy_config):
    md_content = """
<!-- list-of-records:blob_schedule -->

| Epoch                       | Max Blobs Per Block | Description                      |
| --------------------------- | ------------------- | -------------------------------- |
| `Epoch(269568)` **Deneb**   | `uint64(6)`         | The limit is set to `6` blobs    |
| `Epoch(364032)` **Electra** | `uint64(9)`         | The limit is raised to `9` blobs |
"""
    file = tmp_path / "list_of_records.md"
    file.write_text(md_content)
    # The config must have a 'BLOB_SCHEDULE' key with the expected structure for mainnet
    config = dummy_config.copy()
    config["BLOB_SCHEDULE"] = [
        {"EPOCH": "269568", "MAX_BLOBS_PER_BLOCK": "6"},
        {"EPOCH": "364032", "MAX_BLOBS_PER_BLOCK": "9"},
    ]
    m2s = MarkdownToSpec(
        file_name=Path(file),
        preset=dummy_preset,
        config=config,
        preset_name="mainnet",
    )
    spec_obj = m2s.run()
    # The result should have 'BLOB_SCHEDULE' in config_vars
    assert "BLOB_SCHEDULE" in spec_obj.config_vars
    # The value should be a list of dicts with type constructors applied
    assert isinstance(spec_obj.config_vars["BLOB_SCHEDULE"], list)
    assert spec_obj.config_vars["BLOB_SCHEDULE"][0]["EPOCH"] == "Epoch(269568)"
    assert spec_obj.config_vars["BLOB_SCHEDULE"][0]["MAX_BLOBS_PER_BLOCK"] == "uint64(6)"
    assert spec_obj.config_vars["BLOB_SCHEDULE"][1]["EPOCH"] == "Epoch(364032)"
    assert spec_obj.config_vars["BLOB_SCHEDULE"][1]["MAX_BLOBS_PER_BLOCK"] == "uint64(9)"


def test_run_includes_list_of_records_table_minimal(tmp_path, dummy_preset, dummy_config):
    md_content = """
<!-- list-of-records:blob_schedule -->

| Epoch                       | Max Blobs Per Block | Description                      |
| --------------------------- | ------------------- | -------------------------------- |
| `Epoch(269568)` **Deneb**   | `uint64(6)`         | The limit is set to `6` blobs    |
| `Epoch(364032)` **Electra** | `uint64(9)`         | The limit is raised to `9` blobs |
"""
    file = tmp_path / "list_of_records_minimal.md"
    file.write_text(md_content)
    config = dummy_config.copy()
    # Use different values than the table for minimal preset
    config["BLOB_SCHEDULE"] = [
        {"EPOCH": "2", "MAX_BLOBS_PER_BLOCK": "3"},
        {"EPOCH": "4", "MAX_BLOBS_PER_BLOCK": "5"},
    ]
    m2s = MarkdownToSpec(
        file_name=Path(file),
        preset=dummy_preset,
        config=config,
        preset_name="minimal",
    )
    spec_obj = m2s.run()
    assert "BLOB_SCHEDULE" in spec_obj.config_vars
    assert isinstance(spec_obj.config_vars["BLOB_SCHEDULE"], list)
    # The result should follow the config, not the table
    assert spec_obj.config_vars["BLOB_SCHEDULE"][0]["EPOCH"] == "Epoch(2)"
    assert spec_obj.config_vars["BLOB_SCHEDULE"][0]["MAX_BLOBS_PER_BLOCK"] == "uint64(3)"
    assert spec_obj.config_vars["BLOB_SCHEDULE"][1]["EPOCH"] == "Epoch(4)"
    assert spec_obj.config_vars["BLOB_SCHEDULE"][1]["MAX_BLOBS_PER_BLOCK"] == "uint64(5)"


def test_run_includes_python_function(tmp_path, dummy_preset, dummy_config):
    md_content = """
#### `compute_epoch_at_slot`

```python
def compute_epoch_at_slot(slot: Slot) -> Epoch:
    \"\"\"
    Return the epoch number at slot.
    \"\"\"
    return Epoch(slot // SLOTS_PER_EPOCH)
```
"""
    file = tmp_path / "function.md"
    file.write_text(md_content)
    m2s = MarkdownToSpec(
        file_name=Path(file),
        preset=dummy_preset,
        config=dummy_config,
        preset_name="mainnet",
    )
    spec_obj = m2s.run()
    # The function should be present in the SpecObject's functions
    assert "compute_epoch_at_slot" in spec_obj.functions
    func_src = spec_obj.functions["compute_epoch_at_slot"]
    assert "def compute_epoch_at_slot(slot: Slot) -> Epoch" in func_src
    assert "return Epoch(slot // SLOTS_PER_EPOCH)" in func_src


def test_run_includes_python_class_container(tmp_path, dummy_preset, dummy_config):
    md_content = """
#### `Checkpoint`

```python
class Checkpoint(Container):
    epoch: Epoch
    root: Root
```
"""
    file = tmp_path / "class_container.md"
    file.write_text(md_content)
    m2s = MarkdownToSpec(
        file_name=Path(file),
        preset=dummy_preset,
        config=dummy_config,
        preset_name="mainnet",
    )
    spec_obj = m2s.run()
    # The class should be present in the SpecObject's ssz_objects
    assert "Checkpoint" in spec_obj.ssz_objects
    class_src = spec_obj.ssz_objects["Checkpoint"]
    assert "class Checkpoint(Container):" in class_src
    assert "epoch: Epoch" in class_src
    assert "root: Root" in class_src


def test_run_includes_python_dataclass(tmp_path, dummy_preset, dummy_config):
    md_content = """
## Helpers

### `PayloadAttributes`

Used to signal to initiate the payload build process via `notify_forkchoice_updated`.

```python
@dataclass
class PayloadAttributes(object):
    timestamp: uint64
    prev_randao: Bytes32
    suggested_fee_recipient: ExecutionAddress
```
"""
    file = tmp_path / "dataclass.md"
    file.write_text(md_content)
    m2s = MarkdownToSpec(
        file_name=Path(file),
        preset=dummy_preset,
        config=dummy_config,
        preset_name="mainnet",
    )
    spec_obj = m2s.run()
    # The dataclass should be present in the SpecObject's dataclasses
    assert "PayloadAttributes" in spec_obj.dataclasses
    class_src = spec_obj.dataclasses["PayloadAttributes"]
    assert "@dataclass" in class_src
    assert "class PayloadAttributes(object):" in class_src
    assert "timestamp: uint64" in class_src
    assert "prev_randao: Bytes32" in class_src
    assert "suggested_fee_recipient: ExecutionAddress" in class_src


def test_run_skips_predefined_type_rows(tmp_path, dummy_preset, dummy_config):
    md_content = """
## Cryptographic types

| Name                                                                                                                                                    | SSZ equivalent                                       | Description                                                  |
| ------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------ |
| [`PolynomialCoeff`](https://github.com/ethereum/consensus-specs/blob/36a5719b78523c057065515c8f8fcaeba75d065b/pysetup/spec_builders/eip7594.py#L20-L24) | `List[BLSFieldElement, FIELD_ELEMENTS_PER_EXT_BLOB]` | <!-- predefined-type --> A polynomial in coefficient form    |
| [`Coset`](https://github.com/ethereum/consensus-specs/blob/36a5719b78523c057065515c8f8fcaeba75d065b/pysetup/spec_builders/eip7594.py#L27-L33)           | `Vector[BLSFieldElement, FIELD_ELEMENTS_PER_CELL]`   | <!-- predefined-type --> The evaluation domain of a cell     |
| [`CosetEvals`](https://github.com/ethereum/consensus-specs/blob/36a5719b78523c057065515c8f8fcaeba75d065b/pysetup/spec_builders/eip7594.py#L36-L42)      | `Vector[BLSFieldElement, FIELD_ELEMENTS_PER_CELL]`   | <!-- predefined-type --> A cell's evaluations over its coset |
"""
    file = tmp_path / "predefined_types.md"
    file.write_text(md_content)
    m2s = MarkdownToSpec(
        file_name=Path(file),
        preset=dummy_preset,
        config=dummy_config,
        preset_name="mainnet",
    )
    spec_obj = m2s.run()
    # These should not be in custom_types or constant_vars due to <!-- predefined-type -->
    assert "PolynomialCoeff" not in spec_obj.custom_types
    assert "Coset" not in spec_obj.custom_types
    assert "CosetEvals" not in spec_obj.custom_types
    assert "PolynomialCoeff" not in spec_obj.constant_vars
    assert "Coset" not in spec_obj.constant_vars
    assert "CosetEvals" not in spec_obj.constant_vars


def test_run_skips_eth2spec_skip_code_block(tmp_path, dummy_preset, dummy_config):
    md_content = """
## Helpers

### `PayloadAttributes`

Used to signal to initiate the payload build process via `notify_forkchoice_updated`.

<!-- eth2spec: skip -->
```python
@dataclass
class PayloadAttributes(object):
    timestamp: uint64
    prev_randao: Bytes32
    suggested_fee_recipient: ExecutionAddress
```
"""
    file = tmp_path / "dataclass_skip.md"
    file.write_text(md_content)
    m2s = MarkdownToSpec(
        file_name=Path(file),
        preset=dummy_preset,
        config=dummy_config,
        preset_name="mainnet",
    )
    spec_obj = m2s.run()
    # The dataclass should NOT be present in the SpecObject's dataclasses
    assert "PayloadAttributes" not in spec_obj.dataclasses


def test_finalize_types_called_and_updates_custom_types(
    tmp_path, dummy_preset, dummy_config, monkeypatch
):
    # Minimal markdown with a type definition
    md_content = """
# Types

| Name             | SSZ equivalent | Description                       |
| ---------------- | -------------- | --------------------------------- |
| `Slot`           | `uint64`       | a slot number                     |
| `Epoch`          | `uint64`       | an epoch number                   |
"""
    file = tmp_path / "types.md"
    file.write_text(md_content)
    m2s = MarkdownToSpec(
        file_name=Path(file),
        preset=dummy_preset,
        config=dummy_config,
        preset_name="mainnet",
    )

    # Spy on _finalize_types
    called = {}
    orig_finalize_types = m2s._finalize_types

    def spy_finalize_types():
        called["ran"] = True
        return orig_finalize_types()

    monkeypatch.setattr(m2s, "_finalize_types", spy_finalize_types)

    spec_obj = m2s.run()
    assert called.get("ran") is True
    # After _finalize_types, custom_types should include 'Slot' and 'Epoch'
    assert spec_obj.custom_types["Slot"] == "uint64"
    assert spec_obj.custom_types["Epoch"] == "uint64"
