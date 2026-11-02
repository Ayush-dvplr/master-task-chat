# Operator questions

**A cluster has two rows with attempt number 2 and both hold lock. Which one?**
The one whose acquisition time is closest to the epoch instant. If they are
equally close, the earlier one.

**A row sits exactly on the upper edge of a window.** It is outside that
window. The window is closed below and open above. It may fall inside no window
at all, and then it is set aside.

**The withdrawal journal names a session that was the only locked attempt of
its cluster.** The session goes, and then the cluster has no locked attempt, so
the rest of the cluster is set aside as well. Two rules, applied in the order
stage T01 gives.

**A link's reports all take effect after the interval closes.** Then no report
governs it. Its correction is zero and the selection records CAL_ABSENT.

**Two links join the same pair of nodes.** Both are usable. The tree admits one
of them by the rule and the other is an excluded link with published closures.

**A node has no usable link.** It is a component of one node, it is unanchored,
it is its own root, its offset is zero at every epoch and its dissemination is
withheld as unanchored.

**A node's only link carries no reading at any epoch.** Its offsets are absent
throughout, and its dissemination is withheld for want of data. It is not
unanchored: it sits in the anchored component.

**An oscillator has exactly the history minimum of valid epochs.** It is
included. The comparison is strict.

**An oscillator's residuals are all zero.** Its published dispersion is zero
and it takes the ceiling weight of its class from the workbook.

**Every weighted oscillator is above the oscillator cap.** There is nobody to
take the excess. The pass records SW_CAP_UNSATISFIABLE and changes nothing.

**No oscillator carries a deviation at an epoch.** That epoch is void. It has
no free scale and no steered scale, but it still carries its steering
correction.

**The decision epoch has no primary realisation.** There is no departure, the
step is zero and the outcome is ST_NO_REALISATION. The correction is zero at
every epoch.

**Does the published free scale plus the published correction give the
published steered scale?** Not in general. All three are rounded renderings of
exact values, and the steered scale is the rounding of the exact sum.
