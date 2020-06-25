from typing import Protocol, Optional
from remerkleable.tree import Node, Root, RebindableNode, NavigationError


class VirtualSource(Protocol):
    def get_left(self, key: Root) -> Node:
        ...

    def get_right(self, key: Root) -> Node:
        ...

    def is_leaf(self, key: Root) -> bool:
        ...


class VirtualNode(RebindableNode, Node):
    """A node that instead of lazily computing the root, lazily fetches the left and right child based on the root."""

    _root: Root
    _src: VirtualSource
    _is_leaf: Optional[bool] = None
    _left: Optional[Node] = None
    _right: Optional[Node] = None

    def __init__(self, root: Root, src: VirtualSource):
        self._root = root
        self._src = src

    def get_left(self) -> Node:
        if self._left is None:
            if self._is_leaf is None or self._is_leaf is False:
                self._left = self._src.get_left(self._root)
            else:
                raise NavigationError("Virtual node is a leaf node, cannot get left child node.")
        return self._left

    def get_right(self) -> Node:
        if self._right is None:
            if self._is_leaf is None or self._is_leaf is False:
                self._right = self._src.get_right(self._root)
            else:
                raise NavigationError("Virtual node is a leaf node, cannot get right child node.")
        return self._right

    def is_leaf(self) -> bool:
        if self._is_leaf is None:
            self._is_leaf = self._src.is_leaf(self._root)
        return self._is_leaf

    @property
    def root(self) -> Root:
        return self._root

    def merkle_root(self) -> Root:
        return self._root

    def __repr__(self):
        return f"0x{self._root.hex()}"
