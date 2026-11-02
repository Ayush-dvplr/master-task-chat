# LGA appendix: type enforcement

This appendix is part of the LGA contract and states the SELinux type
enforcement algebra in full. `SPEC-LGA.md` section 6.2 gives the outline.

## Types and attributes

The `selinux-types` group declares every type. A type's `attributes` field is a
vertical bar separated list. A type whose attribute list contains `domain` is a
domain; every other type is a file type. The `is_domain` field repeats that
fact and never contradicts it.

Four attributes appear: `domain`, `file_type`, `privileged`, `auditable`, and
`base_type` is used for a type carrying none of the others. An attribute is
never also a type name, so a name is unambiguously one or the other.

## Allow records and attribute expansion

An allow record grants, for the pair of its `source` and its `target`, every
permission in its comma separated `perms` list in the class its `tclass` names.

A record whose `source` names an attribute grants for every type carrying that
attribute. A record whose `target` names an attribute grants against every type
carrying that attribute. A record naming an attribute on both sides grants for
every pair. Expansion is by name: a name that is not an attribute is taken as
the type of that name, even when no type of that name is declared.

The grant set is the union of every record's expansion. A permission is allowed
for a source, a target and a class when the triple with that permission is in
that union. Allow records never deny; there is no record that removes a
permission another record granted.

## Dontaudit records

The `selinux-dontaudit` group is advisory. A dontaudit record neither grants a
permission nor refuses an access. It records that the site has chosen to stop
logging a particular access. Nothing in the delivered artifacts depends on a
dontaudit record's effect on the decision, because it has none, and a reader
that treats a dontaudit record as a denial will refuse accesses the policy
permits.

## The transition triple

At the `exec` event the process is running in its source domain and is about to
execute a file carrying the executable type.

The transition records that apply are the `selinux-transition` records whose
`source` equals the source domain and whose `exec_type` equals the executable
type. They are ordered by `rank` ascending and then by `rule_id` ascending, and
the first is the chosen record. Rank decides, not the order the records appear
in the corpus, and not the shard a record happens to sit in.

When no record applies, no transition happens. The process keeps its source
domain, the event is not refused, the transition rule is reported as the
literal `NONE`, and the three flags are reported as `yes`.

When a record applies it names a landing domain. The transition happens only
when all three of these are allowed:

```
execute     the source domain, the executable type, class file, permission execute
entrypoint  the landing domain, the executable type, class file, permission entrypoint
transition  the source domain, the landing domain, class process, permission transition
```

When all three hold, the domain in force after the event is the landing domain.
When one or more is absent, the event is refused. The reason names the
alphabetically first of the absent three, so a run missing both `entrypoint`
and `transition` reports `te_missing_entrypoint`, and a run missing only
`transition` reports `te_missing_transition`. The rule reported is the chosen
transition record. The domain in force after a refused transition is the source
domain, and that is the domain the later events of that run are judged against.

## Access events

An `access` event names a class, a target type and one or more permissions. It
is allowed when every permission it names is allowed for the domain in force,
that target type and that class. Otherwise the event is refused and the reason
names the alphabetically first absent permission.

A `ptrace` access is an ordinary access: it names the class `process` and the
permission `ptrace`, and it is judged by the same rule as any other. No
permission has a special case.

The domain in force is the domain the `exec` event left the process in. Events
before the `exec` event are never `access` events.

## The audit event

The `audit` event of a run is judged for reporting only. Its permissions are
checked against the domain in force exactly as an access event's are, and the
result feeds audit continuity, but the event is never refused and never decides
a run.

## What a te_allow_add atom changes

A `te_allow_add` atom names a `source`, a `target`, a `class` and a `perm`. It
adds that one triple and permission to the grant set. When its `source` or its
`target` element names an attribute the addition expands over every type
carrying that attribute, exactly as a shipped record would. No atom in the
catalogue names an attribute on both sides at once.
