from pathlib import Path

from eth_consensus_specs.config.config_util import load_config_file, parse_config_vars


def test_parse_config_vars_with_list_of_dicts():
    config = parse_config_vars(
        {
            "BLOB_SCHEDULE": [
                {"EPOCH": "412672", "MAX_BLOBS_PER_BLOCK": "15"},
                {"EPOCH": "419072", "MAX_BLOBS_PER_BLOCK": "21"},
            ],
        }
    )

    assert config["BLOB_SCHEDULE"] == [
        {"EPOCH": 412672, "MAX_BLOBS_PER_BLOCK": 15},
        {"EPOCH": 419072, "MAX_BLOBS_PER_BLOCK": 21},
    ]


def test_load_mainnet_config_with_blob_schedule():
    repo_root = Path(__file__).resolve().parents[5]
    config = load_config_file(repo_root / "configs" / "mainnet.yaml")

    assert config["BLOB_SCHEDULE"] == [
        {"EPOCH": 412672, "MAX_BLOBS_PER_BLOCK": 15},
        {"EPOCH": 419072, "MAX_BLOBS_PER_BLOCK": 21},
    ]
