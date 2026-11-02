# Recurrence primer

Three worked selections. The figures are invented and belong to no path in this
extract; they exist so the rules of stage 3 can be checked against arithmetic.

## A month period with two positive positions

Rule: `freq` month, `anchor` 2030-02-11, `byday` [2, 4], `bymonthday` empty,
`setpos` [1, 3], `horizon_periods` 2.

Period 0 is February 2030. The Tuesdays and Thursdays of that month are
2030-02-05, 2030-02-07, 2030-02-12, 2030-02-14, 2030-02-19, 2030-02-21,
2030-02-26 and 2030-02-28, so the candidate set has eight members. Position 1
selects 2030-02-05 and position 3 selects 2030-02-12.

Period 1 is March 2030. The candidate set is 2030-03-05, 2030-03-07,
2030-03-12, 2030-03-14, 2030-03-19, 2030-03-21, 2030-03-26 and 2030-03-28.
Position 1 selects 2030-03-05 and position 3 selects 2030-03-12.

The selection of the rule is 2030-02-05, 2030-02-12, 2030-03-05 and
2030-03-12. Note that position 3 is the third candidate of its own period, not
the third candidate of the expansion.

## An isoweek period with a negative position

Rule: `freq` isoweek, `anchor` 2030-02-13, `byday` [1, 3, 5], `bymonthday`
empty, `setpos` [-1], `horizon_periods` 3.

The anchor is a Wednesday, so period 0 starts on Monday 2030-02-11 and runs to
Sunday 2030-02-17. Its candidate set is 2030-02-11, 2030-02-13 and 2030-02-15,
a set of size three. Position -1 reads zero based index 3 plus -1, which is 2,
so it selects 2030-02-15. Position -3 would read index 0 and select
2030-02-11, and position -4 would read index -1, which is below zero, and
select nothing.

Periods 1 and 2 start on 2030-02-18 and 2030-02-25 and select 2030-02-22 and
2030-03-01 the same way.

## A month day rule in a short month

Rule: `freq` month, `anchor` 2030-01-09, `byday` empty, `bymonthday` [31],
`setpos` [1], `horizon_periods` 4.

Period 0 is January 2030 and its candidate set is 2030-01-31, so position 1
selects that date. Period 1 is February 2030, which has no 31st, so its
candidate set is empty and position 1 selects nothing. Period 2 is March 2030
and selects 2030-03-31. Period 3 is April 2030, which has no 31st, so it
selects nothing. The selection is 2030-01-31 and 2030-03-31, and February does
not fall back onto 2030-02-28.

## A fourweek period

Rule: `freq` fourweek, `anchor` 2030-02-04, `byday` [6], `bymonthday` empty,
`setpos` [2], `horizon_periods` 2.

Period 0 covers 2030-02-04 to 2030-03-03 and period 1 covers 2030-03-04 to
2030-03-31. The Saturdays of period 0 are 2030-02-09, 2030-02-16, 2030-02-23
and 2030-03-02, so position 2 selects 2030-02-16. The Saturdays of period 1 are
2030-03-09, 2030-03-16, 2030-03-23 and 2030-03-30, so position 2 selects
2030-03-16.
