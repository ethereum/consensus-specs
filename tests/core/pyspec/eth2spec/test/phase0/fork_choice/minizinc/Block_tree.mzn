include "globals.mzn";

set of int: BLOCKS = 0..7;

array[BLOCKS] of var BLOCKS: parent;
array[BLOCKS] of var set of BLOCKS: children;
array[BLOCKS] of var int: depths;
array[BLOCKS] of var int: widths;

function var int: count_children(var BLOCKS: block) =
  sum(ch in BLOCKS)(if ch != 0 /\ parent[ch] == block then 1 else 0 endif);

function var int: sub_tree_size(var BLOCKS: block) =
  if count_children(block) == 0 then
    1
  else
    sum(ch in BLOCKS)(if ch != 0 /\ parent[ch] == block then sub_tree_size(ch) else 0 endif)
  endif;


array[BLOCKS] of var int: tst;
array[BLOCKS] of var int: tst2;

constraint forall(b in BLOCKS)(tst[b] == count_children(b));
constraint forall(b in BLOCKS)(tst2[b] == card(children[b]));
constraint int_set_channel(parent, children);
constraint forall(b in BLOCKS)(if b == 0 then depths[b] == 0 else depths[b] == depths[parent[b]] + 1 endif);

constraint forall(b in BLOCKS)(if b != 0 then parent[b] < b else parent[b] == b endif);
constraint forall(b in BLOCKS)(count_children(b) <= 2);
constraint forall(b in BLOCKS)(depths[b] <= 5);
constraint forall(b in BLOCKS)(widths[b] == sub_tree_size(b));