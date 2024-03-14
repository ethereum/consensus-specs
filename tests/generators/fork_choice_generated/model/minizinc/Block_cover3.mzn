include "globals.mzn";

int: AE;
int: MB = 4;

set of int: EPOCH = AE..(AE+MB-1);
set of int: BLOCK = 0..MB;

type BS = record(EPOCH: e, EPOCH: je, EPOCH: uje);


array[BLOCK] of var EPOCH: es;
array[BLOCK] of var EPOCH: pjes;
array[BLOCK] of var EPOCH: cjes;
array[BLOCK] of var EPOCH: ujes;
array[BLOCK] of var bool: prevs;
array[BLOCK] of var bool: currs;
array[BLOCK] of var BLOCK: ancestors;

function var EPOCH: n_e(var BLOCK: b) = es[b] + 1;
function var EPOCH: n_pje(var BLOCK: b) = cjes[b];
function var EPOCH: n_cje(var BLOCK: b) =
  if currs[b] then
    es[b]
  elseif prevs[b] then
    es[b] - 1
  else
    cjes[b]
  endif;

constraint es[0] == AE;
constraint pjes[0] == AE /\ cjes[0] == AE;
constraint forall(b in BLOCK)(if b > 0 then ancestors[b] < b else ancestors[b] == b endif);

var BLOCK: max_block;

constraint forall(b in BLOCK where b <= max_block /\ b > 0)(n_e(ancestors[b]) == es[b] /\ n_pje(ancestors[b]) == pjes[b] /\ n_cje(ancestors[b]) == cjes[b]);
constraint forall(b in BLOCK where b <= max_block)(ujes[b] == n_cje(b));

function var EPOCH: get_vse(var BLOCK: b) =
  if es[b] < curr_e then n_cje(b) else cjes[b] endif;

var EPOCH: curr_e;
var EPOCH: store_je;

constraint forall(b in BLOCK where b <= max_block)(es[b] <= curr_e);
constraint forall(b in BLOCK where b <= max_block)(get_vse(b) <= store_je);
constraint exists(b in BLOCK where b <= max_block)(get_vse(b) == store_je);

predicate is_leaf(var BLOCK: b) = not exists(c in BLOCK where c <= max_block)(ancestors[c] == b);

var BLOCK: target_block;
constraint target_block <= max_block;

bool: store_je_eq_zero;
bool: block_vse_eq_store_je;
bool: block_vse_plus_two_ge_curr_e;
bool: block_is_leaf;
bool: block_is_justified_descendant;

constraint block_vse_eq_store_je <-> get_vse(target_block) == store_je;
constraint block_vse_plus_two_ge_curr_e <-> get_vse(target_block) + 2 >= curr_e;
constraint block_is_leaf <-> is_leaf(target_block);
constraint block_is_justified_descendant <-> es[target_block] >= store_je;
constraint store_je_eq_zero <-> store_je == 0;
