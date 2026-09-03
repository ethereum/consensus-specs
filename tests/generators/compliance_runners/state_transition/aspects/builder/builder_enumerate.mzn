% Enumeration model for the builder aspect.
%
% Declares a single unrestricted Builder decision variable subject to
% builder_constraints so all feasible Builder solutions can be enumerated
% (see builder_sweep_materializer._enumerate_all_builder_solutions).

include "builder.mzn";

var Builder: b;

constraint builder_constraints(b);

solve satisfy;
