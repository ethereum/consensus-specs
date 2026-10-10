% Shared value domains for coverage dimensions.
%
% One enum carries every coverage value plus NA, so a not-applicable dimension
% can be marked NA regardless of whether it is a comparison or a boolean.
% Comparison dimensions range over CMP (or CMP_NA when guarded); boolean
% coverage dimensions over BOOLV (or BOOLV_NA when guarded).
%
%   NA marks a dimension that is not applicable (its value cannot be recovered
%   from the input vector). It is distinct from an applicable-but-unreached
%   dimension, which keeps a real value.

enum Dim = { LT, EQ, GT, F, T, NA };

set of Dim: CMP      = { LT, EQ, GT };
set of Dim: CMP_NA   = { LT, EQ, GT, NA };
set of Dim: BOOLV    = { F, T };
set of Dim: BOOLV_NA = { F, T, NA };
