from eth_utils import encode_hex
from ruamel.yaml import YAML
from snappy import compress

from eth2spec.test import context

from .gen_typing import TestCase


def get_default_yaml():
    yaml = YAML(pure=True)
    yaml.default_flow_style = None

    def _represent_none(self, _):
        return self.represent_scalar("tag:yaml.org,2002:null", "null")

    def _represent_str(self, data):
        if data.startswith("0x"):
            # Without this, a zero-byte hex string is represented without quotes.
            return self.represent_scalar("tag:yaml.org,2002:str", data, style="'")
        return self.represent_str(data)

    yaml.representer.add_representer(type(None), _represent_none)
    yaml.representer.add_representer(str, _represent_str)

    return yaml


def get_cfg_yaml():
    # Spec config is using a YAML subset
    cfg_yaml = YAML(pure=True)
    cfg_yaml.default_flow_style = False  # Emit separate line for each key
    cfg_yaml.width = 1024  # Do not wrap long lines
    cfg_yaml.indent(mapping=2, sequence=4, offset=2)  # Indent BLOB_SCHEDULE

    def cfg_represent_bytes(self, data):
        return self.represent_int(encode_hex(data))

    def cfg_represent_quoted_str(self, data):
        return self.represent_scalar("tag:yaml.org,2002:str", data, style="'")

    cfg_yaml.representer.add_representer(bytes, cfg_represent_bytes)
    cfg_yaml.representer.add_representer(context.quoted_str, cfg_represent_quoted_str)

    return cfg_yaml


class Dumper:
    """Helper for dumping test case outputs (cfg, data, meta, ssz)."""

    def __init__(self, default_yaml: YAML = None, cfg_yaml: YAML = None):
        self.default_yaml = default_yaml or get_default_yaml()
        self.cfg_yaml = cfg_yaml or get_cfg_yaml()

    def dump_meta(self, test_case: TestCase, meta: dict) -> None:
        if not meta:
            return
        self._dump_yaml(test_case, "meta", meta, self.default_yaml)

    def dump_cfg(self, test_case: TestCase, name: str, data: any) -> None:
        self._dump_yaml(test_case, name, data, self.cfg_yaml)

    def dump_data(self, test_case: TestCase, name: str, data: any) -> None:
        self._dump_yaml(test_case, name, data, self.default_yaml)

    def dump_ssz(self, test_case: TestCase, name: str, data: bytes) -> None:
        """Compress and write SSZ data for test case."""
        path = test_case.dir / f"{name}.ssz_snappy"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            f.write(compress(data))

    def dump_manifest(self, test_case: TestCase) -> None:
        """Write manifest.yml file containing test case metadata."""
        manifest_data = {
            'config_name': test_case.preset_name,
            'fork_name': test_case.fork_name,
            'runner_name': test_case.runner_name,
            'handler_name': test_case.handler_name,
            'suite_name': test_case.suite_name,
            'case_name': test_case.case_name,
        }
        # Use cfg_yaml which has block style formatting (default_flow_style=False)
        # This ensures each field appears on a separate line, matching data.yaml format
        self._dump_yaml(test_case, "manifest", manifest_data, self.cfg_yaml)


    def _dump_yaml(self, test_case: TestCase, name: str, data: any, yaml_encoder: YAML) -> None:
        """Helper to write YAML files for test case."""
        path = test_case.dir / f"{name}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            yaml_encoder.dump(data, f)
