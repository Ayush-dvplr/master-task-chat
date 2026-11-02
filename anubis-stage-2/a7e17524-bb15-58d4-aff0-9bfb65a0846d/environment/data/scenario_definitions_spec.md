# Scenario definitions

Each scenario re-adjudicates the same cycle with one change and reports only the
figures its artifact asks for. The seating the relay service holds is never
touched by a scenario, and no scenario changes which requests the horizon admits.

## alpha

The decision instant moves to the stamp given for `alpha` in
`scenario_overlays.json`. Every rule that reads the decision instant reads the new
one, which includes the governing record rule, the publication cut on a mirror
index, the embargo split, the cooldown, the freeze and hold windows and the waiver
expiry. The horizon does not move, so a request submitted after the alpha instant
is still adjudicated.

## beta

The decision instant is unchanged. `release_bulletins.json` is read as if it held
no bulletins and `delegation_grants.json` is read as if it held no grants.

## mode

The decision instant is unchanged. Two readings are compared. Under `delegated`
every rule is the baseline rule. Under `strict` a verdict of `indeterminate`
clears nothing in any channel, and every other rule is the baseline rule.

## Normative parameters

```
mode_names: strict,delegated
scenario_names: alpha,beta,mode
```
