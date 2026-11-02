# T03 measurement sense

## Input

The corrected readings of T02 and link_register.csv.

## The rule

A link records its comparison in the sense its technique uses, and the two
senses are not interchangeable. link_technique_reference.txt gives the sense
of every technique. A reading on a link whose technique records
SENSE_A_MINUS_B already expresses the clock of node_a minus the clock of
node_b. A reading on a link whose technique records SENSE_B_MINUS_A expresses
the opposite and its sign is inverted to bring it to the A minus B convention.

    difference_ps = corrected_ps                    when SENSE_A_MINUS_B
    difference_ps = 0 - corrected_ps                when SENSE_B_MINUS_A

node_a and node_b are the columns of link_register.csv and are not reordered.

## Output

One signed difference per canonical reading, in the A minus B convention.
