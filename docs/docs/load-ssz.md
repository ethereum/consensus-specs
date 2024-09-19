# Load SSZ file into Pyspec SSZ object

## Common file formats

### Beacon APIs response

The [Beacon APIs](https://github.com/ethereum/beacon-APIs) return JSON format response. In case of a successful response, the requested object can be found within the `response['data']` field.

#### Helpers

##### `eth2spec.debug.tools.get_ssz_object_from_json_file`

```python
get_ssz_object_from_json_file(container: Container, file_path: str) -> SSZObject
```

Get the `SSZObject` from a specific JSON file.

###### Arguments
- `container: Container`: the SSZ Container class. e.g., `BeaconState`.
- `file_path: str`: the path of the JSON file.

###### Example

```python
import eth2spec.capella.mainnet as spec
from eth2spec.debug.tools import get_ssz_object_from_json_file

file_dir = '<YOUR DIR PATH>'

# Load JSON file from Beacon API into Remerkleable Python SSZ object
pre_state = get_ssz_object_from_json_file(spec.BeaconState, f"{file_dir}/state_1.ssz")
post_state = get_ssz_object_from_json_file(spec.BeaconState, f"{file_dir}/state_2.ssz")
signed_block = get_ssz_object_from_json_file(spec.SignedBeaconBlock, f"{file_dir}/block_2.ssz")
```

### SSZ-snappy

The Pyspec test generators generate test vectors to [`consensus-spec-tests`](https://github.com/ethereum/consensus-spec-tests) in [SSZ-snappy encoded format](https://github.com/ethereum/consensus-specs/blob/master/specs/phase0/p2p-interface.md#ssz-snappy-encoding-strategy).

#### Helpers

##### `eth2spec.debug.tools.get_ssz_object_from_ssz_encoded`

```python
get_ssz_object_from_ssz_encoded(container: Container, file_path: str, is_snappy: bool=True) -> SSZObject
```

Get the `SSZObject` from a certain binary file.

###### Arguments
- `container: Container`: The SSZ Container class. e.g., `BeaconState`.
- `file_path: str`: The path of the JSON file.
- `is_snappy: bool`: If `True`, it's the SSZ-snappy encoded file; else, it's only the SSZ serialized file without snappy. Default to `True`.

###### Example
```python
import eth2spec.capella.mainnet as spec
from eth2spec.debug.tools import get_ssz_object_from_ssz_encoded

file_dir = '<YOUR DIR PATH>'

# Load SSZ-snappy file into Remerkleable Python SSZ object
pre_state = get_ssz_object_from_ssz_encoded(spec.BeaconState, f"{file_dir}/state_1.ssz_snappy")
post_state = get_ssz_object_from_ssz_encoded(spec.BeaconState, f"{file_dir}/state_2.ssz_snappy")
signed_block = get_ssz_object_from_ssz_encoded(spec.SignedBeaconBlock, f"{file_dir}/block_2.ssz_snappy")
```

#### Use script to dump a specific field to a new file

##### Installation
```sh
cd consensus-specs/scripts

pip3 install -r requirements.txt
```

##### Dump SSZ to JSON file

```
python inspect_state.py --state-path=<The path of ssz_snappy state file> --output-dir=<Your output dir> --fork=capella --field=<One field of BeaconState> --is-snappy
```

- `--state-path`: The path of SSZ-snappy state file
- `--output-dir`: The directory of the output folder
- `--fork`: The fork name. e.g., `capella`
- `--field`: The specific field of `BeaconState` that gets printed to the output file
- `--is-snappy`: The flag to indicate it's SSZ-snappy. Otherwise, it's only SSZ serialized file.
