from remerkleable.core import BasicView as BasicView, View as View
from remerkleable.tree import Node as Node, Root as Root, RootNode as RootNode, ZERO_ROOT as ZERO_ROOT
from typing import Any, List as PyList, Optional, Sequence, Type

class BitfieldIter:
    anchor: Node
    depth: int
    i: int
    j: int
    rootIndex: int
    length: int
    currentRoot: Root
    stack: PyList[Optional[Node]]
    def __init__(self, anchor: Node, depth: int, length: int) -> Any: ...
    def __iter__(self) -> Any: ...
    def __next__(self): ...

class PackedIter:
    anchor: Node
    depth: int
    i: int
    j: int
    rootIndex: int
    length: int
    per_node: int
    currentRoot: RootNode
    elem_type: Type[BasicView]
    stack: PyList[Optional[Node]]
    def __init__(self, anchor: Node, depth: int, length: int, elem_type: Type[BasicView]) -> Any: ...
    def __iter__(self) -> Any: ...
    def __next__(self): ...

class NodeIter:
    anchor: Node
    depth: int
    i: int
    length: int
    per_node: int
    stack: PyList[Optional[Node]]
    currentRoot: Any = ...
    def __init__(self, anchor: Node, depth: int, length: int) -> Any: ...
    def __iter__(self) -> Any: ...
    def __next__(self): ...

class ComplexElemIter(NodeIter):
    reused_view: View
    def __init__(self, anchor: Node, depth: int, length: int, elem_type: Type[View]) -> Any: ...
    def __next__(self): ...

class ComplexFreshElemIter(NodeIter):
    elem_type: Type[View]
    def __init__(self, anchor: Node, depth: int, length: int, elem_type: Type[View]) -> Any: ...
    def __next__(self): ...

class ContainerElemIter(NodeIter):
    elem_types: Sequence[Type[View]]
    def __init__(self, anchor: Node, depth: int, elem_types: Sequence[Type[View]]) -> Any: ...
    def __next__(self): ...
