# Rulebook: Identity

Filed under I. This rulebook consumes the token event register and every
admitted tap, and produces for each admitted tap a canonical identity, an
identity outcome, and the chain the resolution walked. It also produces the
home operator of every canonical identity, which the tariff rulebook needs
before it can price anything.

## I1. The event register

Each row of the token event register carries an `event_id`, an `effective_at`
instant, an `event_type`, a `subject_ref` and a `target_ref`. There are four
event types. Two of them redirect an identity:

- `rotate`: the subject is a card that was replaced. It redirects to its target.
- `merge`: the subject was folded into its target. It redirects to its target.

Two of them end an identity, and carry no target:

- `retire`: the subject was taken out of use in an orderly way.
- `revoke`: the subject was withdrawn against the holder's will.

## I2. Resolution is as at the tap instant

Identity is never resolved as of now. It is resolved **as at the instant of
the tap being priced**. An event with an `effective_at` later than the tap
contributes nothing to that tap, however many other taps it governs.

For a tap at instant `t` carrying `token_ref` `r`, the walk is:

1. Start the chain at `r`.
2. Collect every `rotate` or `merge` event whose `subject_ref` is the current
   identity and whose `effective_at` is at or before `t`. If there are none,
   the walk ends.
3. Of those, the one in force is the one with the latest `effective_at`.
   Where two share that instant, the one with the greater `event_id` is in
   force. Move to its `target_ref` and append it to the chain.
4. Repeat from step 2.

## I3. Chains that close on themselves

A register can contain a redirection that returns to an identity the walk has
already visited. That is a cycle, and it is not an error in the data: it is a
pair or a ring of cards that were merged into each other. When the walk
reaches an identity already in the chain, the walk stops and the canonical
identity is the **lexicographically smallest** identity in the cycle. The
outcome is `cycle_broken`.

## I4. Terminal events

Once the walk has ended, the chain is examined for terminal events. A
`retire` or `revoke` counts when its `subject_ref` is **any** member of the
chain and its `effective_at` is at or before `t`: an identity does not escape
its own retirement by rotating into a fresh card.

Where both kinds are present, `revoke` outranks `retire`. The outcome is:

- `revoked`, and the tap is withdrawn with the reason `identity_revoked`;
- or `retired`, and the tap is withdrawn with the reason `identity_retired`.

## I5. The four other outcomes

Where no terminal event applies, the outcome is `direct` when the chain has a
single member and `rotated` when it has more. Those taps carry on to pricing.
Together with `cycle_broken`, `retired` and `revoked` that is the whole
outcome vocabulary: `direct`, `rotated`, `cycle_broken`, `retired`, `revoked`.

## I6. The home operator

Every canonical identity has one home operator for the epoch. It is the
operator of the zone of the gate of the **earliest admitted tap in canonical
order whose canonical identity is that identity**.

Two things about this are worth stating plainly, because both are easy to get
wrong and both change the figures:

- The earliest admitted tap counts even when that tap is later withdrawn, for
  any reason at all. Home operator is a fact about the identity, not about
  the money.
- Home operator is resolved from canonical identities, not from raw
  `token_ref` values, so two cards that rotate into one identity share one
  home operator.

A tap is a **cross operator** tap when the operator of its own gate differs
from the home operator of its canonical identity. Cross operator taps are the
ones the interchange uplift applies to and the only ones that raise an
obligation in the netting layer.
