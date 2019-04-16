from eth2spec.utils.minimal_ssz import hash_tree_root


def decode(json, typ):
    if isinstance(typ, str) and typ[:4] == 'uint':
        return json
    elif typ == 'bool':
        assert json in (True, False)
        return json
    elif isinstance(typ, list):
        return [decode(element, typ[0]) for element in json]
    elif isinstance(typ, str) and typ[:4] == 'byte':
        return bytes.fromhex(json[2:])
    elif hasattr(typ, 'fields'):
        temp = {}
        for field, subtype in typ.fields.items():
            temp[field] = decode(json[field], subtype)
            if field + "_hash_tree_root" in json:
                assert(json[field + "_hash_tree_root"][2:] == 
                       hash_tree_root(temp[field], subtype).hex())
        ret = typ(**temp)
        if "hash_tree_root" in json:
            assert(json["hash_tree_root"][2:] == 
                   hash_tree_root(ret, typ).hex())
        return ret
    else:
        print(json, typ)
        raise Exception("Type not recognized")
