# Arbiter Service Contract

The arbiter at `/app/service/arbiter.py` records slate outcomes. It holds no
legality policy. Where a reply from the arbiter disagrees with the slate
contract, the slate contract governs. `GET /advice` returns console
convenience numbers that the published corpus supersedes.

Start the service with the seed file it ships with:

```
python3 /app/service/arbiter.py --seed /app/data/registry_seed.json
```

It listens on `127.0.0.1` at port `8814` and serves until it is stopped. The
console at `/app/service/arbiterctl.py` reaches the same service.

## Configuration

`registry_seed.json` states the slate id, the page size, the number of non
empty pages after which an empty page is served, the number of requests by
which the listing lags writes, the format whose writes are deferred, the feed
of contested entries, the pre seeded entry ids and the state those entries
begin in. `service_token.json` states the token, the request budget, the
renewal path, the accepted scopes and the code returned once the budget is
spent. `channel_policy.ini` states the console only operations, the default
scope each channel applies when a write omits one, and the header names.

## Operations and states

The operations are `register`, `seat`, `amend`, `flag`, `bar`, `defer` and
`reinstate`. The states are `intake`, `seated`, `amended`, `flagged`, `barred`
and `deferred`.

```
intake    seat -> seated      amend -> amended   flag -> flagged
          bar  -> barred      defer -> deferred
seated    amend -> amended    flag  -> flagged   bar -> barred
          defer -> deferred
amended   flag -> flagged     bar   -> barred    defer -> deferred
flagged   amend -> amended    bar   -> barred    defer -> deferred
deferred  seat -> seated      amend -> amended   flag -> flagged
          bar  -> barred
barred    reinstate -> deferred
```

`register` creates an entry in the state named by the seed, leaves it in that
state, takes a journal sequence of its own and needs no prior read. A
`register` aimed at an entry that already exists is refused with
`state_conflict`. Any other operation that the table above does not list for
the current state is refused with
`state_conflict`, leaves the state untouched and counts in the refusal totals.
The refusal codes are `unknown_entry`, `state_conflict`, `channel_denied`,
`stale_etag`, `malformed` and `scope_invalid`.

## Reading

`GET /health` reports readiness and costs nothing against the budget.

`GET /state` returns the slate id, the journal sequence, the digest, every
entry with its state, scope, channel and last sequence, and the refusal
totals.

`GET /journal` returns the applied operations in sequence order, each with its
sequence, operation, entry, scope and channel.

`GET /entries` returns one page of entry ids. Pass `cursor` to fetch a later
page. A page carries `next_cursor` only when a further page exists. One empty
page is served after every run of non empty pages whose length is the number
in the seed, and an empty page carries a cursor like any other. The listing
reflects writes only after the number of requests the seed names as the
listing lag, while `GET /entry` reflects every applied write at once.

`GET /entry` takes `id` and returns that entry with an `etag`.

`GET /operation` takes `id` and completes a deferred operation.

## Writing

Writes are `POST /act` with a JSON body holding `operation`, `entry`, `format`
and `scope`. The console sends the same body. A refused write answers 409 and
names its refusal code.

Every write carries the channel header. The console always sends `console` and
anything else is `api`. The operations named in `channel_policy.ini` as
console only are refused with `channel_denied` when they arrive on the api
channel.

The console prints the reply body and returns a non zero exit status for every
reply other than 200. A deferred write, a refusal and a transport failure are
therefore told apart by the reply body alone.

The `scope` of a write must equal the governing source of that entry under the
slate contract. A write that omits `scope` is given the default scope of its
channel, and the two channels default differently. A scope outside the
accepted list is refused with `scope_invalid`.

A write to an entry that exists must carry `If-Match` with the etag last
handed out for that entry by `GET /entry`. A write whose etag no longer
matches is refused with `stale_etag`. The circuit registrar revises every
entry named in the contested feed once, between the read that hands out its
etag and the first write that quotes it, so the etag for such an entry must be
fetched again and the write repeated under the fresh etag.

A write may carry an idempotency key header. A repeat carrying a key already
seen returns the stored result and applies nothing further. A repeat carrying
no key applies again.

A write whose entry is of the format named by the seed as deferred answers 202
with an `operation_id` and changes nothing until `GET /operation` is called
with that id. The journal records deferred operations at the sequence they
complete, so an operation must be completed before the next one begins if the
order of the journal is to follow the order of the writes.

`POST /renew` resets the request budget and costs nothing against it. Every
other request costs one unit. Once the budget is spent, requests answer 401
with the expiry code until the budget is renewed.

## Journal and digest

The slate is recorded in the order the published report lists its entries, and
each entry is finished before the next one begins: its register where the seed
did not preseed it, then the operation its verdict calls for, then any
reinstatement it earns.

The etag of an entry is read once, immediately before the first write that
quotes it, so a revision the registrar makes in between is met as a refusal
and answered with a fresh read.

Each applied operation takes the next sequence number, starting at one, and
appends a journal row holding that sequence, the operation, the entry, the
scope and the channel. The digest begins as the hexadecimal SHA256 of the
slate id and advances with each applied operation to the hexadecimal SHA256 of
the previous digest, a vertical bar, and the sequence, operation, entry, scope
and channel joined by colons. Refused operations advance neither the sequence
nor the digest.
