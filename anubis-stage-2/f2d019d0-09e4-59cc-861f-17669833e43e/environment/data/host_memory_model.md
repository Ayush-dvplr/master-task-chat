# Host memory

```
entry_bytes, guard_bytes = row of memory_slot_table.csv whose static_dims equals
                           the number of dimensions named in mark_dynamic
guard_closures = over every cached entry, the count of key components that are
                 not `dyn`, summed
host_bytes = host_base_bytes
           + cached entries * entry_bytes
           + guard_closures * guard_bytes
           + running pool peak
host_headroom_bytes = host_ceiling_bytes - host_bytes
```

Headroom is signed. A run that exceeds the ceiling publishes a negative figure
and the steps where that happened. The figure is never clamped.
