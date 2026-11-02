# Serialization policy

Reports are compared byte for byte. The rules below define the only accepted byte
form.

## Canonical form

The canonical form of any value is the JSON text produced with keys sorted, the
compact separators comma and colon with no spaces, and non ASCII characters escaped.
In the Python standard library that is exactly

    json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

Each report file holds the canonical form of its top level object followed by exactly
one newline byte, encoded as UTF-8. No byte order mark, no indentation, no blank line,
no second newline, no trailing spaces.

## Numbers

Integers only. A value such as `1289.0` is wrong where `1289` is right. Signed values
such as a negative delta or a negative coverage gap are written with a leading minus and
no plus sign is ever written. Counts that happen to be zero are still present as `0`;
no key is omitted because its value is zero, and no key is written as null.

## Fixed key sets

Every report carries a `document` key naming its kind, and each scenario report also
carries a `profile` key naming the profile it audits. The run contract lists the
complete key set of every report. A report with a missing key, an extra key or a
renamed key is wrong even when every shared value matches.

Reason count maps always carry all ten rejection reasons, including the ones that
counted nothing.

## The body fingerprint

Every report carries a `body_fingerprint` key whose value describes the rest of that
same report.

To compute it, take the finished report object, remove the `body_fingerprint` key,
serialize what is left in canonical form with no trailing newline, encode it as UTF-8,
take the SHA-256 digest, and keep the first 16 characters of the lowercase hexadecimal
digest. Insert that string back as `body_fingerprint`.

The fingerprint is computed last, over the finished body. Changing any other value in
the report changes the fingerprint. The fingerprint never covers itself.

Worked example. The object with `document` set to `demo` and `steps` set to 3 has the
canonical form

    {"document":"demo","steps":3}

whose SHA-256 digest begins `f90020e11bb59b9a`, so the sealed report is

    {"body_fingerprint":"f90020e11bb59b9a","document":"demo","steps":3}

and the file holding it is that line plus one newline byte.

## The rate digest

Each scenario report carries a `rate_digest`. Build the list of one entry per optimizer
step, in step order, where each entry is a two element list holding the step index and
the resolved rate in milli units. Take the canonical form of that list of lists, encode
it as UTF-8, take the SHA-256 digest and keep the first 16 lowercase hexadecimal
characters. A run with no optimizer steps digests the empty list.

Worked example. Two steps with rates 533 and 1067 give the canonical form

    [[1,533],[2,1067]]

## Determinism

Two runs of the same program over the same archive must write identical bytes. Nothing
in a report may depend on the clock, on the process identifier, on hash seeding, on
directory iteration order or on an environment variable.
