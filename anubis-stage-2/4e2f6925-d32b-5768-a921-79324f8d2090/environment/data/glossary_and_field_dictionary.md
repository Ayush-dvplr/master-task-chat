# Glossary and field dictionary

**acq_time_s** absolute time of an acquisition attempt, in whole seconds.

**anchor** the last valid archived deviation of a history window, and the epoch
it was taken at. A prediction passes exactly through its anchor.

**archive epoch** an epoch of the previous interval, numbered 1 to 24.

**attribution window** the half open interval around a grid instant inside
which an acquisition row belongs to that epoch.

**cluster** the set of acquisition rows sharing one link and one grid epoch.

**component** a maximal set of nodes joined by usable links.

**dead time** an epoch at which a link, a node or an oscillator carries no
measurement.

**departure** the free scale at the decision epoch minus the primary
realisation there.

**dispersion** the mean absolute residual of an oscillator over its history
window, published as a whole picosecond.

**free scale** the weighted mean of the prediction residuals of the ensemble
at one epoch, before steering.

**grid epoch** an epoch of this interval, numbered 1 to 30.

**history window** the last history_window_epochs archived epochs.

**hub** the node the interval header names as the root of the anchored
component.

**link bias** the part of a link's reading that the calibration report does not
remove. It is why two spanning trees disagree and why the excluded links carry
non zero closures.

**loop closure** the disagreement between an excluded link's reading and the
difference the tree implies.

**mass preserving** a capping rule under which the sum of the weight vector is
unchanged by the pass, the placement residue included.

**node offset** a node's clock minus the clock of the root of its component.

**admission cost** the path cost of a candidate link's reached end plus its
own published uncertainty, which is the path cost its unreached end would take.
It is what stage T04 admits on.

**path cost** the sum of the published uncertainties of the tree edges between
the root of a component and one of its nodes. The root carries zero.

**placement residue** the amount by which placing a capping pass on the
published weight grid moves the total of the vector. Stage T09 hands the whole
of it to one holder, so a pass preserves the total exactly.

**published uncertainty** the uncertainty the register publishes for a link, in
picoseconds. It builds the admission cost that orders the spanning tree and it
is a term of the budget.

**raw weight** weight_scale divided by the published dispersion, or the class
ceiling weight when the published dispersion is zero.

**reference oscillator** the oscillator a node realises its clock with, at the
frozen register revision.

**residual** a measured deviation minus the deviation the prediction gives at
that epoch.

**sense** whether a technique records node_a minus node_b or the opposite.

**steered scale** the free scale plus the accumulated steering correction.

**sweep** one pass of the oscillator cap over the whole weight vector.

**usable link** a link both of whose nodes are registered and which does not
name the same node on both sides.
