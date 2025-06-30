include "globals.mzn";

int: NB; % num of blocks
int: MC; % max children

set of int: BLOCKS = 0..(NB-1);

array[BLOCKS] of var BLOCKS: parent;

function var int: count_children(var BLOCKS: block) =
  sum(ch in BLOCKS)(if ch != 0 /\ parent[ch] == block then 1 else 0 endif);

constraint forall(b in BLOCKS)(if b != 0 then parent[b] < b else parent[b] == b endif);
constraint forall(b in BLOCKS)(count_children(b) <= MC);
