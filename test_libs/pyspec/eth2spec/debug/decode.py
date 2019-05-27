from eth2spec.utils.ssz.ssz_impl import hash_tree_root
from eth2spec.utils.ssz.ssz_typing import *


def decode(data, typ):
    if is_uint(typ):
        return data
    elif is_bool_type(typ):
        assert data in (True, False)
        return data
    elif issubclass(typ, list):
        elem_typ = read_list_elem_typ(typ)
        return [decode(element, elem_typ) for element in data]
    elif issubclass(typ, Vector):
        elem_typ = read_vector_elem_typ(typ)
        return Vector(decode(element, elem_typ) for element in data)
    elif issubclass(typ, bytes):
        return bytes.fromhex(data[2:])
    elif issubclass(typ, BytesN):
        return BytesN(bytes.fromhex(data[2:]))
    elif is_container_typ(typ):
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
        print(data, typ)
        raise Exception("Type not recognized")
