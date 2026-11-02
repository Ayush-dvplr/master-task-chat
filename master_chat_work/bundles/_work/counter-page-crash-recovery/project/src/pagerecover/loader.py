"""Readers for the recovery inputs of one book."""
import configparser
import csv
import json
import os

from . import pages


def _read(path, mode="r"):
    if not os.path.exists(path):
        return b"" if "b" in mode else ""
    with open(path, mode) as fh:
        return fh.read()


def read_journal(path):
    by_image = {}
    for line in _read(path).splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        image = row.pop("image")
        by_image.setdefault(image, []).append(row)
    return by_image


def read_page_map(path):
    parser = configparser.ConfigParser()
    parser.read_string(_read(path))
    return {section: {key: int(value) for key, value in parser[section].items()}
            for section in parser.sections()}


def read_masters(path):
    import tomli

    data = tomli.loads(_read(path))
    return {image: int(entry["master_lsn"]) for image, entry in data.get("images", {}).items()}


def read_catalog(path):
    owners = {}
    for row in csv.DictReader(_read(path).splitlines()):
        owners.setdefault(row["image"], {})[int(row["txn"])] = row["client"]
    return owners


def read_queries(path):
    text = _read(path)
    queries = {}
    for q in (json.loads(text)["queries"] if text else []):
        queries.setdefault(q["image"], []).append(q)
    return queries


def load_book(data_dir):
    journal = read_journal(os.path.join(data_dir, "journal.jsonl"))
    page_map = read_page_map(os.path.join(data_dir, "page_map.ini"))
    masters = read_masters(os.path.join(data_dir, "checkpoint.toml"))
    owners = read_catalog(os.path.join(data_dir, "txn_catalog.csv"))
    queries = read_queries(os.path.join(data_dir, "audit_queries.json"))
    disk = {}
    for frame in pages.decode(_read(os.path.join(data_dir, "disk_pages.bin"), "rb")):
        disk.setdefault(frame["image"], {})[frame["page"]] = {
            "page_lsn": frame["page_lsn"], "slots": frame["slots"]}
    images = {}
    for image_id in sorted(page_map):
        images[image_id] = {
            "id": image_id,
            "pages": page_map[image_id],
            "disk": disk.get(image_id, {}),
            "records": journal.get(image_id, []),
            "master": masters.get(image_id, 0),
        }
    return {"images": images, "owners": owners, "queries": queries}
