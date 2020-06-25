from typing import Type, cast
from remerkleable.core import TypeDef, View, BackedView, BasicTypeDef, BasicView
from remerkleable.tree import Link, to_gindex


class SubtreeView(BackedView, TypeDef):
    @classmethod
    def is_packed(cls) -> bool:
        raise NotImplementedError

    @classmethod
    def tree_depth(cls) -> int:
        raise NotImplementedError

    @classmethod
    def item_elem_cls(cls, i: int) -> Type[View]:
        raise NotImplementedError

    def get(self, i: int) -> View:
        elem_type: Type[View] = self.item_elem_cls(i)
        # basic types are more complicated: we operate on subsections packed into a bottom chunk
        if self.is_packed():
            elems_per_chunk = 32 // elem_type.type_byte_length()
            chunk_i = i // elems_per_chunk
            chunk = self.get_backing().getter(to_gindex(chunk_i, self.tree_depth()))
            return cast(Type[BasicView], elem_type).basic_view_from_backing(chunk, i % elems_per_chunk)
        else:
            return elem_type.view_from_backing(
                self.get_backing().getter(to_gindex(i, self.tree_depth())), lambda v: self.set(i, v))

    def set(self, i: int, v: View) -> None:
        elem_type: Type[View] = self.item_elem_cls(i)
        # if not the right type, try to coerce it
        if not isinstance(v, elem_type):
            v = elem_type.coerce_view(v)
        if self.is_packed():
            # basic types are more complicated: we operate on a subsection of a bottom chunk
            if isinstance(elem_type, BasicTypeDef):
                if not isinstance(v, BasicView):
                    raise Exception("input element is not a basic view")
                basic_v: BasicView = v
                elems_per_chunk = 32 // elem_type.type_byte_length()
                chunk_i = i // elems_per_chunk
                target = to_gindex(chunk_i, self.tree_depth())
                chunk_setter_link: Link = self.get_backing().setter(target)
                chunk = self.get_backing().getter(target)
                new_chunk = basic_v.backing_from_base(chunk, i % elems_per_chunk)
                self.set_backing(chunk_setter_link(new_chunk))
            else:
                raise Exception("cannot pack subtree elements that are not basic types")
        else:
            setter_link: Link = self.get_backing().setter(to_gindex(i, self.tree_depth()))
            self.set_backing(setter_link(v.get_backing()))
