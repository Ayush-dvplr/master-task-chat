# Service protocol

The settlement interface lives in /app/service. simulator.py serves the interface
and client.py speaks to it. Start the interface on the loopback address at port
8765 before any call. service_probe_log.log records the request and response
field names for every endpoint, and desk_transition_log.log records the call
order that earlier sessions followed.

| endpoint | verb | purpose |
| --- | --- | --- |
| /health | GET | readiness of the interface |
| /window | POST | declare the window bounds, cutoff, pool and mode |
| /register | POST | place a pledge on the docket |
| /transition | POST | move a pledge through its events |
| /grace | POST | record granted minutes for a pledge |
| /seal | POST | close the window and return the sealed state |
| /state | GET | the state the interface holds |
| /transcript | GET | every call in sequence |

The window declaration comes first. A registration before the declaration is
refused with the reason window_unset.

A registration carries the pledge identifier, the holder key, the class, the
governing due instant, the prerequisites that sit on the docket and the
prerequisites that sit outside the docket together with their effective instants.
A registration naming a docket prerequisite that the interface has not yet seen is
refused with the reason unknown_prereq, so registrations follow dependency order
and ties inside that order follow the canonical order. A registration whose due
instant falls outside the declared window is refused with the reason
out_of_window. A second registration of the same pledge is refused with the
reason duplicate_registration.

Every pledge is acknowledged before it receives a terminal event. The terminal
events are discharge, breach, waive, block, hold and lapse. A discharge carries
the effective instant of the pledge and its lateness minutes. A breach carries
lateness minutes alone and suits a pledge that reached the cutoff with no
effective instant. A discharge whose effective instant falls before the effective
instant of a prerequisite is refused with the reason effective_regression. A
discharge with zero lateness leaves the pledge cleared and a discharge with
lateness above zero leaves it breached.

A grace call carries the pledge identifier, the granted minutes and the lateness
minutes. A grace call for a pledge outside the breached state is refused with the
reason grace_ineligible_state. A grant beyond the submitted lateness is refused
with the reason grace_over_grant. A grant beyond the capacity left in the pool is
refused with the reason pool_exhausted. The desk addresses a grace call only for a
pledge receiving one minute or more.

The seal closes the window and returns the sealed state, including the settlement
fingerprint the interface computes. The desk confirms closure by issuing the seal
once more, which the interface refuses with the reason already_sealed.

Boundary notices are filed through /register with the boundary flag set to true.
The interface refuses each one with the reason out_of_window, and the refusal is
the record of the exclusion.

Once the seal is confirmed the desk stops the interface process, so nothing is
left listening after the window closes.

channel_policy.ini states which calls travel through client.py and which travel
through the interface directly. The transcript records the channel of every call.
