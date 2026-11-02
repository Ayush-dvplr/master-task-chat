# Rulebook: partition

Filed under P in the platform reference set. The settled window is reported
partition by partition. This rulebook says which partitions are in scope. It
does not say how many there are, because that is a consequence of the
settlement rather than a fact about the platform.

## P1 Domains in scope

A domain is settled when it finishes the window with at least one curated
record. A domain that finishes with no curated record is not settled, whatever
the reason: it may be provisional, every one of its feeds may have been
designated or quarantined, its records may all have been withdrawn, or it may
simply have carried no traffic at all.

The settled window carries one domain report for each settled domain and none
for any other domain. The number of settled domains is not published anywhere.
It is not the number of domains in the domain register, it is not the number of
non provisional domains, and it is not the number of domains that carried
traffic.

## P2 Channels in scope

A channel is settled when at least one of its member domains is settled. The
settled window carries one channel report for each settled channel and none for
any other channel.

## P3 Membership is not scope

Every domain names the channel it belongs to, and that membership never changes
during a settlement. A channel report names its member domains, which is the
full membership from the domain register, and separately names the member
domains that were settled. Those two lists are not the same list and a channel
report that repeats one of them for the other is wrong.

The feed list of a domain report is likewise the full membership from the feed
register. Designation, suspension and quarantine do not remove a feed from the
domain it belongs to.

## P4 Naming

A partition report is named after the partition it reports on. The name is the
partition identifier written in lower case, with every run of characters that
are not lower case letters or digits replaced by a single underscore, prefixed
by the kind of partition and an underscore, and suffixed with the usual data
extension. A domain called `WEST-1` would therefore be reported in a file called
`domain_west_1.json` and a channel called `WEST-1` in a file called
`channel_west_1.json`.

## P5 What a partition report accounts for

A domain report accounts for the whole of its domain and not only the part that
survived: the records it curated, the records it dropped at the cap, the reasons
its withdrawn records were withdrawn under, the charge it settled, the payload
units it curated, the cap and floor it was working to, its feeds, its quarantined
feeds and the canonical producers of its curated records.

A channel report accounts for its channel: its slot ceiling, the reserve feeds it
designated, its member domains, its settled member domains, the charge each of
those settled domains contributed, and the totals the channel settled.
