"""Readers for the recovery inputs of one book."""
import configparser
import csv
import json
import os
import tomllib

from . import pages

INPUTS = ("journal.jsonl", "disk_pages.bin", "page_map.ini", "checkpoint.toml",
          "txn_catalog.csv", "audit_queries.json")


class MissingInput(Exception):
    """A recovery input of the book is absent; args[0] is its file name."""


def _read(path, mode="r"):
    if "b" in mode:
        with open(path, "rb") as fh:
            return fh.read()
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def read_journal(path):
    by_image = {}
    for line in _read(path).splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        image = row.pop("image")
        by_image.setdefault(image, []).append(row)
    for rows in by_image.values():
        rows.sort(key=lambda r: r["lsn"])
    return by_image


def read_page_map(path):
    parser = configparser.ConfigParser()
    parser.optionxform = str
    parser.read_string(_read(path))
    return {section: {key: int(value) for key, value in parser[section].items()}
            for section in parser.sections()}


def read_masters(path):
    data = tomllib.loads(_read(path))
    return {image: int(entry["master_lsn"]) for image, entry in data.get("images", {}).items()}


def read_catalog(path):
    owners = {}
    for row in csv.DictReader(_read(path).splitlines()):
        owners.setdefault(row["image"], {})[int(row["txn"])] = row["client"]
    return owners


def read_queries(path):
    queries = {}
    for q in json.loads(_read(path))["queries"]:
        queries.setdefault(q["image"], []).append(q)
    return queries


def load_book(data_dir):
    for name in INPUTS:
        if not os.path.isfile(os.path.join(data_dir, name)):
            raise MissingInput(name)
    journal = read_journal(os.path.join(data_dir, "journal.jsonl"))
    page_map = read_page_map(os.path.join(data_dir, "page_map.ini"))
    masters = read_masters(os.path.join(data_dir, "checkpoint.toml"))
    owners = read_catalog(os.path.join(data_dir, "txn_catalog.csv"))
    queries = read_queries(os.path.join(data_dir, "audit_queries.json"))
    disk = {}
    bad_frames = {}
    for frame in pages.decode(_read(os.path.join(data_dir, "disk_pages.bin"), "rb")):
        image_pages = disk.setdefault(frame["image"], {})
        if not frame["crc_ok"] or frame["page"] in image_pages:
            bad_frames[frame["image"]] = bad_frames.get(frame["image"], 0) + 1
        image_pages[frame["page"]] = {"page_lsn": frame["page_lsn"], "slots": frame["slots"]}
    images = {}
    for image_id in sorted(page_map):
        images[image_id] = {
            "id": image_id,
            "pages": page_map[image_id],
            "disk": disk.get(image_id, {}),
            "bad_frames": bad_frames.get(image_id, 0),
            "records": journal.get(image_id, []),
            "master": masters.get(image_id, 0),
        }
    return {"images": images, "owners": owners, "queries": queries}
