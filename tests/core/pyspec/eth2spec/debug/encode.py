from eth2spec.utils.ssz.ssz_impl import hash_tree_root, serialize
from eth2spec.utils.ssz.ssz_typing import (
    Bitlist,
    Bitvector,
    boolean,
    CompatibleUnion,
    Container,
    List,
    ProgressiveBitlist,
    ProgressiveContainer,
    ProgressiveList,
    uint,
    Union,
    Vector,
)


def encode(value, include_hash_tree_roots=False):
    if isinstance(value, uint):
        # Larger uints are boxed and the class declares their byte length
        if value.__class__.type_byte_length() > 8:
            return str(int(value))
        return int(value)
    elif isinstance(value, boolean):
        return value == 1
    elif isinstance(value, Bitlist | ProgressiveBitlist | Bitvector):
        return "0x" + serialize(value).hex()
    elif isinstance(value, list):  # normal python lists
        return [encode(element, include_hash_tree_roots) for element in value]
    elif isinstance(value, List | ProgressiveList | Vector):
        return [encode(element, include_hash_tree_roots) for element in value]
    elif isinstance(value, bytes):  # bytes, ByteList, ByteVector
        return "0x" + value.hex()
    elif isinstance(value, Container | ProgressiveContainer):
        ret = {}
        for field_name in value.fields().keys():
            field_value = getattr(value, field_name)
            ret[field_name] = encode(field_value, include_hash_tree_roots)
            if include_hash_tree_roots:
                ret[field_name + "_hash_tree_root"] = "0x" + hash_tree_root(field_value).hex()
        if include_hash_tree_roots:
            ret["hash_tree_root"] = "0x" + hash_tree_root(value).hex()
        return ret
    elif isinstance(value, Union):
        inner_value = value.value()
        return {
            "selector": int(value.selector()),
            "value": None if inner_value is None else encode(inner_value, include_hash_tree_roots),
        }
    elif isinstance(value, CompatibleUnion):
        return {
            "selector": encode(value.selector()),
            "data": encode(value.data(), include_hash_tree_roots),
        }
    else:
        raise Exception(f"Type not recognized: value={value}, typ={type(value)}")
