# Client identity

Work orders name a client by alias key. The client directory lists one row per
client with its alias key, its home site, its service class, its budget ceiling in
micro units, an optional merge target, an optional retirement day and the first day
on which the client may hold work.

- An alias key names exactly one directory row.
- A row that carries a merge target has been absorbed by the row it names. Work
  that arrives under the absorbed alias belongs to the absorbing client. Merge
  targets chain, and the chain is followed to its end.
- Where a chain of merge targets closes on itself, the client whose identifier
  sorts first among the identifiers on that closed chain governs the work.
- A client that carries a retirement day holds no work on that day or after it.
  Work that arrives on or after the retirement day of its governing client is
  rejected and settles nowhere.
- A client whose first active day is later than the submission day of the work is
  unable to accept it. Such work is deferred rather than rejected.
- The home site and service class of a work order are those of its governing
  client, never those of the alias it arrived under.
