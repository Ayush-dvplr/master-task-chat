# T10 the free ensemble scale

## Input

The deviation series of T06, the predictions of T07 and the final weights of
T09.

## The residual of an oscillator in this interval

At grid epoch k, for an oscillator that carries a deviation at k and holds a
final weight,

    residual(k) = deviation(k) - prediction(k)

with the prediction taken from T07 at the exact frequency. The residual is an
exact rational and is not rounded here.

## The free scale

    free scale(k) = sum over contributing oscillators of weight * residual(k)
                    divided by
                    sum over contributing oscillators of weight

An oscillator contributes at epoch k only when it carries a deviation at k.
The denominator is the sum of the weights of the oscillators that contribute
at that epoch. It is not the total weight of the ensemble, and it is
recomputed at every epoch.

The whole quotient is formed first and rounded once when it is written.
Rounding each term of the numerator to a picosecond before summing gives a
number that is right at every term and wrong in the total, and it is not what
this stage computes.

## The void epoch

An epoch at which no oscillator contributes has no free scale. Its state is
EP_ENSEMBLE_VOID, its free scale is written as an empty field and its
denominator is zero. Every other epoch has state EP_POPULATED.

## Output

For every epoch: its state, the number of contributing oscillators, the
denominator weight and the free scale.
