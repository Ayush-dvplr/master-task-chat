# UNIQUENESS: hangar-check-replan

The tie rule (planning_policy.md:36-38) orders every candidate plan by a total order on
(first, second, third, start list, finish list). Two different plans have different start or
finish lists, so the winner is unique. check_exact.py searches every legal start day at every
compression (no dominance) on the shipped data and finds the same unique plan as solve.py; the
judge probe P7 counts legal plans on a two-request input and shows exactly one fits the order.
The settlement order key (class rank, due_date, request_id) is total because request_id is unique
among open requests, so allowance_shifts per check is unique.
