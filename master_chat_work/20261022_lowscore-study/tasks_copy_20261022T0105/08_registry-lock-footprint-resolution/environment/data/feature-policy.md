# Feature policy

Every package version exposes eight feature bits, numbered 0 to 7. A dependency entry asks for
features of its target through its requested feature mask, and a workspace requirement asks for
features of its package in the same way.

A dependency entry of a locked version is active when its gate is 255, or when the feature bit its
gate names is enabled on the package that declares the entry. An inactive entry asks for nothing
and constrains nothing.

The enabled features of a lock plan give every locked package one mask. They form the smallest
assignment in which the mask of every locked package contains what the workspace asks of that
package directly and what every active entry of every locked version asks of it. Each set of
locked versions has exactly one such smallest assignment.

The settlement passes of a lock plan are counted this way. The state before the first pass gives
every locked package only what the workspace asks of it directly. A pass takes the state left by the
previous pass, collects the requests of every entry that is active in that state, and adds all of
them to that state at once. Passes continue until a pass adds nothing, and that last pass is
counted.
