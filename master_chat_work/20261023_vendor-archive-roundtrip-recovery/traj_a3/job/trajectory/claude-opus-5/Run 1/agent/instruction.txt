A data engineering team is migrating long-lived telemetry archives after the vendor software that wrote them was retired. The archives are in VARC1, a compact, stateful binary container written by the old Sluicegate batch loader. Your job is to rebuild the codec for it.

The format is described in the files under `/app/data`. `/app/data/format_contract.md` is the authority for the format and points to the other documents, the tables and the captures; where another file disagrees with it, the contract is right.

Write two programs and four reports:

- `/app/decode.py`, run as `python3 /app/decode.py <file.varc>`, prints one JSON decode document to standard output and exits 0; for a rejected segment it prints one JSON error object and still exits 0. Run as `python3 /app/decode.py --stream <manifest.json>` it decodes the segment files a manifest lists, and as `python3 /app/decode.py --salvage <file.varc>` it recovers what it can from a segment with in-band damage.
- `/app/encode.py`, run as `python3 /app/encode.py <document.json> <output.varc>`, writes the segment bytes for a decode document. An unmodified document comes back byte for byte; a new or changed record is written in the shortest form.
- `/app/out/decoded_examples.jsonl`, `/app/out/format_report.json`, `/app/out/roundtrip_report.json` and `/app/out/error_analysis.json`, in the shapes `/app/data/decoder_appendix.md` gives. The reports cover the shipped catalog and the examples you build yourself, and nothing else.

Both programs are run in a clean Python 3.12 with only the standard library, on segment files, manifests and documents you have not seen. They cannot read anything under `/app/data` while they run and cannot import helper modules left beside them, so bake what they need from the tables into the programs. The same input must always give the same output. Each output document is graded whole on fresh inputs. VARC1 is invented for this task; everything about it is in the shipped files.

When you are done, reply with a short account of what you built and how you checked it.

You have 7200 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
