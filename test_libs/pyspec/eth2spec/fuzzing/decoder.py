from eth2spec.utils.ssz import ssz_typing as spec_ssz
import ssz


def translate_typ(typ) -> ssz.BaseSedes:
    """
    Translates a spec type to a Py-SSZ type description (sedes).
    :param typ: The spec type, a class.
    :return: The Py-SSZ equivalent.
    """
    if spec_ssz.is_container_type(typ):
        return ssz.Container(
            [translate_typ(field_typ) for (field_name, field_typ) in typ.get_fields()])
    elif spec_ssz.is_bytesn_type(typ):
        return ssz.ByteVector(typ.length)
    elif spec_ssz.is_bytes_type(typ):
        return ssz.ByteList()
    elif spec_ssz.is_vector_type(typ):
        return ssz.Vector(translate_typ(spec_ssz.read_vector_elem_type(typ)), typ.length)
    elif spec_ssz.is_list_type(typ):
        return ssz.List(translate_typ(spec_ssz.read_list_elem_type(typ)))
    elif spec_ssz.is_bool_type(typ):
        return ssz.boolean
    elif spec_ssz.is_uint_type(typ):
        size = spec_ssz.uint_byte_size(typ)
        if size == 1:
            return ssz.uint8
        elif size == 2:
            return ssz.uint16
        elif size == 4:
            return ssz.uint32
        elif size == 8:
            return ssz.uint64
        elif size == 16:
            return ssz.uint128
        elif size == 32:
            return ssz.uint256
        else:
            raise TypeError("invalid uint size")
    else:
        raise TypeError("Type not supported: {}".format(typ))


def translate_value(value, typ):
    """
    Translate a value output from Py-SSZ deserialization into the given spec type.
    :param value: The PySSZ value
    :param typ: The type from the spec to translate into
    :return: the translated value
    """
    if spec_ssz.is_uint_type(typ):
        size = spec_ssz.uint_byte_size(typ)
        if size == 1:
            return spec_ssz.uint8(value)
        elif size == 2:
            return spec_ssz.uint16(value)
        elif size == 4:
            return spec_ssz.uint32(value)
        elif size == 8:
            # uint64 is default (TODO this is changing soon)
            return value
        elif size == 16:
            return spec_ssz.uint128(value)
        elif size == 32:
            return spec_ssz.uint256(value)
        else:
            raise TypeError("invalid uint size")
    elif spec_ssz.is_list_type(typ):
        elem_typ = spec_ssz.read_elem_type(typ)
        return [translate_value(elem, elem_typ) for elem in value]
    elif spec_ssz.is_bool_type(typ):
        return value
    elif spec_ssz.is_vector_type(typ):
        elem_typ = spec_ssz.read_elem_type(typ)
        return typ(*(translate_value(elem, elem_typ) for elem in value))
    elif spec_ssz.is_bytesn_type(typ):
        return typ(value)
    elif spec_ssz.is_bytes_type(typ):
        return value
    elif spec_ssz.is_container_type(typ):
        return typ(**{f_name: translate_value(f_val, f_typ) for (f_name, f_val, f_typ)
                      in zip(typ.get_field_names(), value, typ.get_field_types())})
    else:
        raise TypeError("Type not supported: {}".format(typ))
