# Boundary cases

| case | outcome |
|---|---|
| a pool of the pool table with no member after corrections | the pool is not settled and appears in no report |
| a pool with one member | its target is the pool total, which it already holds, so it settles in round zero |
| a pool whose members all have zero demand | every target equals the holding, so it settles in round zero |
| a pool whose pool total is zero | every target is zero, so it settles in round zero |
| a tenant row retired after corrections | the tenant is no member of any pool; its requests are orphans |
| a member with no counted request | its token units and demand are zero; it still takes part in settlement and receives a bill line |
| a request with zero tokens | it is counted, and adds zero units |
| a correction whose value equals the current value | it applies and changes nothing |
| a class in scope whose pools all have no member | the class has no pool and no bill line, and its scenario file still reports it in scope |
| the prior output lacks a member | the prior and delta fields of that row are empty |
| a key of a meter reading that reaches no member at the reading instant | it adds nothing to the reading |
| a pool whose members all have zero token units | it needs no units per RU and is left out of units_per_ru |
