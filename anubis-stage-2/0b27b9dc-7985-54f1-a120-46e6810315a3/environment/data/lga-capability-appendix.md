# LGA appendix: the capability regime

This appendix is part of the LGA contract and states the capability algebra in
full. `SPEC-LGA.md` section 6.3 gives the outline.

## The capability table

The bit index of a capability is its position in this list, counting from zero.
The index is what a corpus field holding a decimal number means, and it is the
sort key wherever a specification sentence says a capability set is sorted by
bit index.

```
 0 CAP_CHOWN                14 CAP_IPC_LOCK             28 CAP_LEASE
 1 CAP_DAC_OVERRIDE         15 CAP_IPC_OWNER            29 CAP_AUDIT_WRITE
 2 CAP_DAC_READ_SEARCH      16 CAP_SYS_MODULE           30 CAP_AUDIT_CONTROL
 3 CAP_FOWNER               17 CAP_SYS_RAWIO            31 CAP_SETFCAP
 4 CAP_FSETID               18 CAP_SYS_CHROOT           32 CAP_MAC_OVERRIDE
 5 CAP_KILL                 19 CAP_SYS_PTRACE           33 CAP_MAC_ADMIN
 6 CAP_SETGID               20 CAP_SYS_PACCT            34 CAP_SYSLOG
 7 CAP_SETUID               21 CAP_SYS_ADMIN            35 CAP_WAKE_ALARM
 8 CAP_SETPCAP              22 CAP_SYS_BOOT             36 CAP_BLOCK_SUSPEND
 9 CAP_LINUX_IMMUTABLE      23 CAP_SYS_NICE             37 CAP_AUDIT_READ
10 CAP_NET_BIND_SERVICE     24 CAP_SYS_RESOURCE         38 CAP_PERFMON
11 CAP_NET_BROADCAST        25 CAP_SYS_TIME             39 CAP_BPF
12 CAP_NET_ADMIN            26 CAP_SYS_TTY_CONFIG       40 CAP_CHECKPOINT_RESTORE
13 CAP_NET_RAW              27 CAP_MKNOD
```

## Reading a capability set

A capability set is written as a plus separated list. Its members may be
canonical names, lower case names, decimal bit indices, or a mixture of the
three inside one field. The word `none`, in any case, is the empty set. A
comma is accepted in place of a plus. An empty field is the empty set.

A set is written back out as a plus separated list of canonical names sorted by
bit index, or as the literal `NONE` when it is empty.

## The four inputs

The **unit** record supplies the bounding set, the ambient set and the
`no_new_privs` flag. The flag is true only when the field holds exactly `true`
in lower case.

The **binary** record supplies the file permitted set, the file inheritable set
and the effective bit. The effective bit is set only when the field holds
exactly `1`.

The **principal** record supplies the thread inheritable set and the thread
permitted set.

A run names one unit, one binary and one principal. A unit, a binary or a
principal that no run names still appears in the corpus and contributes to
nothing.

## The computation

With `B` the bounding set, `A` the ambient set, `Fp` and `Fi` the file
permitted and file inheritable sets, `Ti` and `Tp` the thread inheritable and
thread permitted sets:

```
from_file = Fp intersect B                      when no_new_privs is false
from_file = Fp intersect B intersect Tp         when no_new_privs is true
permitted = (Ti intersect Fi) union from_file union A
effective = permitted                           when the effective bit is set
effective = A                                   when the effective bit is clear
```

The ambient set is part of the permitted set whatever the other inputs hold, so
a capability in the ambient set is in the effective set under both settings of
the effective bit. A capability in the file permitted set reaches the effective
set only through the bounding set, and under `no_new_privs` only when the
principal's thread permitted set also carries it.

## Refusal

A `capuse` event names one capability. The event is refused when that
capability is outside the effective set. The reason is `cap_absent` and the
rule reported is the capability name.

The exception is an advisory capability. A capability is advisory when the
`cap-required` group carries at least one record naming it whose `advisory`
field is `yes`. An advisory capability outside the effective set never refuses
an event. It is still recorded as a capability gap, and it is what breaks audit
continuity.

## What the two capability atoms change

A `cap_bounding_add` atom names a `unit` and a `cap`. The capability joins that
unit's bounding set and nothing else. It therefore reaches the permitted set
only when the binary's file permitted set also carries it, and under
`no_new_privs` only when the principal's thread permitted set carries it too.
An atom of this kind that fails those conditions changes no decision, and is
still a legitimate member of the catalogue.

A `cap_ambient_add` atom names a `unit` and a `cap`. The capability joins that
unit's ambient set and its bounding set. It therefore always reaches the
permitted set, and reaches the effective set under both settings of the
effective bit.

Neither atom touches a binary record or a principal record.
