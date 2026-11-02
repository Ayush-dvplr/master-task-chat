# Licence policy

Every licence identifier belongs to exactly one family.

Permissive: MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, Zlib, Unlicense.

Copyleft: GPL-2.0, GPL-3.0, LGPL-2.1, LGPL-3.0, AGPL-3.0, MPL-2.0, EPL-2.0.

A licence expression is one identifier, or identifiers joined by OR, or identifiers joined by AND,
never a mix of the two. An OR expression is permissive when at least one of its identifiers is
permissive. An AND expression is copyleft when at least one of its identifiers is copyleft.

The licence that governs a package is the one recorded against the earliest name of its rename
chain, the name whose row gives no renamed_from value. A licence recorded against any later name of
the chain is kept for history and governs nothing, because a rename never relicenses the versions a
package has already published.

A workspace whose copyleft setting reads forbidden may lock no package whose governing licence is
copyleft. A workspace whose setting reads allowed may lock packages of either family.
