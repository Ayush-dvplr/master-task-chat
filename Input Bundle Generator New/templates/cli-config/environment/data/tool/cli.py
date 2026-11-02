#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, data):
    Path(path).write_text(json.dumps(data) + "\n")


def cmd_init(args):
    schema = load_json(args.config)  # BUG: should read args.schema
    data = {
        "profile": schema["profile"],
        "producer": schema["producer"],
        "container": schema["container"],
        "settings": {"checksum": schema["checksum"]},  # BUG: nested data is invalid
    }
    write_json(args.out, data)


def cmd_set(args):
    data = load_json(args.config)
    data[args.key.upper()] = args.value  # BUG: key case and scalar coercion are wrong
    write_json(args.config, data)


def cmd_validate(args):
    schema = load_json(args.schema)
    data = load_json(args.config)
    missing = [key for key in schema["required_keys"].split(",") if key not in data]
    if missing:
        raise SystemExit("missing: " + ",".join(missing))
    if any(isinstance(value, (dict, list)) for value in data.values()):
        raise SystemExit("configuration must be flat")
    print("ok")


def cmd_report(args):
    data = load_json(args.config)
    report = {"ok": True, "config": data, "commands": "unknown"}  # BUG: transcript shape is unusable
    write_json(args.out, report)


def main():
    parser = argparse.ArgumentParser(prog="{{PACKAGE_NAME}}-ctl")
    sub = parser.add_subparsers(dest="command")  # BUG: command is not required
    p = sub.add_parser("init")
    p.add_argument("--schema", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_init)
    p = sub.add_parser("set")
    p.add_argument("--config", required=True)
    p.add_argument("--key", required=True)
    p.add_argument("--value", required=True)
    p.set_defaults(func=cmd_set)
    p = sub.add_parser("validate")
    p.add_argument("--schema", required=True)
    p.add_argument("--config", required=True)
    p.set_defaults(func=cmd_validate)
    p = sub.add_parser("export-report")
    p.add_argument("--config", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_report)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
