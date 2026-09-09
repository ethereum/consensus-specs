% Reusable queue-capacity profile.
%
% EMPTY and AVAILABLE distinguish input/output queue shapes that are both below
% capacity; FULL derives the gate used by handlers that reject or stop appends.

enum QueueCapacity = { EMPTY, AVAILABLE, FULL };

predicate queue_capacity_ok(var QueueCapacity: capacity, var bool: full) =
    full <-> capacity == FULL;
