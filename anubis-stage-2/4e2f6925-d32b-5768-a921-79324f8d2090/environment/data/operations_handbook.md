# Operations handbook

## Why the tree matters

A link's reading is not the pure difference of two clocks. Each link carries a
bias its calibration report does not remove: the residual delay of the fibre or
the satellite path, the receiver electronics and the antenna cable. That bias
is why the graph does not close. Going from the hub to a node one way and back
another gives two different answers, and the closure of a cycle is the sum of
the biases around it.

The desk therefore fixes one tree and publishes along it. The tree is chosen by
published uncertainty because the least uncertain link is the one whose bias is
best characterised. What the desk minimises is the uncertainty a node ends up
carrying, which is the uncertainty of its whole path back to the root and not
of the last link on it, and it is the same figure the budget of stage T12
publishes for that node. A tree grown by the cheapest link in front of it can
hand a node a long cheap path that costs more than one short dear one. That
choice is a decision of the publication, not a property of the network, and it
is why the tree rule is stated exactly and why the links the tree leaves out
are published with their closures rather than quietly dropped.

## Why the caps exist

An ensemble dominated by one oscillator is not an ensemble. If the best clock
in the network holds a third of the weight then the scale is that clock, and
the scale inherits every one of its failures. The oscillator cap bounds any one
holder. The node cap bounds any one site, because oscillators at one site share
a room, a power feed and an environment, and their failures are not
independent.

The excess is redistributed rather than discarded because the weights are
relative. Discarding it would quietly reweight everything downstream by an
amount that depends on how many holders happened to be over the cap.

The sweep budget exists because the redistribution can push a holder over the
cap that was under it before, and the desk publishes a bounded computation
rather than an unbounded one. When the budget binds, the publication says so.

## Why the prediction is two points

The scale is a weighted mean of prediction residuals, and the prediction is a
model of where each oscillator was going. A least squares line through the
window is a better fit to the window and a worse predictor of the epoch after
it, because it is pulled by points a long way in the past. The endpoint slope
carries the recent behaviour of the oscillator and passes exactly through its
last measurement, which is where the interval starts.

## Why the dispersion is carried rounded

Every other rounding in the chain happens at write time. The dispersion does
not, because the desk publishes the dispersion table as whole picoseconds and a
reader has to be able to reproduce the weight from the number in front of them.
A weight formed from an unpublished exact value would not be reproducible from
the publication.
