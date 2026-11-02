# known traps and footguns

Each entry names a reading that looks right, the reading that binds, and
the stage that owns it. Nothing here is new law; every entry restates a
rule from a stage document.

1. S01. Taking the last mission_register.csv row for a mission rather
   than the row whose register_state is current. The file is a history
   and its last row is not its binding row.

2. S01. Resolving a presentation identifier against the settlement
   period rather than against the scheduled start of the pass. The
   crosswalk changes mid campaign and the same identifier reappears in a
   later window.

3. S01. Reading tz_offset_min from any facility element row. Only the
   accounting_site row carries it; the others carry zero.

4. S01. Taking the last contract amendment by file order. The settled
   row is the highest revision_seq whose amendment_status is executed,
   and a superseded revision in this corpus may carry a larger or a
   smaller obligation than the executed one, so the direction of the
   disagreement is no guide to which row binds.

5. S02. Subtracting maintenance as a closed interval, so a docket that
   begins exactly when availability ends removes a second that was never
   there.

6. S02. Forgetting that a blackout advisory is a station fact and
   applies to every aperture at that station.

7. S03. Evaluating the admission predicates in a different order, so a
   pass that fails two of them is recorded under the wrong code.

8. S03. Treating a cancellation on the commit boundary as a rejection.
   It is a late cancellation and the pass stays admitted.

9. S03. Letting an operational event override a cancellation. It does
   not.

10. S03. Taking the last cancellation notice by issued_seq without
    checking notice_state. The binding notice is the last effective one.

11. S04. Using the journal times for a nominal event. Only a partial
    event narrows the interval.

12. S04. Settling a pass that straddles a station local period boundary
    in one period. It settles in both, as two canonical rows.

13. S05. Multiplying total eligible seconds by one blended rate. The
    floor belongs to each rate piece and the pieces are summed after.

14. S05. Applying the per contact cap to a mission or aperture total
    rather than to each canonical row before aggregation.

15. S05. Reading the cap or the budget from the superseded or the draft
    workbook sheet. Only the binding sheet counts.

16. S05. Using legacy_flat_rate_table.csv for capacity. It is retired
    and is read only for the discrepancy report.

17. S06. Treating protection as a tie break inside a priority class
    rather than as the first ordering key. An uncommitted emergency
    override pass loses to a committed ordinary pass.

18. S06. Accepting an event signed by an operator whose grade carries no
    commit evidence as proof of commitment.

19. S06. Letting an override lower a mission below its registered class.

20. S07. Displacing a pass partially. Displacement is whole.

21. S07. Running the greedy walk inside each connected component rather
    than once over the whole aperture period in the published order.

22. S07. Reducing the remaining obligation as passes settle. It is read
    once at the opening of the period.

23. S08. Counting closed opening buckets toward the carry source.

24. S08. Applying new entitlement before carry.

25. S08. Carrying forward for an expired contract instead of forfeiting.

26. S09. Using the running backlog rather than the opening backlog when
    computing demand for the ration.

27. S09. Running the ration to convergence rather than to the published
    pass budget.

28. S09. Applying the damping to the target rather than to the movement
    from the current value.

29. S09. Dropping the minimum movement of one unit, so every row stalls
    one unit short of its target, nothing is ever pinned and the share
    never rises.

30. S09. Treating the pass budget as a maximum and stopping at the
    first pass that moves nothing.

31. S10. Reducing the running backlog by the demand or the allocation
    rather than by the accepted volume.

32. S10. Treating downlink_reports.csv as an accepted volume.

33. S10. Charging a pass to both contracts of a mission that holds two.

34. S11. Computing the utilisation numerator from the pass plan or from
    the admitted rows rather than from the accepted rows.

35. S11. Reducing the utilisation denominator because a budget or an
    allowance ran out.

36. S11. Averaging aperture basis points to get a station figure rather
    than summing the numerators and denominators first.

37. S13. Reducing a shortfall by the exempt volume rather than waiving
    it entirely.

38. S13. Letting an outage exemption restore utilisation.

39. S13. Including a late cancelled pass in the exempt pool.

40. S13. Counting a rejected or withdrawn outage claim.

41. S14. Including stage_digest_manifest.json in its own digest.

42. Everywhere. Introducing floating point. Every quantity in this
    settlement is an integer and every division is a floor.
