"""warrant-ctl: compile bitemporal access profiles from an identity corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit  # noqa: E402
import policy  # noqa: E402
from corpus import Corpus, CorpusError  # noqa: E402

TOOL = "warrant-ctl"


def dump(path: str, doc) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_config(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cmd_resolve(args) -> None:
    corpus = Corpus(Path(args.data))
    config, _, _ = policy.resolve(corpus)
    dump(args.out, config)


def cmd_compile(args) -> None:
    corpus = Corpus(Path(args.data))
    comp, results = audit.build(corpus, load_config(args.config))
    if args.profile not in results:
        raise CorpusError(f"unknown profile {args.profile}")
    dump(args.out, audit.profile_doc(results[args.profile]))


def cmd_audit(args) -> None:
    corpus = Corpus(Path(args.data))
    comp, results = audit.build(corpus, load_config(args.config))
    dump(args.out, audit.audit_doc(comp, results))


def cmd_summarize(args) -> None:
    corpus = Corpus(Path(args.data))
    comp, results = audit.build(corpus, load_config(args.config))
    doc = audit.audit_doc(comp, results)
    dump(args.out, audit.summary_doc(corpus, comp, results, doc))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog=TOOL)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("resolve-config")
    p.add_argument("--data", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_resolve)
    for name, func in (("compile", cmd_compile), ("audit", cmd_audit), ("summarize", cmd_summarize)):
        p = sub.add_parser(name)
        p.add_argument("--data", required=True)
        p.add_argument("--config", required=True)
        if name == "compile":
            p.add_argument("--profile", required=True)
        p.add_argument("--out", required=True)
        p.set_defaults(func=func)
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except CorpusError as exc:
        print(f"{TOOL}: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
