Implement the codec for {{FORMAT_TAG}}, a proprietary {{CONTAINER_NOUN}} container the {{PRODUCER_SYSTEM}} writes. The container directory holds a written specification for the format together with supporting reference material; read the specification carefully and work out the grammar, the record modes, the state semantics, the rejection rules and the CRC trailer from what it documents. Everything a decoder and encoder need is written down somewhere under `/app/data`, and part of the task is deciding which of those files matters for a given question.

Your job is to deliver a decoder and an encoder that agree with that specification on captures you will not see. Write the decoder to `/app/decode.py` and the encoder to `/app/encode.py`. `/app/decode.py`, invoked as `python3 /app/decode.py <input.{{FORMAT_EXT}}>`, should print one JSON object to stdout and exit 0, with nothing else on stdout, and it should still exit 0 when a file turns out to be damaged. `/app/encode.py`, invoked as `python3 /app/encode.py <document.json> <output.{{FORMAT_EXT}}>`, should read a document in that same JSON shape and write the container it came from, reproducing the original file byte for byte. A decoded capture looks like this:

```json
{
  "version": 1,
  "flags": {"reserved_bit_0": false},
  "record_count": 2,
  "base_value": 0,
  "records": [
    {"key": 1, "mode": "raw", "wide_value": true, "long_key": false, "raw_value": 42, "value": 42},
    {"key": 2, "mode": "raw", "wide_value": true, "long_key": false, "raw_value": -3, "value": -3}
  ]
}
```

The `records` array carries exactly `record_count` objects in file order. The `value` field is always the fully-resolved signed integer for that record, and the pre-resolution payload each mode records lets the encoder rebuild the file byte for byte. Keys are integers when short and UTF-8 strings when long. Every number must be an integer, and key order and whitespace inside the JSON are up to you. When a file has to be rejected, the decoder reports the failure as a single JSON error object carrying exactly the keys the specification defines for that error, following the precedence the specification sets out.

Alongside the two programs, leave a JSONL decoding of your own illustrative examples at `/app/out/decoded_examples.jsonl`, a deterministic summary of the grammar you recovered and the header layout and mode mapping at `/app/out/format_report.json`, a deterministic self-check that each illustrative example satisfies `encode(decode(bytes)) == bytes` at `/app/out/roundtrip_report.json`, and a deterministic summary of the documented error paths and their precedence at `/app/out/error_analysis.json`, each in the shape the decoder appendix lays out. Do not put hidden or reseeded corpus answers in any of these files; they cover only examples you construct yourself.

Both programs will be run against captures you have not seen, in a clean Python 3.12 that has only the standard library, so anything you pip install here will not be present at grading time. Only the six artifact paths named above are collected; `/app/decode.py` and `/app/encode.py` cannot import helper modules you write alongside them, and they cannot read `/app/data` while they run. {{FORMAT_TAG}} is invented for this task, so there is nothing about it to find elsewhere. The verifier is adversarial: it checks for code that reads the reference corpus at runtime, for behaviour that keys on the input filename, for reassignment of the standard-library functions it relies on, and for output that changes between two runs on the same input.

You have {{AGENT_TIMEOUT_SEC_INT}} seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
