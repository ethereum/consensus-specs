from eth2spec.utils.ssz.ssz_impl import hash_tree_root
from eth2spec.utils.ssz.ssz_typing import (
    is_uint_type, is_bool_type, is_list_type,
    is_vector_type, is_bytes_type, is_bytesn_type, is_container_type,
    read_vector_elem_type, read_list_elem_type,
    Vector, BytesN
)


def decode(data, typ):
    if is_uint_type(typ):
        return data
    elif is_bool_type(typ):
        assert data in (True, False)
        return data
    elif is_list_type(typ):
        elem_typ = read_list_elem_type(typ)
        return [decode(element, elem_typ) for element in data]
    elif is_vector_type(typ):
        elem_typ = read_vector_elem_type(typ)
        return Vector(decode(element, elem_typ) for element in data)
    elif is_bytes_type(typ):
        return bytes.fromhex(data[2:])
    elif is_bytesn_type(typ):
        return BytesN(bytes.fromhex(data[2:]))
    elif is_container_type(typ):
        temp = {}
        for field, subtype in typ.get_fields():
            temp[field] = decode(data[field], subtype)
            if field + "_hash_tree_root" in data:
                assert(data[field + "_hash_tree_root"][2:] ==
                       hash_tree_root(temp[field], subtype).hex())
        ret = typ(**temp)
        if "hash_tree_root" in data:
            assert(data["hash_tree_root"][2:] ==
                   hash_tree_root(ret, typ).hex())
        return ret
    else:
        raise Exception(f"Type not recognized: data={data}, typ={typ}")
