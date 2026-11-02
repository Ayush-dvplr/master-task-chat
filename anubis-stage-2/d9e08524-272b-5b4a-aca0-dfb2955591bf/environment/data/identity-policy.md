# Identity policy

The package registry lists every registered name with its package key, written as eight lowercase
hexadecimal digits, and the licence expression recorded against that name. A name whose row gives a
renamed_from value continues the package of that earlier name, so the rows form rename chains, and
every name of one chain denotes one package.

The versions of a package are the version records of every field block whose package key belongs to
any name of its chain. A dependency entry or a workspace requirement that names any member of a chain
refers to the whole package. A package is reported under the name of its chain that no row renames
from.

A package key that no registry row carries is unregistered. A block with an unregistered key gives
its records to no package, and a dependency entry whose target key is unregistered refers to no
package.
