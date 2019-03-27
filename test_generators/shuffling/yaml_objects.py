from typing import Any

import yaml


class Validator(yaml.YAMLObject):
    """ 
    A validator stub containing only the fields relevant for get_shuffling()
    """
    fields = {
        'activation_epoch': 'uint64',
        'exit_epoch': 'uint64',
        # Extra index field to ease testing/debugging
        'original_index': 'uint64',
    }

    def __init__(self, **kwargs):
        for k in self.fields.keys():
            setattr(self, k, kwargs.get(k))

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)

    def __getattribute__(self, name: str) -> Any:
        return super().__getattribute__(name)
