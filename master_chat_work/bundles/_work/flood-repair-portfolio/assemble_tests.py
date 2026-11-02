"""Build BUNDLE/tests/test_output.py from tests_template.py, bookgen.py and the pinned books.

python3 -B assemble_tests.py
"""
import hashlib
import json
import os
import pprint
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bookgen  # noqa: E402
import datagen  # noqa: E402

HIDDEN = json.load(open(os.path.join(HERE, "hidden_meta.json")))


def digest(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def main():
    books = {}
    shipped, _ = bookgen.make_book(datagen.SEED, datagen.SPEC)
    for name, text in shipped.items():
        with open(os.path.join(datagen.DATA, name), encoding="utf-8") as fh:
            assert fh.read() == text, "shipped %s differs from the generator" % name
    books["SHIPPED"] = {"seed": datagen.SEED, "spec": datagen.SPEC, "sha256": digest(shipped)}
    for name in ("H1", "H2", "H3", "M"):
        entry = HIDDEN[name]
        spec = dict(entry["spec"])
        spec["large"] = [tuple(x) for x in spec["large"]]
        files, _ = bookgen.make_book(entry["seed"], spec)
        books[name] = {"seed": entry["seed"], "spec": spec, "sha256": digest(files)}

    src = open(os.path.join(HERE, "bookgen.py"), encoding="utf-8").read()
    head = '"""Seeded generator of flood repair books (standard library only).\n\n' \
           'make_book(seed, spec) -> (files, meta); files maps a file name to its text.\n"""\nimport json\n'
    assert src.startswith(head)
    body = "# Seeded book generator (the same code wrote the shipped book).\n" + src[len(head):].strip("\n") + "\n"

    docs = [
        ("feasible", 3, '_feasible("{B}")',
         "On book {T}, every planned round's portfolio is conflict-free, maximal and its total_benefit is the sum of its benefits."),
        ("optimal", 5, '_optimal("{B}")',
         "On book {T}, every planned round's selected list equals the expected best portfolio."),
        ("summary", 5, '_hidden_documents("{B}", ("summary.json",))',
         "On book {T}, summary.json equals the expected document exactly."),
        ("policy_audit", 3, '_hidden_documents("{B}", ("policy_audit.json",))',
         "On book {T}, policy_audit.json equals the expected document exactly."),
        ("data_quality", 3, '_hidden_documents("{B}", ("data_quality.json",))',
         "On book {T}, data_quality.json equals the expected document exactly."),
        ("regions", 3, '_hidden_documents("{B}", REGION_DOCS)',
         "On book {T}, the four region documents equal the expected documents exactly."),
        ("segments", 3, '_hidden_documents("{B}", SEGMENT_DOCS)',
         "On book {T}, the two segment documents equal the expected documents exactly."),
    ]
    crit, weights = [], []
    for name, text in (("H1", "H1"), ("H2", "H2"), ("H3", "H3")):
        label = name.lower()
        for suffix, weight, call, desc in docs:
            fn = "%s_book_%s" % (label, suffix)
            crit.append('@criterion(description=%r)\ndef %s(workspace: Path) -> bool:\n    return _holds(lambda: %s)\n'
                        % (desc.format(T=text), fn, call.format(B=name)))
            weights.append("criteria.%s(weight=%d)" % (fn, weight))

    out = open(os.path.join(HERE, "tests_template.py"), encoding="utf-8").read()
    out = out.replace("#@BOOKGEN@\n", body)
    out = out.replace("#@BOOKS@\n", "_BOOKS: dict[str, dict[str, Any]] = "
                      + pprint.pformat(books, width=110, compact=True, sort_dicts=True) + "\n")
    out = out.replace("#@HIDDEN_CRITERIA@\n", "\n\n".join(crit))
    out = out.replace("#@HIDDEN_WEIGHTS@\n", "\n".join(weights) + "\n")
    assert "#@" not in out
    path = os.path.join(datagen.BUNDLE, "tests", "test_output.py")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(out)
    print("wrote", path, len(out.splitlines()), "lines")


if __name__ == "__main__":
    main()
