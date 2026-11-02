# Shared observation allocation

allocation_groups.csv contains board,component,group,atoms. Each board has one
or more components, with distinct group identifiers within a board. A component's
required atom set is the union of its groups' atoms cells. Repetition of an atom
in different groups' atoms cells has no multiplicity. Atom identifiers are local
to a component. A group row establishes required atoms; its atoms cell does not
describe that group's assigned observation.

allocation_candidates.csv contains board,component,group,candidate,atoms,value.
Candidate names are unique within a group. Exactly one candidate is chosen per
group. In each component, the chosen candidates' atom sets must be pairwise
disjoint and their union must equal the required atom set. A candidate containing
an atom outside that set is inadmissible. Components' atoms have separate scopes,
even if their spelling matches. A board's assignment consists of all of its
components' assignments. Zero assignments and multiple assignments are errors,
including different assignments that happen to have equal values.

allocation_requests.csv contains request,board,group,account,quantity. request is
an integer identifier. A request's credit is quantity times its chosen candidate's
value. Requests identify groups by board and group, rather than component.
An absent group is an error. Account text is case-sensitive. Emit request rows
in ascending integer request order. Zero and signed quantities retain their sign.
