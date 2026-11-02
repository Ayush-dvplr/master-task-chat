"""Assemble BUNDLE/tests/test_output.py from tests_template.py, bookgen.py and the build metadata (WORK only)."""
import hashlib
import json
import os
import pprint
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bookgen  # noqa: E402
import datagen  # noqa: E402

BUNDLE = os.path.join(HERE, "..", "..", "cleanroom-window-schedule")
DATA = os.path.join(BUNDLE, "environment", "data")
SIZES = {"H1": (400, 300, 61), "H2": (500, 350, 200), "H3": (450, 320, 400), "M": (300, 250, 30)}
LABEL = {"H1": "dense", "H2": "carry", "H3": "wide"}
TEXT = {"H1": "a fresh book of dense nights", "H2": "a fresh book of linked mid-size nights",
        "H3": "a fresh book of wide nights"}
DOCS = [("plans_legal", 3, "_legal(%r)", "every plan the program reports for %s keeps every stated plan rule and its night figures follow from it."),
        ("plans_optimal", 5, "_optimal(%r)", "every accepted night of %s gets exactly the maximum-net-value plan."),
        ("summary_matches", 5, "_hidden_documents(%r, (\"summary.json\",))", "summary.json for %s equals the expected document exactly."),
        ("policy_audit_matches", 3, "_hidden_documents(%r, (\"policy_audit.json\",))", "policy_audit.json for %s equals the expected document exactly."),
        ("data_quality_matches", 3, "_hidden_documents(%r, (\"data_quality.json\",))", "data_quality.json for %s equals the expected document exactly."),
        ("regions_match", 3, "_hidden_documents(%r, REGION_DOCS)", "the four region documents for %s equal the expected documents exactly."),
        ("segments_match", 3, "_hidden_documents(%r, SEGMENT_DOCS)", "the two segment documents for %s equal the expected documents exactly.")]


def main():
    shipped = json.load(open(os.path.join(HERE, "shipped_meta.json")))
    hidden = json.load(open(os.path.join(HERE, "hidden_meta.json")))
    sp = datagen.specs()
    files = bookgen.make_book(666278, sp, shipped["attempts"], 3000, 2600, (75, 1500), 60)
    for name, text in files.items():
        with open(os.path.join(DATA, name), encoding="utf-8") as fh:
            assert fh.read() == text, name
    books = {"SHIPPED": {"seed": 666278, "specs": None, "attempts": shipped["attempts"], "clients": 3000,
                         "sites": 2600, "thresholds": [75, 1500], "start": 60,
                         "sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}}
    for name in ("H1", "H2", "H3", "M"):
        m = hidden[name]
        c, s, d = SIZES[name]
        books[name] = {"seed": m["seed"], "specs": m["specs"], "attempts": m["attempts"], "clients": c,
                       "sites": s, "thresholds": m["thresholds"], "start": d, "sha256": m["sha256"]}
    src = open(os.path.join(HERE, "bookgen.py"), encoding="utf-8").read().splitlines(keepends=True)
    body = "".join(src[3:]).rstrip("\n") + "\n"
    template = open(os.path.join(HERE, "tests_template.py"), encoding="utf-8").read()
    crit, weights = [], []
    for name in ("H1", "H2", "H3"):
        for suffix, w, call, desc in DOCS:
            fn = "%s_book_%s" % (LABEL[name], suffix)
            text = desc % TEXT[name]
            crit.append("@criterion(description=%s)\ndef %s(workspace: Path) -> bool:\n    return _holds(lambda: %s)\n\n"
                        % (json.dumps(text[0].upper() + text[1:]), fn, call % name))
            weights.append("criteria.%s(weight=%d)" % (fn, w))
    books_src = "_BOOKS: dict[str, dict[str, Any]] = " + pprint.pformat(books, width=110, compact=True) + "\n"
    out = (template.replace("#@BOOKGEN@\n", body)
           .replace("#@BOOKS@\n", books_src)
           .replace("#@HIDDEN_CRITERIA@\n", "\n".join(crit).rstrip("\n") + "\n")
           .replace("#@HIDDEN_WEIGHTS@\n", "\n".join(weights) + "\n"))
    assert "#@" not in out
    with open(os.path.join(BUNDLE, "tests", "test_output.py"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(out)
    print("written", len(out.splitlines()), "lines")


if __name__ == "__main__":
    main()
