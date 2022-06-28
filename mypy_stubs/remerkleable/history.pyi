from remerkleable.tree import Gindex as Gindex, Node as Node, ROOT_GINDEX as ROOT_GINDEX, get_anchor_gindex as get_anchor_gindex
from typing import List, Tuple, TypeVar

K = TypeVar('K')
History = List[Tuple[K, Node]]

def get_target_history(history: History, target: Gindex) -> History: ...
