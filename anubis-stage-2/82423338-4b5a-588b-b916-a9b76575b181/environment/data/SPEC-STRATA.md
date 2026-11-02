# SPEC-STRATA: the relocation plan contract

STRATA relocates a filesystem tree from a source estate onto a tier of target
devices. A previous relocation run stopped part way through. This document is
the complete contract for the planner that decides what is still to be done. It
states every definition, every constant, every boundary, every encoding and the
exact shape of every artifact. Where this document and an instinct about
filesystems disagree, this document wins.

Version 4. Applies to the corpus this file ships beside.

## 1. Vocabulary

An **object** is one source inode. A **path record** binds one path string to
one inode; an inode with several path records is hard linked. An **extent** is
one logical range of one object mapped onto one physical range. A **physical
identifier** names that physical range; two extents carrying one physical
identifier share storage. A **pool** is a source subvolume. A **device** is a
target volume. A **share domain** groups devices between which sharing survives.
A **window** is one slice of the relocation schedule on one device.

The **barrier** of a pool is the sequence number at which the interrupted run
stopped for that pool. Everything at or below the barrier is already reflected
in the inventory. Everything above it is activity the interrupted run never saw.

An object is **relocatable** when four conditions hold at once. Section 12
states them and the order in which they are tested.

## 2. Corpus encodings

The corpus is a flat directory. Records of one logical table are split across
several files, and different files carry different encodings. Neither a file's
basename nor its extension is binding: detect its encoding from its content, and
identify its logical table by its complete record schema, not by a filename or
an individual field. For keyed `ini` and `properties` records, match the remaining
fields to a schema and restore its first field from the section header or record
identifier before interpreting the complete record. Fourteen encodings appear,
and every one is parseable with the Python standard library.

`csv` is comma separated with one header line naming the fields in schema order.
A cell is enclosed in double quotes when it is empty or holds the delimiter or a
double quote, and a double quote inside a quoted cell is doubled.

`psv` is the same with a vertical bar delimiter. `ssv` is the same with a single
space delimiter.

`tsv` is tab separated with one header line and no quoting. A backslash, a tab
and a newline inside a value arrive as `\\`, `\t` and `\n` respectively.

`fixed` is fixed width. The header line names the fields; a field begins at the
column where its name begins and ends where the next field name begins. The last
field runs to the end of the line. Trailing spaces on a line are absent, so a
short line means the values it would have carried are empty. Values are padded
right with spaces and never contain a space.

`json` is one object holding the key `records`, whose value is the array of
records.

`jsonl` is one JSON object per line.

`toml` is a sequence of `[[record]]` tables, one per record, each line holding
`field = value`. A string value is quoted and carries backslash escapes; an
integer value is bare.

`ini` is a sequence of sections. The section header holds the value of the
record's first field, and each following `field = value` line holds one further
field. The name of the first field is the name the record schema gives it.

`properties` is a sequence of `identifier.field=value` lines. The identifier is
the value of the record's first field and it groups the lines of one record. A
backslash, a colon and an equals sign inside a value arrive escaped with a
backslash.

`rfc822` is a sequence of blocks separated by one blank line. Each line is
`Header-Name: value`, where the header name is the field name with underscores
replaced by hyphens and each part capitalised.

`logfmt` is one line per record holding `field=value` pairs separated by single
spaces. A value that is empty or holds a space or a double quote is enclosed in
double quotes with backslash escapes.

`sexp` is one line per record of the form
`(record (field "value") (field "value"))` with backslash escapes inside the
quoted values.

`rfc5424` is one syslog line per record. The record is the structured data
element introduced by `[strata@41762 ` and closed by the last `]` on the line,
holding `field="value"` pairs with backslash escapes, and a `]` inside a value
arrives as `\]`.

The token `NIL` in any encoding is the only absence token. A numeric zero is
the number zero, never absence. A dash (`-`) and an empty string are invalid
alternates for an absent value.

## 3. Record schemas

Every schema below lists its fields in the order every encoding writes them, so
the first field named is the field an `ini` section header or a `properties`
identifier carries.

Pool: `pool_id`, `alloc_unit`, `root_depth_cap`, `region`.

Barrier revision: `pool_id`, `rev`, `barrier_seq`, `effective_seq`.

Device capacity revision: `device_id`, `rev`, `capacity_raw`, `capacity_unit`,
`existing_used_raw`, `existing_used_unit`, `reserve_ppm`, `effective_seq`.

Device geometry revision: `slot_id`, `device_id`, `rev`, `share_domain`,
`spill_device`, `online`, `alloc_unit`, `effective_seq`.

Window: `device_id`, `window_index`, `io_budget_raw`, `io_budget_unit`,
`descriptor_budget`.

Route: `route_id`, `class`, `pool_id`, `device_id`.

Object: `ino`, `kind`, `size_raw`, `size_unit`, `mode_raw`, `uid`, `gid`,
`mtime_ns`, `class_raw`, `pool_id`, `link_count`, `state`, `gen`.

Path record: `ino`, `path_raw`, `ordinal`, `form`.

Extent: `ino`, `ext_index`, `offset`, `length_raw`, `length_unit`,
`physical_id`, `flags`, `gen`.

Symlink: `ino`, `target_raw`, `form`.

Special node: `node_id`, `ino`, `node_kind`, `major`, `minor`.

Extended attribute: `xattr_id`, `ino`, `name`, `value_len`, `gen`.

Claim: `claim_id`, `ino`, `set_name`.

Deadline: `ino`, `deadline_window`, `class_override`.

Hold notice: `ino`, `reason`, `active`.

Checkpoint entry: `ino`, `ext_index`, `bytes_committed`, `seq`, `pool_id`.

Activity event: `seq`, `ordinal`, `kind`, `ino`, `path_a`, `path_b`, `arg_num`,
`arg_alt`.

## 4. Units

Every raw size arrives beside a unit. The factor is exactly:

```
B    1
KiB  1024
MiB  1048576
GiB  1073741824
kB   1000
MB   1000000
GB   1000000000
s    512
bl   4096
```

A size in bytes is the raw number multiplied by its factor. `kB`, `MB` and `GB`
are decimal and `KiB`, `MiB` and `GiB` are binary; they are different units and
the corpus uses both. `s` is a sector and `bl` is a block, and neither is the
allocation unit of anything.

## 5. Canonical forms

A **canonical path** is the NFC normalisation of the raw path with every run of
separators collapsed to one, every `.` segment removed, every `..` segment
resolved by removing the segment before it, a `..` at the root simply removed,
a leading separator added when the raw path has none, and no trailing separator.
The root is the single separator. The **depth** of a path is the number of
segments it holds, and the depth of the root is zero. Two path records that
normalise to one canonical path are one path.

For path records and symlinks, `form` declares the Unicode normalisation form
of the final raw arrival string (`path_raw` or `target_raw`), not an intermediate
string before it was stored. `nfc` declares that the raw string is already NFC;
`nfd` declares that it is already NFD. A string, including an ASCII-only string,
may satisfy both forms; its declaration still determines its arrival form. Keep
that declaration unchanged through canonicalisation and NFC output conversion,
rather than inferring it from the converted string. Outputs reporting arrival
form copy the declaration, and arrival-form counts use that declaration.

A **canonical mode** is four octal digits with leading zeros. A raw mode arrives
as octal digits with or without a leading zero, as octal digits prefixed `0o`,
or as a decimal number prefixed `d`. Only the low twelve bits are kept.

A **canonical class** is the lowercase form of the raw class. The four classes
are `gold`, `silver`, `bronze` and `tin`, and they rank in that order with
`gold` strongest.

Every artifact is UTF-8 without a byte order mark, uses LF line endings, and
ends with exactly one newline. Text fields are emitted in NFC.

## 6. Authoritative records

Several tables carry more than one row for one key. The authoritative row is
settled as follows, and never by the order rows happen to appear in a file.

For a pool barrier, a device capacity revision and a device geometry revision,
the authoritative row is the one whose `effective_seq` is largest, and where two
share that number the one whose `rev` is larger.

For an object, the authoritative row is the one whose `gen` is largest, and
where two share a generation the one whose `mtime_ns` is larger. The number of
further rows the corpus carries for that inode is reported as
`superseded_rows`.

For an extent, the authoritative row for one pair of inode and extent index is
the one whose `gen` is largest.

For an extended attribute, the authoritative row for one pair of inode and name
is the one whose `gen` is largest, and where two share a generation the one
whose `xattr_id` is larger.

For a special node record, the authoritative row for one inode is the one whose
`node_id` is smallest.

For a route, the authoritative row for one pair of class and pool is the one
whose `route_id` is smallest.

Some fields are advisory. They are recorded in the plan and they decide nothing.
The declared `link_count` on an object is advisory and the number of live path
records is the real one. The `class_override` on a deadline is advisory. The
`node_kind` on a special node record is advisory and the inventory kind decides.
The `pool_id` on a checkpoint entry is advisory and the barrier that applies is
the barrier of the pool the inventory gives the inode. A hold notice is advisory
in full: it is counted and its reasons are recorded, and it never removes an
object from the plan. The `sealed` extent flag is advisory. The `region` and
`size_unit` values are recorded and act on nothing.

## 7. The inventory

`object_inventory.jsonl` carries one JSON object per authoritative object,
ordered by ascending inode, with keys in this order:

```
ino kind size_bytes mode uid gid mtime_ns class pool_id
declared_link_count state superseded_rows size_unit
```

`size_bytes` is the raw size converted by section 4. `mode` is the canonical
mode. `class` is the canonical class. `state` is the state on the authoritative
row before any activity is replayed.

## 8. The target tier

The allocation unit of a **pool** rounds extents. The allocation unit of a
**device** chunks a split copy. They are different numbers and neither
substitutes for the other. An object whose pool is not in the pool catalogue
uses the default pool allocation unit of 4096 bytes.

For a device, `reserve_bytes` is the capacity multiplied by `reserve_ppm`
divided by one million, rounded down. `usable_bytes` is the capacity minus the
reserve. `io_budget_bytes` is the sum of the budgets of the device's windows and
`descriptor_peak` is the largest descriptor budget among them. `windows` is the
number of windows the device has, written as an integer.

`device_topology.json` is one JSON object with keys `devices`, `device_count`
and `domain_count` in that order. `devices` is the array of device records
ordered by ascending device identifier, each with keys in this order:

```
device_id capacity_bytes existing_used_bytes reserve_ppm reserve_bytes
usable_bytes alloc_unit share_domain spill_device online windows
io_budget_bytes descriptor_peak
```

`online` is 1 when the authoritative geometry revision says the device is
online and 0 otherwise. `device_count` is the number of devices and
`domain_count` the number of distinct share domains among them.

## 9. Extents

An extent's flags arrive comma separated, and the recognised words are `hole`,
`unwritten`, `inline`, `shared` and `sealed`. The word `none` means no flag.

Extents of one inode are considered in ascending extent index. Two repairs
apply, in this order. First, an extent whose offset falls before the end of the
last preceding extent that survived with a positive length has its offset moved
forward to that end and its length reduced by the same amount; that extent is
`truncated`. Second, an extent that reaches past the object's logical size has
its length reduced so that it ends exactly at the size; that extent is
`clipped`. An extent whose length is zero or less once both repairs have been
considered is `void`, and that includes an extent that arrives with a length of
zero and so needs neither repair. A void extent reports a length of zero,
carries the repair value `void` alone and does not move the end that the next
extent is measured against. An extent that needed both repairs carries
`truncated+clipped`. An extent that needed neither and keeps a positive length
carries `none`. The logical size used here is the size in the inventory, before
any activity is replayed.

The physical class of an extent is `hole` when it carries the hole flag,
`inline` when it carries the inline flag, `reserved` when it carries the
unwritten flag, and `data` otherwise; and it is `void` when the extent is void,
whatever its flags say. A hole holds no data and is never copied. An
inline extent lives in the inode and is never copied. A reserved extent occupies
space on the target and is never copied.

`raw_physical_bytes` is zero for a hole, an inline extent and a void extent. For
a data extent and for a reserved extent it is the length rounded up to a whole
number of the pool's allocation units.

`extent_map.tsv` is tab separated with a header line, ordered by ascending inode
and then ascending extent index, holding every extent of every object of kind
`regular` in the inventory whatever its relocatable verdict, with columns:

```
ino ext_index offset length_bytes end_offset physical_id physical_class
raw_physical_bytes flags repair
```

`offset` and `length_bytes` are the repaired values and `end_offset` is their
sum. `flags` lists the flags the extent carries in the order `hole`,
`unwritten`, `inline`, `shared`, `sealed`, joined with `+`, or the word `none`.

## 10. Symlinks and their resolution

A symlink is never dereferenced for its payload. Its `target` is the NFC form of
the stored target string, unchanged in every other way, and `target_bytes` is
the length of that string in UTF-8 bytes. Its `kind` is `absolute` when the
target begins with a separator and `relative` otherwise. A symlink whose target
is at most 59 bytes is fast and occupies no space; one longer than that occupies
exactly one allocation unit of its pool.

Resolution runs against the path index built from the path records before any
activity is replayed, where a canonical path held by more than one inode belongs
to the lowest of them. A relative target is joined to the parent directory of
the path record of the symlink that carries the lowest ordinal, and the result
is canonicalised. Start each resolution with zero hops and an empty set of
reached canonical target paths; do not preseed it with the starting symlink's
path. For each canonical target, first test membership in that set. A repeated
target makes the outcome `cyclic` immediately, without another hop. Otherwise
add the target to the set. It is `inside` when the resolved path is in the index
and the inode it names is not itself a symlink. It is `dangling` when the
resolved path is not in the index and its first segment is the first segment of
some path in the index. It is `outside` when the resolved path is not in the
index and its first segment is the first segment of no path in the index. When
the resolved path names another symlink, follow that symlink from the parent of
its own lowest ordinal path record and increment the hop count by one. On
reaching hop eight, stop with `capped` before resolving or testing the next
target, even if that next target would repeat or terminate the chain.

`symlink_topology.jsonl` carries one JSON object per symlink object in the
inventory, ordered by ascending inode, with keys in this order:

```
ino arrival_form target target_bytes kind resolution hops fast physical_bytes
```

`fast` is 1 or 0 and `hops` is the number of hops followed, which is zero when
the target does not name another symlink.
`arrival_form` copies the symlink record's declared `form`, not a form inferred
from its NFC `target`.

## 11. Replaying the activity

Events are replayed in ascending `seq`, then ascending `ordinal`, then by kind
in code point order, then by ascending inode.

An event naming an inode the inventory does not hold is `ignored` for the reason
`unknown_inode`. An event on an inode whose pool is not in the pool catalogue is
`ignored` for the reason `unknown_pool`. An event whose sequence is at or below
the barrier of that inode's pool is `absorbed` for the reason
`at_or_before_barrier`; the barrier itself is absorbed and the sequence one past
it is not. An `unlink` or a `rename` whose canonical `path_a` is not one of the
paths the inode currently holds is `ignored` for the reason `unknown_path`.
Every other event is `applied` and its reason is the empty string. The tests
above are made in the order they are written here and an event carries exactly
one outcome.

An applied event has these effects. An `unlink` removes that canonical path from
the inode, and an inode left with no path becomes pruned. A `rename` replaces
that canonical path with the canonical form of `path_b` on every path record
holding it. A `link` adds the canonical `path_a` as a further path record whose
ordinal is one past the largest the inode holds and whose arrival form is `nfc`.
A `hold` makes the inode held and a `release` makes it live. A `setxattr` sets
the attribute named by `path_a` to the value length in `arg_num`, adding it when
the inode does not carry it. A `write` covers the half open byte range that
starts at `arg_num` and runs for `arg_alt` bytes. A `truncate` sets the size in
`arg_num`. A `chmod`, a `chown` and a `write` change nothing else the plan
records.

`mutation_replay.jsonl` carries one JSON object per event in replay order with
keys in this order:

```
seq ordinal kind ino target effect reason
```

`target` is the canonical `path_a` for `unlink`, `rename` and `link`; the
attribute name for `setxattr`; `arg_num` and `arg_alt` joined by a colon for
`write`; `arg_num` for `truncate`, `chmod` and `chown`; and the empty string for
`hold` and `release`.

## 12. Which objects are relocatable

An object is relocatable when all four hold. Its pool is in the pool catalogue.
Its state after the replay is live and it holds at least one path. Exactly one
claim names it. The depth of its primary path is at most the `root_depth_cap` of
its pool, where a depth equal to the cap is inside and one more is outside.

An object that fails carries exactly one reason, the first that fails in the
order just given: `unknown_pool`, `not_live`, then `unclaimed` when no claim
names it or `contested` when more than one does, then `depth_exceeded`. A
relocatable object carries the empty string.

`scope_resolution.csv` carries one row per object in the inventory, ordered by
ascending inode, with columns:

```
ino class pool_id pool_region relocatable reason paths_after_replay
hold_notices hold_reasons claims claim_sets depth
```

`relocatable` is 1 or 0. `paths_after_replay` is the number of distinct
canonical paths the inode holds after the replay. `hold_notices` is the number
of hold notices for that inode whose `active` value is `true` and
`hold_reasons` is their distinct reasons in code point order joined with `+`.
`claims` is the number of claims naming the inode and `claim_sets` is their
distinct set names in code point order joined with `+`. `depth` is the depth of
the primary path, and zero when the inode holds none. Every object produces a
row, including the objects that take no further part in the plan.

## 13. Hard link clusters

The primary path of an inode is chosen from the paths it holds after the replay
by four keys applied in order: the smallest depth, then the smallest length in
UTF-8 bytes, then the code point order of the path, then the smallest ordinal of
the path record. The `tiebreak_level` is the number of the key that first left
the winner alone against the paths still in contention, and it is zero when the
inode holds one path record.

`link_clusters.jsonl` carries one JSON object per relocatable object, ordered by
ascending inode, with keys in this order:

```
ino primary_path tiebreak_level member_paths link_ops arrival_forms
```

`member_paths` is the array of the inode's distinct canonical paths other than
the primary, in code point order. `link_ops` is its length. `arrival_forms` is
the number of the inode's live path records whose arrival form is `nfd`.

## 14. What the interrupted run left behind

A checkpoint entry belongs to a pair of inode and extent index. Entries are
grouped by that pair. No group means no checkpoint entry exists for that pair;
it produces no resume-state row and gives a copy item the origin `fresh`. A
group containing a `bytes_committed` value of `NIL` does exist and is not a
missing group. Within a group, the entry that decides the outcome is the
one with the largest sequence at or below the barrier of the pool the inventory
gives that inode, and where two share a sequence the one whose committed size is
larger, an absent committed size counting as less than any number. When no entry
in the group is at or below the barrier the group is `after_barrier`, its
reported sequence is the smallest sequence in the group and its committed size
is reported as -1.

Otherwise the outcome follows from the committed size against the expected size,
where the expected size is the `raw_physical_bytes` of the repaired extent. An
absent committed size (`NIL`) is `never_started` and is reported as -1,
unless the group was already classified `after_barrier` above. Numeric zero
remains zero in the reported committed size. A committed size
equal to the expected size is `durable`. A committed size larger than expected
is `overrun`. A committed size of zero where more was expected is `zeroed`. Any
other committed size below expected is `partial`. Only a `durable` entry
survives; every other outcome means the extent is copied again from the start.

A durable entry is undone by activity above the barrier. An applied `write`
whose half open byte range meets the extent's half open repaired range undoes
it; ranges that only touch at an endpoint do not meet. The repaired range of a
void extent is empty and sits at its repaired offset, and a write meets it when
the write starts before that offset and ends after it. An applied `truncate`
whose new size is strictly below the end of the extent undoes it; a truncation
to exactly the end of the extent does not. An undone entry becomes `redirty` and
reports the sequence of the earliest event that undid it as `invalidated_by`;
every other entry reports zero there.

`resume_state.jsonl` carries one JSON object per group whose inode is
relocatable and whose extent index survives in the extent map, ordered by
ascending inode and then ascending extent index, with keys in this order:

```
ino ext_index seq committed expected status invalidated_by
```

## 15. Extended attributes

An attribute in the `user` namespace and one in the `trusted` namespace are
always migrated. An attribute in the `security` namespace is migrated only when
the object's class is `gold` or `silver`. An attribute in the `system` namespace
is dropped, except `system.posix_acl_access` and `system.posix_acl_default`,
which are migrated. The namespace of an attribute is the part of its name before
the first full stop. The size of an attribute is the length of its name in UTF-8
bytes, plus one, plus its value length.

`xattr_ledger.csv` carries one row per relocatable object, ordered by ascending
inode, with columns:

```
ino migrated_count dropped_count migrated_bytes dropped_bytes
first_migrated_name namespaces
```

`first_migrated_name` is the migrated name that comes first in code point order,
or the empty string when nothing is migrated. `namespaces` is the distinct
namespaces of the migrated attributes in code point order joined with `+`, or
the empty string. An object with no attributes at all still produces its row.

## 16. Special nodes

A device number is `major` multiplied by 256 plus `minor`. A minor above 255 is
a documented overflow: the minor used is the raw minor modulo 256 and the
overflow is reported. The recreation verb follows the inventory kind: `mkfifo`
for a fifo, `bind` for a socket and `mknod` for a character or block device. An
inode of one of those kinds that carries no special node record at all is
recorded with a major, a minor and a device number of zero, and the verb `skip`
when its kind is a character or block device.

`special_nodes.tsv` is tab separated with a header line, holding one row per
relocatable object whose inventory kind is `fifo`, `socket`, `chardev` or
`blockdev`, ordered by ascending inode, with columns:

```
ino node_kind major minor rdev overflow recreate
```

`node_kind` is the inventory kind.

## 17. Placement, sharing and the eviction fixed point

The device an object starts on is the device its authoritative route names for
its class and its pool. A route naming a device the catalogue does not hold
places the object instead on the lowest numbered online device, with the reason
`unrouted`. A device that is offline hands the object to its spill device, and
that repeats while the device reached is offline, up to four hops, with the
reason `offline_spill`; when the device reached after four hops is still offline
the reason is `offline_chain` and the object stays there.

Sharing survives only inside one share domain. For every physical identifier,
the relocatable objects whose surviving data or reserved extents carry it are
grouped by the share domain of the device they are placed on. Each distinct
domain materialises one copy. Inside a domain the copy is attributed to the
holder whose primary path comes first in code point order, and where two holders
share a primary path to the lower inode of them; where that holder carries the
identifier on more than one extent the copy is attributed to its lowest extent
index; every other extent carrying that identifier in that domain is a reflink
and is attributed nothing. The size of one copy is the largest `raw_physical_bytes` among the
extents carrying the identifier.

The **attributed bytes** of an object is the sum of `raw_physical_bytes` over
the surviving data and reserved extents whose copy it owns.

The **claim** of a device is the sum of the attributed bytes of the objects
placed on it. Its **projection** is its existing used bytes plus its claim, and
its **headroom** is its usable bytes minus its projection. A device whose
headroom is below zero is overcommitted.

Overcommitment is resolved by rounds, at most eight of them. In one round the
attribution above is recomputed from the current placement, and then every
device is taken in ascending device identifier and sheds exactly one object to
its spill device if it is overcommitted at the moment the walk reaches it. The
object it sheds is the first by weakest class,
then by largest attributed bytes, then by its primary path in code point order,
then by smallest inode, among the objects on it that have never been shed
before. A device with no such object sheds nothing,
and so does a device whose spill device is itself or is not in the catalogue.
The rounds stop when a round sheds nothing or when the eighth round completes,
and a device still overcommitted then stays overcommitted.

Shedding changes which domains hold a shared identifier, so the attribution is
recomputed from scratch at the start of every round rather than carried over
from the round before. Within a round the claims move as the walk proceeds: the
moment a device sheds, the attributed bytes of the object it shed leave its own
claim and arrive in the claim of the spill device. A device is therefore judged
against the claim it holds when the walk reaches it, which includes anything a
lower numbered device has just handed it, and a device that goes over only
because of what it received this round sheds in this round rather than the
next. The order the devices are walked in is part of the rule.

`placement.csv` carries one row per relocatable object, ordered by ascending
inode, with columns:

```
ino class initial_device device share_domain moved round reason
attributed_bytes deadline_window class_override
```

`initial_device` is the device before any shedding and `device` the device
after. `moved` is 1 when they differ. `round` is the round in which the object
was shed, and zero when it never was. `reason` is `evicted` for a shed object,
otherwise the reason the initial placement carried, otherwise the empty string.
`deadline_window` and `class_override` are copied from the object's deadline
row, and they are zero and the empty string when the object has no deadline row.

`sharing_expansion.jsonl` carries one JSON object per physical identifier held
by two or more relocatable objects, ordered by the identifier in code point
order, with keys in this order:

```
physical_id referencing_inodes domains copies owners unit_bytes expanded_bytes
```

`referencing_inodes` is the ascending array of those inodes, `domains` the
distinct destination domains in code point order, `copies` the number of them,
`owners` the owning inode of each domain in the same order as `domains`,
`unit_bytes` the size of one copy and `expanded_bytes` the size of one copy
multiplied by one less than the number of copies.

`allocation_projection.csv` carries one row per device, ordered by ascending
device identifier, with columns:

```
device_id capacity_bytes reserve_bytes usable_bytes existing_used_bytes
claim_bytes projected_bytes headroom_bytes over_committed placed_objects
evicted_out received_in
```

`over_committed` is 1 when the headroom is below zero. `placed_objects` is the
number of objects the device ends with. `evicted_out` is the number of objects
that were shed from it and `received_in` the number it received. A device that
holds nothing still produces its row.

## 18. The delta work set

A copy item exists for every surviving extent that is data, whose object is
relocatable and owns the copy of that extent in its domain, and whose checkpoint
outcome is not durable. Its size is the extent's `raw_physical_bytes`.

Its origin is `fresh` when the checkpoint holds no group for it, `redirty` when
the group is redirty, and `restart` for every other outcome.

Its effective class is the strongest class among the relocatable objects whose
surviving data or reserved extents carry the same physical identifier and which
are placed in the same share domain. An object of a weaker class carrying an
identifier a stronger one also carries is raised to the stronger class.

Its deadline window is the `deadline_window` on its object's deadline row, and
zero when the object has no deadline row.

`delta_workset.tsv` is tab separated with a header line, ordered by strongest
effective class, then ascending deadline window, then the primary path of the
object in code point order, then ascending inode, then ascending extent index,
with columns:

```
ino ext_index device_id physical_id copy_bytes origin effective_class
deadline_window
```

## 19. Metadata operations

Metadata operations carry no copy bytes except where stated. For every
relocatable object the plan holds: `mkdir` when its kind is `dir`; the
recreation verb of section 16 when it has a special node row whose verb is not
`skip`, with detail the major and the minor joined by a colon; `symlink` when it
is a symlink, with detail its target; one `link` per member path of its cluster,
with detail that path; one `reflink` per surviving data extent whose copy it
does not own, with detail the physical identifier and bytes the extent's
`raw_physical_bytes`; one `fallocate` per surviving reserved extent, with detail
the extent index and bytes the extent's `raw_physical_bytes`; one `setxattr` per
migrated attribute, with detail its name; one `chown` with detail the uid and
the gid joined by a colon; one `chmod` with detail the canonical mode; and one
`utimes` with detail the modification time in nanoseconds.

`metadata_workset.jsonl` carries one JSON object per operation with keys in this
order:

```
op ino path detail bytes
```

`path` is the object's primary path. Operations are ordered by ascending inode,
then by operation rank, then by detail in code point order. The rank is 1 for
`mkdir`, 2 for `mknod`, `mkfifo` and `bind`, 3 for `symlink`, 4 for `link`, 5
for `reflink`, 6 for `fallocate`, 7 for `setxattr`, 8 for `chown`, 9 for `chmod`
and 10 for `utimes`.

## 20. The window schedule

Copy items are offered to the schedule in the order of the delta work set. Each
is placed on the windows of its own device.

An item no larger than the largest single window budget on that device is placed
whole into the lowest numbered window whose remaining budget is at least its
size and which can admit it under the descriptor rule. When no window can, the
item is deferred in full.

An item larger than the largest single window budget on that device is split. It
is offered to the windows in ascending order. First test admission: the window
must admit the inode under the descriptor rule and its remaining budget must be
at least one device allocation unit. Skip a window that fails either test.
For an admitted window, compare the whole residual item to the unrounded
remaining budget first. If it fits, take that residual unchanged, even when it
is not a multiple of the device allocation unit. Otherwise take the remaining
budget rounded down to a whole number of device allocation units. Do not round
the room before testing whether the whole residual fits. Whatever is left when
the windows run out is deferred.

The descriptor rule is that each window opens at most as many distinct inodes as
its descriptor budget allows. An item whose inode is already open in that window
needs no further descriptor.

`window_schedule.tsv` is tab separated with a header line, ordered by ascending
device identifier, then ascending window index, then ascending inode, then
ascending extent index, then ascending chunk index, with columns:

```
device_id window_index ino ext_index chunk_index bytes descriptor_opened
```

`chunk_index` counts from zero over the placements of one item, in the order
they were made. `descriptor_opened` is 1 when the placement opened the inode in
that window and 0 when the inode was already open there.

An item is `whole` when one placement took all of it and that placement went to
the lowest numbered window that still had any remaining budget when the item was
offered. It is `rolled` when one placement took all of it and went elsewhere. It
is `split` when more than one placement was made and nothing was left. It is
`deferred` when anything was left.

`split_ledger.jsonl` carries one JSON object per item whose outcome is not
`whole`, ordered by ascending inode and then ascending extent index, with keys
in this order:

```
ino ext_index device_id status chunks placed_bytes residual_bytes
first_window last_window
```

`chunks` is the number of placements made, `placed_bytes` their total and
`residual_bytes` what was left. `first_window` and `last_window` are the window
indexes of the first and last placement, and both are -1 when no placement was
made.

`descriptor_budget.csv` carries one row per window of every device, ordered by
ascending device identifier and then ascending window index, with columns:

```
device_id window_index descriptor_budget descriptors_used io_budget_bytes
bytes_used utilisation_ppm
```

`descriptors_used` is the number of placements in that window that opened an
inode. `utilisation_ppm` is the bytes used multiplied by one million divided by
the window budget, rounded down, and zero when the budget is zero. A window that
took nothing still produces its row.

## 21. Cutover and rollback

An object is ready for cutover when it is relocatable and no copy item of it
left anything deferred. `cutover_sequence.txt` holds the primary path of every
ready object on its own line, ordered by ascending depth, then by the path in
code point order, then by ascending inode. Ordering by depth is what puts a
directory before everything beneath it. A member path of a cluster gets no line
of its own.

`rollback_plan.jsonl` carries one JSON object per cutover line in that order,
followed by one for every relocatable object that has deferred bytes, ordered by
ascending inode. Keys in this order:

```
step ino path guard reverse barrier_seq
```

`step` counts the cutover lines from one, and is zero for an object with
deferred bytes. The guard is `digest_match` when any checkpoint group of the
object is redirty, otherwise `size_match` when the object has any copy item at
all, otherwise `xattr_count_match`. The reverse action is `abort_hold` for an
object with deferred bytes; otherwise it is `restore_link` when the object's
cluster has any member path, otherwise `rename_back` when an applied `rename`
named the object, otherwise `unlink_target`. `barrier_seq` is the barrier of the
object's pool.

## 22. Conservation

For every device the attributed bytes of the objects it holds is exactly the sum
of four quantities: the bytes the schedule placed on it, the bytes its objects
resume from durable checkpoint entries of extents of physical class `data`, the
bytes its objects reserve through extents of physical class `reserved` whatever
the checkpoint outcome of those extents, and the bytes its objects deferred. The
residual is the attributed total minus those four and it is zero for every
device.

`conservation.json` is one JSON object with keys `devices`, `balanced_devices`
and `unbalanced_devices` in that order. `devices` is the array of one record per
device, ordered by ascending device identifier, with keys in this order:

```
device_id attributed_bytes copied_bytes resumed_bytes reserved_bytes
deferred_bytes residual_bytes
```

`balanced_devices` is the number whose residual is zero and
`unbalanced_devices` the number whose residual is not.

## 23. The planner and its closure artifacts

The planner is a command taking the corpus directory as its first argument and
the output directory as its second. It exits 0 when it writes a plan, 2 when the
number of arguments is wrong, and 3 when the corpus path does not resolve to a
directory.

`cli_contract.json` is one JSON object with keys in this order:

```
tool usage exit_ok exit_usage exit_policy artifact_count
```

The values are `stratactl`, `stratactl.py CORPUS_DIR OUT_DIR`, the three exit
codes above, and the number of artifacts the planner writes beside itself, which
is 24.

`manifest.json` is one JSON object holding the key `artifacts`, whose value is
the array of one record per artifact, in the order the artifacts are listed in
section 24 up to and including `cli_contract.json`, with keys in this order:

```
name rows bytes digest
```

`rows` is the number of newline characters in the artifact, `bytes` its length
in UTF-8 bytes and `digest` the first sixteen hexadecimal characters of the
SHA-256 of those bytes.

`summary.json` is one JSON object with keys in this order:

```
relocatable_objects excluded_objects clusters copy_items metadata_ops
cutover_steps manifest_digest
```

The counts are the number of relocatable objects, the number of objects excluded
from relocation, the number of clusters, the number of copy items, the number of
metadata operations and the number of cutover lines. `manifest_digest` is the
first sixteen hexadecimal characters of the SHA-256 of the manifest digests
joined in manifest order by single newlines, with no trailing newline.

## 24. The artifacts, in order

```
object_inventory.jsonl
device_topology.json
extent_map.tsv
symlink_topology.jsonl
mutation_replay.jsonl
scope_resolution.csv
link_clusters.jsonl
resume_state.jsonl
xattr_ledger.csv
special_nodes.tsv
placement.csv
sharing_expansion.jsonl
allocation_projection.csv
delta_workset.tsv
metadata_workset.jsonl
window_schedule.tsv
split_ledger.jsonl
descriptor_budget.csv
cutover_sequence.txt
rollback_plan.jsonl
conservation.json
cli_contract.json
manifest.json
summary.json
```

A comma separated artifact quotes a cell only when it holds a comma or a double
quote, doubling an inner double quote. A tab separated artifact quotes nothing.
A JSON artifact is written with an indent of two spaces, its keys in the order
this document gives them and never sorted, and non-ASCII characters left as
themselves. A JSON lines artifact writes one compact object per line with no
spaces after the separators beyond the single space JSON puts after a colon and
a comma, its keys in the order this document gives them.
