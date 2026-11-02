# Resolution policy

The workspace manifest names every benchmark workspace with its snapshot day and its copyleft
setting. The requirements table lists what each workspace asks for directly: a package name, a
lowest version (inclusive), a version bound (exclusive) and a requested feature mask. Versions are
written major.minor.patch. A version lies inside a range when its version code is at least the
lowest version code and below the bound.

## Eligible versions

A version of a package is eligible for a workspace when it is not yanked, its publish day is on or
before the snapshot day of the workspace, and its publish day lies at least the quarantine days
before that snapshot day. A version published exactly the quarantine days before the snapshot day
is eligible. The quarantine days is one registry constant shared by every workspace. The deprecated
marker has no bearing on eligibility.

A version record is quarantined for a workspace when it belongs to a registered package, is not
yanked, is published on or before the snapshot day, and is published fewer than the quarantine days
before it.

## Valid lock plans

A lock plan for a workspace locks exactly one eligible version of each package in a set of packages.
A lock plan is valid when every one of these conditions holds together:

- every package the workspace requires is locked, at a version inside the requirement's range;
- every active dependency entry of every locked version names a registered target, that target is
  locked, and its locked version lies inside the entry's range;
- every locked package is required by the workspace or is the target of an active dependency entry
  of a locked version;
- the copyleft setting of the workspace holds for every locked package.

Whether a dependency entry is active is settled by the feature policy.
