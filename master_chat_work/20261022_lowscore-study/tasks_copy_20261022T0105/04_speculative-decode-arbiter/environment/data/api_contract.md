# SDA arbiter service contract

The corpus ships `arbiter_service.py`, a local service
that models the arbiter control plane. It is standard library only and it binds
the loopback address, so it reaches no external host and needs none.

The service holds control plane state only. It does not compute the replay and
it holds none of the figures the replay produces. It exists so the admission,
cancellation and lease decisions a replay reaches can be enacted against a
running service and read back from it.

## Starting it

Start the listener from the corpus directory.

    python3 arbiter_service.py serve --port 8713 --data <corpus directory>

The listener runs in the foreground. Start it in the background, or in a second
shell, and leave it running while the run proceeds.

## The two channels

The same in process state is reachable two ways, and both are real.

The command line channel runs a subcommand in a new process, which posts to the
running listener and prints the JSON response.

    python3 arbiter_service.py admit  --stream SDA-T07-0143
    python3 arbiter_service.py cancel --stream SDA-T07-0143
    python3 arbiter_service.py lease  --slot S04 --stream SDA-T07-0143
    python3 arbiter_service.py note   --text "any short free text"
    python3 arbiter_service.py state

The HTTP channel speaks to the same listener directly.

    GET  /v1/health
    GET  /v1/state
    POST /v1/admit    body {"stream": "<canonical stream identifier>"}
    POST /v1/cancel   body {"stream": "<canonical stream identifier>"}
    POST /v1/lease    body {"slot": "<slot>", "stream": "<canonical stream identifier>"}
    POST /v1/note     body {"text": "<free text>"}

Every POST carries a JSON body and the header `Content-Type: application/json`.
Every response is a JSON object. A successful operation answers with `ok` set
to true. An unknown route answers 404 and a malformed body answers 400, both
with `ok` set to false and an `error` string.

The routes are also served without the `/v1` prefix for `state` and `health`.

## State shape

`GET /v1/state` answers with an object carrying four keys.

    admitted    the canonical stream identifiers admitted, ascending
    cancelled   the canonical stream identifiers cancelled, ascending
    leases      an object mapping slot to the canonical stream holding it
    notes       the free text notes recorded, in the order they arrived

Repeating an `admit` or a `cancel` for a stream already in that list leaves the
list unchanged. A `lease` for a slot that already carries a holder replaces the
holder. Identifiers are stored exactly as they are sent, so send the canonical
form.

## What the service is for

The service is the control plane the run acts against. It computes nothing and
grades nothing, and reading its state tells you what you asked it to record
rather than whether the replay is right.
