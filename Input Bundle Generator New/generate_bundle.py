#!/usr/bin/env python3
"""Scaffold a new Harbor input bundle from templates/.

v2.0 changes over v1:

    * ``--category`` picks one of 16 human categories (see CATEGORIES.md).
      Each category emits an exact Title-Case display value while retaining an
      internal frontier-bench domain/subcategory pair and category-scoped
      narrative/MAGIC-byte pools.
    * ``--seed INT`` is optional.  Without it, the generator draws 64 random
      bits from ``secrets`` and prints the chosen seed so the run is
      reproducible.  With it, generation is byte-deterministic.
    * ``--random`` picks a random category too.  When ``--random`` is set,
      every other identifying argument (``--name``, ``--title``,
      ``--format-tag``, ``--format-ext``, ``--description``, ``--keywords``)
      becomes optional and is auto-generated.  A single required argument
      remains: ``--out``.
    * When any of the identifying arguments is omitted (with or without
      ``--random``), the generator synthesizes a coherent value from the
      seed + category so ``generate_bundle.py --out /tmp/x --category
      security`` is a valid one-liner.
    * Templates now carry additional placeholders that are derived from the
      seed rather than the CLI: ``{{SAMPLE_SEED}}``, ``{{CHALLENGE_SEED}}``,
      ``{{EVAL_SEED}}``, ``{{MAGIC_ASCII}}``, ``{{VERSION_NUM}}``,
      ``{{CATEGORY_CANONICAL}}``, ``{{SUBCATEGORY}}``,
      ``{{CATEGORY_HUMAN}}``, ``{{SEED_HEX}}``.

The generator remains dependency-free (stdlib only) and never touches paths
outside ``<out>/<name>/``.  It preserves executable bits on
``solution/solve.sh`` and ``tests/test.sh``.
"""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import itertools
import json
import os
import random
import re
import secrets
import shutil
import stat
import struct
import subprocess
import sys
import textwrap
import tomllib
import zipfile
import zlib
from pathlib import Path
from typing import Any, Iterable, NoReturn, NotRequired, TypedDict, cast

_REPO_ROOT = Path(__file__).resolve().parent
_TEMPLATE_ROOT = _REPO_ROOT / "templates"
_ARCHETYPE_MANIFEST = "archetype.toml"
_DEFAULT_ARCHETYPE = "format-recovery"
_ARCHETYPE_AUTO = "auto"
_ARCHETYPE_RANDOM = "random"

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
_ARCHETYPE_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
_TAG_RE = re.compile(r"^[A-Z][A-Z0-9]{2,7}$")
_EXT_RE = re.compile(r"^\.[a-z0-9]{2,8}$")

_SKIP_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
_SKIP_FILE_SUFFIXES = (".pyc", ".pyo")
_DATAGEN = "datagen.py"
_SKIP_FILE_NAMES = {_ARCHETYPE_MANIFEST, _DATAGEN}


class ModeIds(TypedDict):
    raw: int
    delta: int
    dict: int


class SelectorGrammar(TypedDict):
    mode_bits: list[int]
    wide_bit: int
    long_key_bit: int
    mode_ids: ModeIds


class ContainerGrammar(TypedDict):
    selector: SelectorGrammar
    header_order: list[str]
    delta_encoding: str
    dict_source: str
    dict_direction: str
    crc_coverage: str


class SourceArchive(TypedDict):
    source: str
    output: str


class InputDir(TypedDict):
    dir: str
    mount: str


_DEFAULT_INPUTS: list[InputDir] = [{"dir": "data", "mount": "/app/data"}]
_INPUT_DIR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class ArchetypeManifest(TypedDict):
    name: str
    summary: str
    artifacts: list[str]
    default_description: str
    default_keywords: list[str]
    dependencies: dict[str, list[str]]
    inputs: list[InputDir]
    datagen_input: str
    source_archives: NotRequired[list[SourceArchive]]
    post_generate: NotRequired[list[str]]


# ---------------------------------------------------------------------------
# Category taxonomy.  See CATEGORIES.md for the human-readable table.
# Each entry declares:
#   display      -- the Title-Case string emitted as [metadata].category.
#                   Held as an explicit field rather than derived by
#                   title-casing the key, so a downstream vocabulary change
#                   is a one-line edit here.
#   canonical    -- the frontier-bench [metadata].category (7 domains)
#   subcategory  -- an open-list [metadata].subcategory string
#   magic_pool   -- 5-byte ASCII magic candidates for the invented format
#   tag_prefix_pool -- short uppercase prefixes for --format-tag synthesis
#   ext_pool     -- lowercase file extensions (WITHOUT the leading dot)
#   noun_pool    -- narrative nouns used in the auto-description
#   verb_pool    -- narrative verbs used in the auto-description
#   producer_pool -- fictional systems that emit the format, used to open
#                    instruction.md with a concrete in-world backstory
#   keyword_pool -- keyword candidates for the [task].keywords array
# ---------------------------------------------------------------------------
_CATEGORIES: dict[str, dict] = {
    "software-engineering": {
        "display": "Software Engineering",
        "canonical": "Software",
        "subcategory": "Systems",
        "family": "format-recovery",
        "notes": "closest match to the reference bundle",
        "magic_pool": [b"MICRO", b"HEXBF", b"ROLLP", b"BYTEA", b"CODEC"],
        "tag_prefix_pool": ["MICRO", "HEXBF", "ROLLP", "BYTEC"],
        "ext_pool": ["mbin", "hbin", "rbin", "bcod"],
        "noun_pool": ["container", "envelope", "packet", "blob", "record"],
        "verb_pool": ["decoded", "parsed", "reversed", "recovered"],
        "producer_pool": [
            "Halyard release bus",
            "BUILD-7 artifact pipeline",
            "Meridian packaging service",
            "Coreline build farm",
        ],
        "keyword_pool": [
            "binary",
            "reverse-engineering",
            "python",
            "container",
            "format-recovery",
            "stdlib",
            "bytes",
            "protocol",
        ],
    },
    "system-admin": {
        "display": "System Administration",
        "canonical": "Software",
        "subcategory": "Systems",
        "family": "format-recovery",
        "notes": "ops-style narrative",
        "magic_pool": [b"LOGRC", b"PROCT", b"NETST", b"MOUNT", b"CRONT"],
        "tag_prefix_pool": ["LOGRC", "PROCT", "NETST", "MOUNT"],
        "ext_pool": ["lrec", "psnp", "nstat", "mtab"],
        "noun_pool": ["log dump", "process snapshot", "mount table", "cron manifest"],
        "verb_pool": ["parsed", "diffed", "audited", "reconstructed"],
        "producer_pool": [
            "Nodewatch fleet agent",
            "OPS-3 host collector",
            "Sentinel inventory daemon",
            "Rampart config sweeper",
        ],
        "keyword_pool": [
            "sysadmin",
            "ops",
            "log-parsing",
            "snapshot",
            "monitoring",
            "stdlib",
            "python",
            "binary",
        ],
    },
    "data-science": {
        "display": "Data Science",
        "canonical": "ML",
        "subcategory": "Evaluation",
        "family": "format-recovery",
        "notes": "tabular flavor",
        "magic_pool": [b"CSVDX", b"PARQM", b"ARWMB", b"COLPK", b"DFRAM"],
        "tag_prefix_pool": ["CSVDX", "PARQM", "ARWMB", "COLPK"],
        "ext_pool": ["cdx", "pqm", "arw", "cpk"],
        "noun_pool": [
            "dataframe shard",
            "column-packed page",
            "tabular capture",
            "sample archive",
        ],
        "verb_pool": ["loaded", "reconstructed", "sliced", "materialised"],
        "producer_pool": [
            "Quarry feature store",
            "PANEL-2 extract service",
            "Lattice sampling grid",
            "Ferrite dataset packer",
        ],
        "keyword_pool": [
            "data-science",
            "tabular",
            "columnar",
            "packed",
            "evaluation",
            "python",
            "stdlib",
            "binary",
        ],
    },
    "security": {
        "display": "Security",
        "canonical": "Security",
        "subcategory": "Reverse engineering",
        "family": "format-recovery",
        "notes": "packet/blob narrative",
        "magic_pool": [b"NONCE", b"VAULT", b"SEALB", b"CIPHR", b"KEYVL"],
        "tag_prefix_pool": ["NONCE", "VAULT", "SEALB", "CIPHR"],
        "ext_pool": ["nnc", "vlt", "slb", "cphr"],
        "noun_pool": ["sealed blob", "vault entry", "ciphered record", "opaque token"],
        "verb_pool": ["unsealed", "recovered", "decoded", "verified"],
        "producer_pool": [
            "Ironvault sealing service",
            "KMS-9 envelope daemon",
            "Bastion transit proxy",
            "Nightlock key courier",
        ],
        "keyword_pool": [
            "security",
            "reverse-engineering",
            "binary",
            "vault",
            "container",
            "stdlib",
            "python",
            "auth",
        ],
    },
    "scientific-computing": {
        "display": "Scientific Computing",
        "canonical": "Science",
        "subcategory": "Physics",
        "family": "format-recovery",
        "notes": "numeric samples",
        "magic_pool": [b"WAVEF", b"SAMPF", b"TENSR", b"FIELD", b"GRIDX"],
        "tag_prefix_pool": ["WAVEF", "SAMPF", "TENSR", "FIELD"],
        "ext_pool": ["wvf", "smpf", "tsr", "fld"],
        "noun_pool": ["wave packet", "sample stream", "field snapshot", "grid dump"],
        "verb_pool": ["reconstructed", "sampled", "integrated", "recovered"],
        "producer_pool": [
            "Helios telemetry array",
            "RIG-5 acquisition frontend",
            "Kelvin instrument bus",
            "Solstice detector farm",
        ],
        "keyword_pool": [
            "science",
            "numerical",
            "physics",
            "sampling",
            "binary",
            "stdlib",
            "python",
            "format-recovery",
        ],
    },
    "file-operations": {
        "display": "File Operations",
        "canonical": "Software",
        "subcategory": "Systems",
        "family": "format-recovery",
        "notes": "archive/index narrative",
        "magic_pool": [b"FIDX1", b"ARCHV", b"MANFT", b"CATLG", b"TARIX"],
        "tag_prefix_pool": ["FIDX1", "ARCHV", "MANFT", "CATLG"],
        "ext_pool": ["fidx", "arv", "mft", "ctl"],
        "noun_pool": [
            "file index",
            "archive manifest",
            "catalog page",
            "directory snapshot",
        ],
        "verb_pool": ["indexed", "cataloged", "manifested", "reconstructed"],
        "producer_pool": [
            "Cartogram archive indexer",
            "FS-6 catalog builder",
            "Ledgerbox backup appliance",
            "Strongroom vault packer",
        ],
        "keyword_pool": [
            "file-operations",
            "archive",
            "index",
            "catalog",
            "manifest",
            "stdlib",
            "python",
            "binary",
        ],
    },
    "debugging": {
        "display": "Debugging",
        "canonical": "Software",
        "subcategory": "Systems",
        "family": "format-recovery",
        "notes": "crash-dump narrative",
        "magic_pool": [b"CRSHD", b"COREZ", b"MDUMP", b"TRACE", b"BACKT"],
        "tag_prefix_pool": ["CRSHD", "COREZ", "MDUMP", "TRACE"],
        "ext_pool": ["crd", "cor", "mdz", "trc"],
        "noun_pool": ["crash dump", "memory core", "stack trace", "diagnostic capture"],
        "verb_pool": ["parsed", "reconstructed", "diagnosed", "recovered"],
        "producer_pool": [
            "Blackbox crash collector",
            "DBG-4 postmortem daemon",
            "Coredrop capture agent",
            "Faultline trace shipper",
        ],
        "keyword_pool": [
            "debugging",
            "crash-dump",
            "core",
            "stack-trace",
            "diagnostics",
            "binary",
            "stdlib",
            "python",
        ],
    },
    "data-processing": {
        "display": "Data Processing",
        "canonical": "Software",
        "subcategory": "Data engineering",
        "family": "format-recovery",
        "notes": "ETL container flavor",
        "magic_pool": [b"ETLBK", b"BATCH", b"STGE1", b"PIPE1", b"MERGE"],
        "tag_prefix_pool": ["ETLBK", "BATCH", "STGE1", "PIPE1"],
        "ext_pool": ["etl", "bat", "stg", "pip"],
        "noun_pool": ["ETL batch", "staging page", "pipeline shard", "merge record"],
        "verb_pool": ["ingested", "batched", "staged", "recovered"],
        "producer_pool": [
            "Millrace ETL runner",
            "PIPE-8 staging service",
            "Confluence merge engine",
            "Sluicegate batch loader",
        ],
        "keyword_pool": [
            "data-engineering",
            "etl",
            "pipeline",
            "batch",
            "staging",
            "python",
            "stdlib",
            "binary",
        ],
    },
    "model-training": {
        "display": "Model Training",
        "canonical": "ML",
        "subcategory": "Training",
        "family": "format-recovery",
        "notes": "checkpoint blob flavor",
        "magic_pool": [b"CKPT1", b"WGHT1", b"OPTST", b"SHARD", b"EPCH1"],
        "tag_prefix_pool": ["CKPT1", "WGHT1", "OPTST", "SHARD"],
        "ext_pool": ["ckpt", "wgh", "opt", "shd"],
        "noun_pool": [
            "checkpoint shard",
            "weight page",
            "optimiser state",
            "training snapshot",
        ],
        "verb_pool": ["loaded", "resumed", "reconstructed", "recovered"],
        "producer_pool": [
            "Anvil checkpoint writer",
            "TRN-2 trainer harness",
            "Foundry weight shipper",
            "Kilnworks state saver",
        ],
        "keyword_pool": [
            "ml",
            "training",
            "checkpoint",
            "weights",
            "optimiser",
            "python",
            "stdlib",
            "binary",
        ],
    },
    "mathematics": {
        "display": "Mathematics",
        "canonical": "Science",
        "subcategory": "Math",
        "family": "format-recovery",
        "notes": "symbolic ordering",
        "magic_pool": [b"POLYP", b"MATRX", b"VECTM", b"FIELM", b"NUMPK"],
        "tag_prefix_pool": ["POLYP", "MATRX", "VECTM", "FIELM"],
        "ext_pool": ["pol", "mtx", "vcm", "flm"],
        "noun_pool": [
            "polynomial vector",
            "matrix page",
            "field element",
            "coefficient set",
        ],
        "verb_pool": ["evaluated", "reconstructed", "solved", "recovered"],
        "producer_pool": [
            "Abacus solver farm",
            "SYM-3 algebra service",
            "Quadrature evaluation grid",
            "Numerary coefficient store",
        ],
        "keyword_pool": [
            "math",
            "polynomial",
            "matrix",
            "field",
            "numerical",
            "python",
            "stdlib",
            "binary",
        ],
    },
    "machine-learning": {
        "display": "Machine Learning",
        "canonical": "ML",
        "subcategory": "Inference",
        "family": "format-recovery",
        "notes": "tensor packet flavor",
        "magic_pool": [b"TENSF", b"VECTF", b"INFR1", b"BATIN", b"PREDX"],
        "tag_prefix_pool": ["TENSF", "VECTF", "INFR1", "BATIN"],
        "ext_pool": ["tsf", "vcf", "inf", "prd"],
        "noun_pool": [
            "tensor packet",
            "inference batch",
            "prediction record",
            "vector dump",
        ],
        "verb_pool": ["decoded", "batched", "inferred", "recovered"],
        "producer_pool": [
            "Relay inference gateway",
            "INF-6 batch server",
            "Tensorport serving mesh",
            "Predictbox scoring node",
        ],
        "keyword_pool": [
            "ml",
            "inference",
            "tensor",
            "prediction",
            "batch",
            "python",
            "stdlib",
            "binary",
        ],
    },
    "games": {
        "display": "Games",
        "canonical": "Software",
        "subcategory": "Algorithms",
        "family": "format-recovery",
        "notes": "save-file / replay flavor",
        "magic_pool": [b"SAVEG", b"REPLY", b"MOVE1", b"BOARD", b"TURNS"],
        "tag_prefix_pool": ["SAVEG", "REPLY", "MOVE1", "BOARD"],
        "ext_pool": ["svg", "rpl", "mvs", "brd"],
        "noun_pool": ["save state", "replay tape", "move list", "board snapshot"],
        "verb_pool": ["restored", "replayed", "reconstructed", "recovered"],
        "producer_pool": [
            "Replayvault match recorder",
            "SAV-5 state serialiser",
            "Arcade session store",
            "Checkpointer save daemon",
        ],
        "keyword_pool": [
            "games",
            "save-file",
            "replay",
            "state",
            "algorithms",
            "python",
            "stdlib",
            "binary",
        ],
    },
    "video-processing": {
        "display": "Video Processing",
        "canonical": "Media",
        "subcategory": "Design",
        "family": "format-recovery",
        "notes": "frame-packet flavor",
        "magic_pool": [b"FRMPK", b"GOP1X", b"MBLKK", b"KEYFR", b"CHNKV"],
        "tag_prefix_pool": ["FRMPK", "GOP1X", "MBLKK", "KEYFR"],
        "ext_pool": ["fpk", "gop", "mbk", "kfr"],
        "noun_pool": [
            "frame packet",
            "GOP chunk",
            "macroblock page",
            "keyframe capture",
        ],
        "verb_pool": ["decoded", "reassembled", "reconstructed", "recovered"],
        "producer_pool": [
            "Reelworks transcode farm",
            "VID-9 packetiser",
            "Framebus capture card",
            "Cineport mux service",
        ],
        "keyword_pool": [
            "media",
            "video",
            "frame",
            "codec",
            "keyframe",
            "python",
            "stdlib",
            "binary",
        ],
    },
    "data-querying": {
        "display": "Data Querying",
        "canonical": "Software",
        "subcategory": "Databases",
        "family": "format-recovery",
        "notes": "index / catalog flavor",
        "magic_pool": [b"IDXQR", b"BTRE1", b"PAGE1", b"HEAP1", b"CATQR"],
        "tag_prefix_pool": ["IDXQR", "BTRE1", "PAGE1", "HEAP1"],
        "ext_pool": ["idx", "bt1", "pg1", "hp1"],
        "noun_pool": ["index page", "btree node", "heap page", "catalog snapshot"],
        "verb_pool": ["indexed", "queried", "walked", "recovered"],
        "producer_pool": [
            "Indexwright storage engine",
            "QRY-4 page manager",
            "Catalogue btree writer",
            "Heapline table store",
        ],
        "keyword_pool": [
            "databases",
            "index",
            "btree",
            "heap",
            "catalog",
            "python",
            "stdlib",
            "binary",
        ],
    },
    "optimization": {
        "display": "Optimization",
        "canonical": "Software",
        "subcategory": "Algorithms",
        "family": "format-recovery",
        "notes": "schedule blob flavor",
        "magic_pool": [b"SCHDL", b"PLANN", b"ALLOC", b"TASK1", b"SLOT1"],
        "tag_prefix_pool": ["SCHDL", "PLANN", "ALLOC", "TASK1"],
        "ext_pool": ["sch", "pln", "alc", "tsk"],
        "noun_pool": [
            "schedule blob",
            "plan capture",
            "allocation record",
            "task page",
        ],
        "verb_pool": ["scheduled", "planned", "allocated", "recovered"],
        "producer_pool": [
            "Dispatcher planning service",
            "OPT-7 allocator",
            "Schedulehouse solver",
            "Routemark planner daemon",
        ],
        "keyword_pool": [
            "optimization",
            "scheduling",
            "planning",
            "allocation",
            "algorithms",
            "python",
            "stdlib",
            "binary",
        ],
    },
    "personal-assistant": {
        "display": "Personal Assistant",
        "canonical": "Operations",
        "subcategory": "Marketing",
        "family": "format-recovery",
        "notes": "reminder store flavor",
        "magic_pool": [b"RMNDR", b"NOTEX", b"TODO1", b"CALDX", b"ALRTX"],
        "tag_prefix_pool": ["RMNDR", "NOTEX", "TODO1", "CALDX"],
        "ext_pool": ["rmd", "ntx", "tdo", "cdx"],
        "noun_pool": ["reminder blob", "note capture", "todo list", "calendar page"],
        "verb_pool": ["decoded", "restored", "reconstructed", "recovered"],
        "producer_pool": [
            "Daybook reminder store",
            "PA-3 sync service",
            "Notekeeper journal daemon",
            "Agenda calendar packer",
        ],
        "keyword_pool": [
            "ops",
            "reminder",
            "todo",
            "calendar",
            "assistant",
            "python",
            "stdlib",
            "binary",
        ],
    },
}


# Adjective + noun word pools for auto-name synthesis.  Kept small and
# stdlib-only.  Combined with the seed hex prefix these yield >1e8 unique
# names.
_ADJECTIVES = [
    "amber",
    "arctic",
    "azure",
    "bold",
    "brave",
    "brisk",
    "calm",
    "clever",
    "coral",
    "crisp",
    "dapper",
    "deft",
    "eager",
    "empty",
    "faint",
    "fancy",
    "fluent",
    "fresh",
    "gentle",
    "gilded",
    "glossy",
    "hazy",
    "hidden",
    "humble",
    "icy",
    "inky",
    "jaunty",
    "jolly",
    "keen",
    "lively",
    "lucid",
    "merry",
    "misty",
    "nimble",
    "olive",
    "opal",
    "pale",
    "petite",
    "plush",
    "polar",
    "quaint",
    "quiet",
    "rapid",
    "royal",
    "russet",
    "sable",
    "scarlet",
    "silent",
    "slate",
    "snowy",
    "solid",
    "somber",
    "spry",
    "stately",
    "sturdy",
    "sunny",
    "svelte",
    "swift",
    "tacit",
    "teal",
    "terse",
    "tidy",
    "tranquil",
    "urban",
    "valid",
    "vast",
    "vivid",
    "warm",
    "witty",
    "woven",
    "young",
    "zesty",
]
_NOUNS = [
    "acorn",
    "atlas",
    "beacon",
    "bloom",
    "brook",
    "canyon",
    "cedar",
    "cliff",
    "comet",
    "compass",
    "cove",
    "crest",
    "delta",
    "dune",
    "eagle",
    "echo",
    "ember",
    "falcon",
    "fern",
    "fjord",
    "forge",
    "gale",
    "geode",
    "glade",
    "grove",
    "harbor",
    "haven",
    "helix",
    "horizon",
    "island",
    "kestrel",
    "lagoon",
    "lantern",
    "ledger",
    "loft",
    "lumen",
    "meadow",
    "mesa",
    "moth",
    "nebula",
    "nectar",
    "notch",
    "oak",
    "ocean",
    "orbit",
    "orchid",
    "pebble",
    "pine",
    "pinion",
    "plateau",
    "prairie",
    "prism",
    "quartz",
    "quill",
    "ravine",
    "reef",
    "ridge",
    "river",
    "sage",
    "saffron",
    "seed",
    "shore",
    "silo",
    "slate",
    "sparrow",
    "spire",
    "spring",
    "spruce",
    "steppe",
    "summit",
    "swan",
    "thicket",
    "tide",
    "torch",
    "tundra",
    "vista",
    "willow",
    "zephyr",
]


# ---------------------------------------------------------------------------
# Argument validation helpers.  Raises ``_die`` with exit code 2 on failure.
# ---------------------------------------------------------------------------
def _die(msg: str, code: int = 2) -> NoReturn:
    print(f"[generate_bundle] ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def _pick_seed() -> int:
    """Return a non-deterministic 63-bit seed drawn from ``secrets``.

    We stay under 2**63 so seed representations fit int64 sinks (Rust,
    Java, Go) if a downstream family recipe ever needs to persist them.
    """
    return secrets.randbits(63)


def _seeded_random(seed: int) -> random.Random:
    """Return an isolated ``random.Random`` primed with ``seed``.

    Using a private ``Random`` instance means our generation is completely
    isolated from any process-global RNG state, which is what makes runs
    with the same ``--seed`` byte-deterministic.
    """
    return random.Random(seed)


def _slugify(text: str) -> str:
    """Reduce free text to the kebab-case stem of a bundle directory name.

    Keeps at most six words so that a long --title still yields a readable
    directory, and strips anything outside [a-z0-9-] so the result always
    satisfies the stem half of ``_NAME_RE``.
    """
    words = re.findall(r"[a-z0-9]+", text.lower())
    return "-".join(words[:6])


def _numbered_name(stem: str, out_dir: str) -> str:
    """Append the lowest free two-digit ordinal to ``stem``.

    Scans ``out_dir`` for existing ``<stem>-NN`` siblings so that repeated
    generations of the same subject land as -01, -02, ... instead of
    colliding. Falls back to -01 when the output directory is unreadable.
    """
    used: set[int] = set()
    try:
        pattern = re.compile(rf"^{re.escape(stem)}-([0-9]+)$")
        for entry in Path(out_dir).expanduser().iterdir():
            match = pattern.match(entry.name)
            if match:
                used.add(int(match.group(1)))
    except OSError:
        pass
    ordinal = next(n for n in itertools.count(1) if n not in used)
    return f"{stem}-{ordinal:02d}"


def _auto_name(rng: random.Random, category: str, seed: int) -> str:
    """Synthesize a unique bundle directory name.

    Fallback used only when neither --name nor --title is supplied, so
    there is no task subject to slugify.  Format:
    ``<category-slug>-<adjective>-<noun>``.  The ordinal suffix that makes
    the directory unique is appended later by :func:`_numbered_name`.
    """
    adj = rng.choice(_ADJECTIVES)
    noun = rng.choice(_NOUNS)
    del seed
    return f"{category}-{adj}-{noun}"


def _auto_title(name: str) -> str:
    """Convert 'batch-eval-parity-01' to 'Batch Eval Parity'."""
    stem = re.sub(r"-[0-9]+$", "", name)
    return " ".join(part.capitalize() for part in stem.split("-") if part)


def _auto_format_tag(rng: random.Random, category: str) -> str:
    """Pick a valid --format-tag from the category's tag_prefix_pool.

    We simply pick one of the pre-vetted prefixes; every entry in every
    pool already satisfies ``_TAG_RE``.
    """
    return rng.choice(_CATEGORIES[category]["tag_prefix_pool"])


def _auto_format_ext(rng: random.Random, category: str) -> str:
    """Pick a valid --format-ext with leading dot from the category's ext_pool."""
    return "." + rng.choice(_CATEGORIES[category]["ext_pool"])


def _auto_magic(rng: random.Random, category: str) -> bytes:
    return rng.choice(_CATEGORIES[category]["magic_pool"])


def _auto_container_noun(rng: random.Random, category: str) -> str:
    return rng.choice(_CATEGORIES[category]["noun_pool"])


def _auto_producer(rng: random.Random, category: str) -> str:
    return rng.choice(_CATEGORIES[category]["producer_pool"])


def _auto_version(rng: random.Random) -> int:
    """VERSION 1..5 chosen from seed.  Kept small so u8 slot is always fine."""
    return rng.randint(1, 5)


def _derive_seed(root: int, tag: str) -> int:
    """Derive a stable child seed from a root seed and a string tag.

    Uses BLAKE2b so the derivation is deterministic without depending on
    Python's hash randomization.  We keep 63 bits so downstream int-typed
    consumers see a non-negative value.
    """
    digest = hashlib.blake2b(f"{root}:{tag}".encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") & ((1 << 63) - 1)


# ---------------------------------------------------------------------------
# Substitution table.  Built once per invocation from the fully-resolved
# arguments (either user-supplied or auto-generated).
# ---------------------------------------------------------------------------
def _keywords_toml_array(raw: str) -> str:
    tokens = [tok.strip() for tok in raw.split(",") if tok.strip()]
    return "[" + ", ".join(json.dumps(tok) for tok in tokens) + "]"


# Harbor 0.24 QC (FC-S18) requires every author to carry a real full name
# ("First Last" or "First Middle Last", each word capitalised with the rest
# lowercase) plus an email whose local part is built from the name words.  We
# therefore accept ``--author`` only in the explicit ``Full Name <email>`` form
# so neither half can be inferred wrongly.  See structure_qc.AUTHOR_NAME_RE and
# structure_qc.name_matches_email for the authoritative shape.
_AUTHOR_NAME_WORD_RE = re.compile(r"^[A-Z](?:[a-z]+|'[A-Z][a-z]+)(?:-[A-Z][a-z]+)*$")
_AUTHOR_EMAIL_RE = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")
_AUTHOR_ENTRY_RE = re.compile(r"^(?P<name>.+?)\s*<(?P<email>[^<>]+)>\s*$")


def _author_name_is_real(name: str) -> bool:
    words = name.split(" ")
    if len(words) < 2:
        return False
    return all(_AUTHOR_NAME_WORD_RE.match(w) for w in words)


def _author_email_is_built_from_name(name: str, email: str) -> bool:
    """Mirror of structure_qc.name_matches_email.

    Returns True when the email local part (letters only, lower-cased) can be
    assembled from the author's name words (any order, each word used whole,
    as its initial, or skipped, with at least one word used whole).
    """
    local = re.sub(r"[^a-z]", "", email.split("@", 1)[0].lower())
    words = [w for w in re.split(r"[^a-z]+", name.lower()) if w]
    if not local or not words:
        return False
    from itertools import permutations

    def build(rest: str, ws: tuple[str, ...], whole: bool) -> bool:
        if not ws:
            return not rest and whole
        w, tail = ws[0], ws[1:]
        return ((rest.startswith(w) and build(rest[len(w):], tail, True))
                or (rest.startswith(w[0]) and build(rest[1:], tail, whole))
                or build(rest, tail, whole))

    return any(build(local, p, False) for p in permutations(words[:4]))


def _split_author_entry(entry: str) -> tuple[str, str]:
    """Split ``"Full Name <email@domain>"`` into ``(name, email)``."""
    match = _AUTHOR_ENTRY_RE.match(entry)
    if match is None:
        raise ValueError(f"not a validated --author entry: {entry!r}")
    return match.group("name").strip(), match.group("email").strip()


def _authors_toml_array(entries: list[str]) -> str:
    """Render ``[task].authors`` as TOML inline tables of ``{name, email}``.

    Harbor 0.24 QC rejects bare-string authors and author tables whose ``name``
    is not a real human name (structure_qc FC-S18).  The generator therefore
    always emits inline tables and refuses to render a placeholder.
    """
    tables = []
    for entry in entries:
        name, email = _split_author_entry(entry)
        tables.append(f"{{ name = {json.dumps(name)}, email = {json.dumps(email)} }}")
    return "[" + ", ".join(tables) + "]"


def _validate_author_entries(entries: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen_emails: set[str] = set()
    for raw in entries:
        entry = raw.strip()
        if not entry:
            _die("--author values must not be blank")
        match = _AUTHOR_ENTRY_RE.match(entry)
        if match is None:
            _die(
                f"--author {raw!r} must be 'Full Name <email@example.com>' "
                "(two or more capitalised words, then the author's email in "
                "angle brackets; QC FC-S18 rejects any other shape)."
            )
        name = match.group("name").strip()
        email = match.group("email").strip()
        if not _author_name_is_real(name):
            _die(
                f"--author {raw!r}: name {name!r} must be two or more "
                "capitalised words like 'Ram Lakhan'; placeholders, handles "
                "and all-caps initials fail QC FC-S18."
            )
        if not _AUTHOR_EMAIL_RE.match(email):
            _die(
                f"--author {raw!r}: email {email!r} is not a well-formed "
                "address."
            )
        if not email.lower().endswith("@ethara.ai"):
            _die(
                f"--author {raw!r}: email must be the author's ethara.ai address "
                "(QC FC-S18 fails any other domain)."
            )
        if not _author_email_is_built_from_name(name, email):
            print(
                f"[generate_bundle] WARNING: --author {raw!r}: the email local part "
                "is not built from the name words; QC FC-S18 warns so the tasker "
                "confirms this is the author.",
                file=sys.stderr,
            )
        key = email.casefold()
        if key in seen_emails:
            _die(f"--author lists {email!r} more than once")
        seen_emails.add(key)
        cleaned.append(entry)
    return cleaned


def _format_number(value: float | int) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if float(value).is_integer():
        return f"{value:.1f}"
    return repr(float(value))


def _magic_ascii_literal(magic: bytes) -> str:
    """Render 5-byte ASCII MAGIC as a Python-source b"..." literal.

    All pool entries are pure ASCII so json.dumps yields a bytes-safe
    string; we just prefix with ``b`` and swap ``"`` escaping to make the
    output valid inside Python source.
    """
    txt = magic.decode("ascii")
    escaped = txt.replace("\\", "\\\\").replace('"', '\\"')
    return f'b"{escaped}"'


def _magic_hex_bytes(magic: bytes) -> str:
    """Render 5-byte MAGIC as space-separated lowercase hex for docs."""
    return " ".join(f"{b:02x}" for b in magic)


def _derive_grammar(root: int) -> ContainerGrammar:
    """Derive the per-bundle container grammar from the root seed.

    Templates receive this as a Python literal, so test_output.py and solve.py
    consume one generated grammar instead of maintaining parallel derivations.
    """
    rng = random.Random(_derive_seed(root, "container-grammar"))
    bits = list(range(8))
    rng.shuffle(bits)
    mode_bits = sorted(bits[:2])
    wide_bit = bits[2]
    long_key_bit = bits[3]
    modes = [0, 1, 2]
    rng.shuffle(modes)
    header_items = ["version", "flags", "record_count", "base_value", "reserved"]
    rng.shuffle(header_items)
    return {
        "selector": {
            "mode_bits": mode_bits,
            "wide_bit": wide_bit,
            "long_key_bit": long_key_bit,
            "mode_ids": {"raw": modes[0], "delta": modes[1], "dict": modes[2]},
        },
        "header_order": header_items,
        "delta_encoding": rng.choice(["zigzag_uvarint", "signed_leb128"]),
        "dict_source": rng.choice(["resolved_values", "payload_values"]),
        "dict_direction": rng.choice(["forward", "backward"]),
        "crc_coverage": rng.choice(["prefix", "header_records"]),
    }


def _grammar_header_layout(grammar: ContainerGrammar) -> dict[str, int]:
    pos = 5
    layout: dict[str, int] = {}
    widths = {
        "version": 1,
        "flags": 1,
        "record_count": 2,
        "base_value": 4,
        "reserved": 3,
    }
    for name in grammar["header_order"]:
        layout[str(name)] = pos
        pos += widths[str(name)]
    return layout


def _grammar_python_literal(grammar: ContainerGrammar) -> str:
    return repr(grammar)


def _grammar_summary(grammar: ContainerGrammar) -> str:
    selector = grammar["selector"]
    return json.dumps(
        {
            "selector": selector,
            "header_order": grammar["header_order"],
            "delta_encoding": grammar["delta_encoding"],
            "dictionary": {
                "source": grammar["dict_source"],
                "direction": grammar["dict_direction"],
            },
            "crc_coverage": grammar["crc_coverage"],
        },
        sort_keys=True,
    )


def _grammar_header_table(
    grammar: ContainerGrammar, magic_hex: str, version: int
) -> str:
    layout = _grammar_header_layout(grammar)
    rows = [
        "| offset  | width   | field         | notes |",
        "|---------|---------|---------------|-------|",
        f"| 0..4    | 5 bytes | magic         | ASCII bytes `{magic_hex}`. Any other value is `bad_magic` (§7). |",
    ]
    widths = {
        "version": "u8",
        "flags": "u8",
        "record_count": "u16 LE",
        "base_value": "i32 LE",
        "reserved": "3 bytes",
    }
    notes = {
        "version": f"Must be `{version}`. Any other value is `unsupported_version` (§7).",
        "flags": "Reserved flag byte. Bit 0 has meaning; bits 1..7 must be `0`. See §6.",
        "record_count": "Number of records that follow in the body.",
        "base_value": "Signed initial value used by some record modes. See §4.",
        "reserved": "Must be `0x00 0x00 0x00`. The trailer (§8) binds these bytes when the bundle uses full-prefix CRC coverage.",
    }
    for name in grammar["header_order"]:
        start = layout[str(name)]
        width_bytes = {
            "version": 1,
            "flags": 1,
            "record_count": 2,
            "base_value": 4,
            "reserved": 3,
        }[str(name)]
        end = start + width_bytes - 1
        off = str(start) if start == end else f"{start}..{end}"
        rows.append(
            f"| {off:<7} | {widths[str(name)]:<7} | {str(name):<13} | {notes[str(name)]} |"
        )
    return "\n".join(rows)


def _grammar_selector_doc(grammar: ContainerGrammar) -> str:
    selector = grammar["selector"]
    mode_bits = selector["mode_bits"]
    mode_ids = selector["mode_ids"]
    used = sorted([*mode_bits, selector["wide_bit"], selector["long_key_bit"]])
    reserved = [str(b) for b in range(8) if b not in used]
    return "\n".join(
        [
            f"- bits `{mode_bits[0]}` and `{mode_bits[1]}` carry the payload **mode** number (`{mode_ids['raw']}` = raw, `{mode_ids['delta']}` = delta, `{mode_ids['dict']}` = dictionary). The lower listed bit contributes value 1 and the higher listed bit contributes value 2.",
            f"- bit `{selector['wide_bit']}` carries the `WIDE_VALUE` flag (raw mode only): `1` = 32-bit payload, `0` = 16-bit.",
            f"- bit `{selector['long_key_bit']}` carries the `LONG_KEY` flag: `1` = varint-length UTF-8 key, `0` = 1-byte key.",
            f"- bits `{', '.join(reserved)}` must be `0`.",
        ]
    )


def _grammar_crc_doc(grammar: ContainerGrammar) -> str:
    if grammar["crc_coverage"] == "prefix":
        return "the full file prefix before the trailer: magic, all header fields and the body"
    return "the header fields after the magic bytes, followed by the body"


def _grammar_worked_examples(grammar: ContainerGrammar) -> str:
    selector = grammar["selector"]
    mode_ids = selector["mode_ids"]
    mode_bits = selector["mode_bits"]

    def selector_byte(mode: str, wide: bool = False, long_key: bool = False) -> int:
        mode_id = mode_ids[mode]
        value = ((mode_id & 1) << mode_bits[0]) | (((mode_id >> 1) & 1) << mode_bits[1])
        if wide:
            value |= 1 << selector["wide_bit"]
        if long_key:
            value |= 1 << selector["long_key_bit"]
        return value

    if grammar["delta_encoding"] == "zigzag_uvarint":
        delta_text = "delta -3 is zigzag-uvarint byte `05`"
    else:
        delta_text = "delta -3 is signed-LEB128 byte `7d`"

    if grammar["dict_source"] == "resolved_values":
        source_text = "the prior resolved values `[11, 22, 33]`"
        selected = 11
    else:
        source_text = "the prior payload integers `[101, -4, 7]`"
        selected = 101
    payload_index = 0 if grammar["dict_direction"] == "forward" else 2
    return "\n".join(
        [
            "### Worked delta record",
            "",
            f"With a running value of `10`, {delta_text}; the resolved value becomes `7`. ",
            f"Its selector mode number is `{mode_ids['delta']}` and a short key `2a` follows selector byte `{selector_byte('delta'):02x}`.",
            "",
            "### Worked dictionary record",
            "",
            f"Given {source_text}, payload index byte `{payload_index:02x}` selects `{selected}` using {grammar['dict_direction']} indexing.",
            f"The resolved value and the next running value both become `{selected}`. Its selector mode number is `{mode_ids['dict']}`.",
        ]
    )


def _grammar_empty_hex(grammar: ContainerGrammar, magic: bytes, version: int) -> str:
    parts = {
        "version": struct.pack("<B", version),
        "flags": b"\x00",
        "record_count": struct.pack("<H", 0),
        "base_value": struct.pack("<i", 0),
        "reserved": b"\x00\x00\x00",
    }
    prefix = magic + b"".join(parts[str(name)] for name in grammar["header_order"])
    crc_payload = (
        prefix if grammar["crc_coverage"] == "prefix" else prefix[len(magic) :]
    )
    return (prefix + struct.pack("<I", zlib.crc32(crc_payload) & 0xFFFFFFFF)).hex(" ")


def _grammar_delta_doc(grammar: ContainerGrammar) -> str:
    mode_ids = grammar["selector"]["mode_ids"]
    if grammar["delta_encoding"] == "zigzag_uvarint":
        encoding = (
            "The signed delta is zig-zag mapped (`n >= 0` becomes `2n`, `n < 0` becomes "
            "`2|n| - 1`) and then written as an unsigned LEB128 varint: 7 data bits per "
            "byte, least-significant group first, high bit set on every byte except the "
            "last. For example a delta of `-3` maps to zig-zag `5`, a single byte `05`."
        )
    else:
        encoding = (
            "The signed delta is written as signed LEB128: 7 data bits per byte, "
            "least-significant group first, high bit set on every byte except the last, "
            "and the payload is sign-extended from the final byte. For example a delta of "
            "`-3` is the single byte `7d`."
        )
    return "\n".join(
        [
            f"A record whose selector mode number is `{mode_ids['delta']}` is a **delta** "
            "record. Its payload is one signed integer delta.",
            "",
            encoding,
            "",
            "The delta updates the running value described in \u00a76 (`running = running + "
            "delta`); the new running value is the record's resolved `value`. The raw "
            "delta, before it is applied, is reported as `delta_raw`.",
        ]
    )


def _grammar_dict_doc(grammar: ContainerGrammar) -> str:
    mode_ids = grammar["selector"]["mode_ids"]
    if grammar["dict_direction"] == "forward":
        index_rule = "the actual entry is `payload_index` counted from the front"
    else:
        index_rule = (
            "the actual entry is `(dictionary_length - 1) - payload_index`, i.e. counted "
            "from the back"
        )
    if grammar["dict_source"] == "resolved_values":
        source_rule = "the resolved value of every preceding record"
    else:
        source_rule = (
            "the pre-resolution payload of every preceding record (`raw_value` for raw, "
            "`delta_raw` for delta, `dict_index` for dictionary records)"
        )
    return "\n".join(
        [
            f"A record whose selector mode number is `{mode_ids['dict']}` is a "
            "**dictionary** record. Its payload is one unsigned byte, the *payload "
            "index*.",
            "",
            f"The dictionary grows as records are resolved: {source_rule} is appended to "
            "it (see \u00a76). When a dictionary record is read, "
            f"{index_rule} of the dictionary built so far. The entry found there becomes "
            "both the record's resolved `value` and the new running value; a payload "
            "index outside the current dictionary is a `truncated_record` error. The "
            "payload index exactly as written is reported as `dict_index`.",
        ]
    )


def _grammar_state_doc(grammar: ContainerGrammar) -> str:
    if grammar["dict_source"] == "resolved_values":
        appended = "the record's resolved value"
    else:
        appended = (
            "the record's pre-resolution payload (`raw_value` for raw, `delta_raw` for "
            "delta, `dict_index` for dictionary records)"
        )
    return "\n".join(
        [
            "Records are resolved left to right against a single running value and a "
            "dictionary that grows by one entry per record. The running value starts at "
            "the header `base_value`.",
            "",
            "- **raw** replaces the running value with the record's signed payload;",
            "- **delta** adds its signed delta to the running value (\u00a74);",
            "- **dictionary** replaces the running value with the selected dictionary "
            "entry (\u00a75).",
            "",
            f"Immediately after each record is resolved, {appended} is appended to the "
            "dictionary, so the Nth record (counting from zero) is read against a "
            "dictionary holding exactly N entries. The running value left behind by a "
            "record is that record's resolved `value`.",
        ]
    )


def _build_substitutions(args: argparse.Namespace) -> dict[str, str]:
    ext_bare = args.format_ext.lstrip(".")
    cat = _CATEGORIES[args.category]
    keywords_toml = _keywords_toml_array(args.keywords)
    tags_toml = _keywords_toml_array(args.tags) if args.tags else keywords_toml
    grammar = _derive_grammar(args.seed)
    magic_hex = _magic_hex_bytes(args.magic)
    eval_seed = _derive_seed(args.seed, "eval")
    shared_trailer = f"{args.format_tag.lower()}:" + hashlib.sha256(
        f"{args.archetype}:{args.format_tag}:{args.seed}".encode()
    ).hexdigest()[:16]
    return {
        # v1 placeholders (preserved for backward compatibility with instruction.md,
        # solve.py, and the environment/data/ template files).
        "{{BUNDLE_NAME}}": args.name,
        "{{BUNDLE_TITLE}}": args.title,
        "{{FORMAT_TAG}}": args.format_tag,
        "{{PACKAGE_NAME}}": args.format_tag.lower(),
        "{{FORMAT_EXT}}": ext_bare,
        "{{TASK_DESCRIPTION}}": args.description,
        "{{TASK_KEYWORDS}}": keywords_toml,
        "{{AUTHORS}}": _authors_toml_array(args.authors),
        # v2 placeholders retained for docs/README that still reference the
        # human-vs-canonical taxonomy split.
        "{{CATEGORY_CANONICAL}}": cat["canonical"],
        "{{SUBCATEGORY}}": cat["subcategory"],
        "{{CATEGORY_HUMAN}}": args.category,
        "{{SEED_HEX}}": f"{args.seed:016x}",
        "{{SAMPLE_SEED}}": str(_derive_seed(args.seed, "sample")),
        "{{CHALLENGE_SEED}}": str(_derive_seed(args.seed, "challenge")),
        "{{EVAL_SEED}}": str(eval_seed),
        "{{CLI_MAX_RECORDS_BASE}}": str(50 + (eval_seed % 451)),
        "{{CLI_RETRY_LIMIT_BASE}}": str(2 + (eval_seed % 5)),
        "{{CLI_TIMEOUT_MS_BASE}}": str(1000 + (eval_seed % 7000)),
        "{{CLI_TRAILER}}": shared_trailer,
        "{{SERVICE_ALPHA_BONUS}}": str(eval_seed % 7),
        "{{SERVICE_BETA_BONUS}}": str(eval_seed % 11),
        "{{MAGIC_ASCII}}": _magic_ascii_literal(args.magic),
        "{{MAGIC_HEX}}": magic_hex,
        "{{VERSION_NUM}}": str(args.version),
        "{{VERSION_NUM_HEX}}": f"{args.version:02x}",
        "{{GRAMMAR_PY_LITERAL}}": _grammar_python_literal(grammar),
        "{{GRAMMAR_RAW_MODE_ID}}": str(grammar["selector"]["mode_ids"]["raw"]),
        "{{GRAMMAR_SUMMARY}}": _grammar_summary(grammar),
        "{{GRAMMAR_HEADER_TABLE}}": _grammar_header_table(
            grammar, magic_hex, args.version
        ),
        "{{GRAMMAR_SELECTOR_DOC}}": _grammar_selector_doc(grammar),
        "{{GRAMMAR_CRC_DOC}}": _grammar_crc_doc(grammar),
        "{{GRAMMAR_DELTA_DOC}}": _grammar_delta_doc(grammar),
        "{{GRAMMAR_DICT_DOC}}": _grammar_dict_doc(grammar),
        "{{GRAMMAR_STATE_DOC}}": _grammar_state_doc(grammar),
        "{{GRAMMAR_WORKED_EXAMPLES}}": _grammar_worked_examples(grammar),
        "{{GRAMMAR_EMPTY_HEX}}": _grammar_empty_hex(grammar, args.magic, args.version),
        "{{CONTAINER_NOUN}}": args.container_noun,
        "{{PRODUCER_SYSTEM}}": args.producer_system,
        "{{ARCHETYPE}}": args.archetype,
        "{{ARTIFACTS}}": args.artifacts_toml,
        "{{CATEGORY}}": cat["display"],
        "{{TASK_TAGS}}": tags_toml,
        "{{ESTIMATED_DURATION_SEC}}": _format_number(args.estimated_duration_sec),
        "{{EXPERT_TIME_MIN}}": _format_number(args.expert_time_estimate_min),
        "{{EXPERT_TIME_HR}}": f"{args.expert_time_estimate_min / 60:g}",
        "{{JUNIOR_TIME_MIN}}": _format_number(args.junior_time_estimate_min),
        "{{JUNIOR_TIME_HR}}": f"{args.junior_time_estimate_min / 60:g}",
        "{{VERIFIER_TIMEOUT_SEC}}": _format_number(args.verifier_timeout_sec),
        "{{AGENT_TIMEOUT_SEC}}": _format_number(args.agent_timeout_sec),
        "{{AGENT_TIMEOUT_SEC_INT}}": str(int(args.agent_timeout_sec)),
        "{{AGENT_TIMEOUT_HR}}": f"{args.agent_timeout_sec / 3600:g}",
        "{{BUILD_TIMEOUT_SEC}}": _format_number(args.build_timeout_sec),
        "{{CPUS}}": str(args.cpus),
        "{{MEMORY_MB}}": str(args.memory_mb),
        "{{STORAGE_MB}}": str(args.storage_mb),
        "{{DOCKER_IMAGE}}": args.docker_image,
        "{{MCP_SERVERS}}": args.mcp_servers_toml,
    }


# ---------------------------------------------------------------------------
# File walking + rewriting.
# ---------------------------------------------------------------------------
def _is_text_file(path: Path) -> bool:
    if path.name == "Dockerfile":
        return True
    try:
        sample = path.read_bytes()[:8192]
    except OSError:
        return False
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _apply_substitutions(text: str, subs: dict[str, str]) -> str:
    for placeholder, value in subs.items():
        text = text.replace(placeholder, value)
    return text


def _rewrite_path(rel_path: Path, subs: dict[str, str]) -> Path:
    parts = []
    for segment in rel_path.parts:
        new = segment
        for placeholder, value in subs.items():
            new = new.replace(placeholder, value)
        parts.append(new)
    return Path(*parts) if parts else rel_path


def _discover_archetypes() -> list[str]:
    if not _TEMPLATE_ROOT.is_dir():
        return []
    return sorted(
        d.name
        for d in _TEMPLATE_ROOT.iterdir()
        if _ARCHETYPE_RE.fullmatch(d.name)
        and d.is_dir()
        and (d / _ARCHETYPE_MANIFEST).is_file()
    )


_DOMAIN_ARCHETYPE_AFFINITY: dict[str, list[str]] = {
    "software-engineering": ["repo-patch", "build-repair", "cli-config", "performance"],
    "system-admin": [
        "cli-config",
        "service-interaction",
        "build-repair",
        "data-pipeline",
    ],
    "data-science": [
        "data-pipeline",
        "domain-calculation",
        "performance",
        "format-recovery",
    ],
    "security": ["format-recovery", "repo-patch", "cli-config", "service-interaction"],
    "scientific-computing": [
        "domain-calculation",
        "performance",
        "data-pipeline",
        "format-recovery",
    ],
    "file-operations": [
        "format-recovery",
        "data-pipeline",
        "cli-config",
        "build-repair",
    ],
    "debugging": ["repo-patch", "build-repair", "performance", "format-recovery"],
    "data-processing": [
        "data-pipeline",
        "domain-calculation",
        "performance",
        "format-recovery",
    ],
    "model-training": [
        "performance",
        "data-pipeline",
        "build-repair",
        "service-interaction",
    ],
    "mathematics": [
        "domain-calculation",
        "performance",
        "format-recovery",
        "repo-patch",
    ],
    "machine-learning": [
        "performance",
        "service-interaction",
        "data-pipeline",
        "domain-calculation",
    ],
    "games": ["format-recovery", "performance", "data-pipeline", "service-interaction"],
    "video-processing": [
        "format-recovery",
        "performance",
        "data-pipeline",
        "build-repair",
    ],
    "data-querying": [
        "domain-calculation",
        "data-pipeline",
        "performance",
        "format-recovery",
    ],
    "optimization": ["performance", "domain-calculation", "repo-patch", "cli-config"],
    "personal-assistant": [
        "cli-config",
        "service-interaction",
        "data-pipeline",
        "format-recovery",
    ],
}


def _select_archetype(category: str, seed: int, mode: str) -> str:
    """Pick an archetype when the caller did not name one explicitly.

    "auto" restricts the pick to archetypes that suit the category (per
    _DOMAIN_ARCHETYPE_AFFINITY); "random" picks from every discovered
    archetype.  Either way the choice is seeded, so a given seed+category is
    reproducible while varying the seed varies the archetype -- which keeps a
    batch of bundles from all being the same shape.  A dedicated derived rng
    is used so the content rng draw order (and reproducibility) is untouched.
    """
    discovered = _discover_archetypes()
    if not discovered:
        return _DEFAULT_ARCHETYPE
    if mode == _ARCHETYPE_RANDOM:
        pool = discovered
    else:
        affinity = _DOMAIN_ARCHETYPE_AFFINITY.get(category, discovered)
        pool = [a for a in affinity if a in discovered] or discovered
    picker = random.Random(_derive_seed(seed, f"archetype:{category}"))
    return picker.choice(sorted(pool))


def _archetype_dir(archetype: str) -> Path:
    if not _ARCHETYPE_RE.fullmatch(archetype):
        _die(f"invalid archetype name {archetype!r}")
    root = _TEMPLATE_ROOT.resolve()
    candidate = (_TEMPLATE_ROOT / archetype).resolve()
    if candidate.parent != root:
        _die(f"archetype {archetype!r} escapes the templates directory")
    return candidate


def _load_archetype_manifest(archetype: str) -> ArchetypeManifest:
    manifest = _archetype_dir(archetype) / _ARCHETYPE_MANIFEST
    if not manifest.is_file():
        _die(f"archetype '{archetype}' has no {_ARCHETYPE_MANIFEST} at {manifest}")
    try:
        with manifest.open("rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        _die(f"{manifest} is not valid TOML: {exc}")

    name = data.get("name")
    summary = data.get("summary")
    artifacts = data.get("artifacts")
    if not isinstance(name, str) or not name:
        _die(f"{manifest}: name must be a non-empty string")
    if name != archetype:
        _die(f"{manifest}: name must equal archetype directory {archetype!r}")
    if not isinstance(summary, str) or not summary:
        _die(f"{manifest}: summary must be a non-empty string")
    if not isinstance(artifacts, list) or not all(
        isinstance(item, str) for item in artifacts
    ):
        _die(f"{manifest}: artifacts must be a list of strings")
    default_description = data.get("default_description")
    if not isinstance(default_description, str) or not default_description.strip():
        _die(f"{manifest}: default_description must be a non-empty string")
    default_keywords = data.get("default_keywords")
    if (
        not isinstance(default_keywords, list)
        or not default_keywords
        or not all(isinstance(item, str) for item in default_keywords)
    ):
        _die(f"{manifest}: default_keywords must be a non-empty list of strings")
    source_archives = data.get("source_archives")
    if source_archives is not None and (
        not isinstance(source_archives, list)
        or not all(
            isinstance(item, dict)
            and isinstance(item.get("source"), str)
            and isinstance(item.get("output"), str)
            for item in source_archives
        )
    ):
        _die(f"{manifest}: source_archives must contain source/output strings")
    dependencies = data.get("dependencies", {})
    if not isinstance(dependencies, dict) or not all(
        isinstance(k, str) and isinstance(v, list) and all(isinstance(i, str) for i in v)
        for k, v in dependencies.items()
    ):
        _die(f"{manifest}: [dependencies] must map an input file to a list of input files")
    raw_inputs = data.get("inputs", _DEFAULT_INPUTS)
    if not isinstance(raw_inputs, list) or not raw_inputs:
        _die(f"{manifest}: [[inputs]] must list at least one input directory")
    inputs: list[InputDir] = []
    for item in raw_inputs:
        if not isinstance(item, dict) or set(item) != {"dir", "mount"}:
            _die(f"{manifest}: every [[inputs]] entry has exactly the keys dir and mount: {item!r}")
        name, mount = item["dir"], item["mount"]
        if not isinstance(name, str) or not _INPUT_DIR_RE.match(name) or name == "Dockerfile":
            _die(f"{manifest}: input dir {name!r} must be a plain directory name under environment/")
        if not isinstance(mount, str) or not mount.startswith("/") or mount.rstrip("/") in {"", "/app"}:
            _die(f"{manifest}: input {name!r} mount {mount!r} must be an absolute path below /")
        if name in {i["dir"] for i in inputs} or mount in {i["mount"] for i in inputs}:
            _die(f"{manifest}: input {name!r} or mount {mount!r} declared twice")
        inputs.append({"dir": name, "mount": mount.rstrip("/")})
    datagen_input = data.get("datagen_input", inputs[0]["dir"])
    if datagen_input not in {i["dir"] for i in inputs}:
        _die(f"{manifest}: datagen_input {datagen_input!r} is not a declared [[inputs]] dir")
    post_generate = data.get("post_generate")
    if post_generate is not None and (
        not isinstance(post_generate, list)
        or not post_generate
        or not all(isinstance(item, str) and item for item in post_generate)
    ):
        _die(f"{manifest}: post_generate must be a non-empty list of strings")
    # ``supports_cheat`` was accepted by earlier revisions of this tool but
    # the cheat/ overlay has been retired.  Silently ignore any leftover key
    # so that older archetype.toml files continue to parse; the value is
    # discarded and has no effect on the emitted bundle.
    result: ArchetypeManifest = {
        "name": name,
        "summary": summary,
        "artifacts": artifacts,
        "default_description": default_description,
        "default_keywords": default_keywords,
        "dependencies": dependencies,
        "inputs": inputs,
        "datagen_input": datagen_input,
    }
    if source_archives is not None:
        result["source_archives"] = source_archives
    if post_generate is not None:
        result["post_generate"] = post_generate
    return result


def _safe_relative_path(raw: str, label: str) -> Path:
    if "\\" in raw or "\x00" in raw:
        _die(f"{label} contains an unsafe character: {raw!r}")
    path = Path(raw)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        _die(f"{label} must be a relative path inside the archetype: {raw!r}")
    return path


def _write_source_archive(
    template_dir: Path,
    target: Path,
    archive: SourceArchive,
    subs: dict[str, str],
) -> None:
    source_rel = _safe_relative_path(archive["source"], "source archive input")
    source = (template_dir / source_rel).resolve()
    if not source.is_relative_to(template_dir) or not source.is_dir():
        _die(f"source archive input is missing or escapes its archetype: {source_rel}")
    output_rel = _rewrite_path(
        _safe_relative_path(archive["output"], "source archive output"), subs
    )
    output = (target / output_rel).resolve()
    if not output.is_relative_to(target):
        _die(f"source archive output escapes the bundle: {output_rel}")
    output.parent.mkdir(parents=True, exist_ok=True)
    members = sorted(source.rglob("*"))
    symlinks = [path for path in members if path.is_symlink()]
    if symlinks:
        shown = ", ".join(str(path.relative_to(source)) for path in symlinks[:5])
        _die(f"source archive input contains symlinks: {shown}")
    seen_names: set[tuple[str, ...]] = set()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as zf:
        for src in (path for path in members if path.is_file()):
            resolved = src.resolve()
            if not resolved.is_relative_to(source):
                _die(f"source archive member escapes its source root: {src}")
            rel = _rewrite_path(src.relative_to(source), subs)
            if rel.is_absolute() or ".." in rel.parts:
                _die(f"rewritten source archive member is unsafe: {rel}")
            member_name = rel.as_posix()
            collision_key = tuple(part.casefold() for part in rel.parts)
            if collision_key in seen_names:
                _die(
                    f"duplicate source archive member after substitution: {member_name}"
                )
            if any(
                collision_key == existing[: len(collision_key)]
                or existing == collision_key[: len(existing)]
                for existing in seen_names
            ):
                _die(
                    "source archive file/directory prefix collision after "
                    f"substitution: {member_name}"
                )
            seen_names.add(collision_key)
            info = zipfile.ZipInfo(rel.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o100644 << 16
            if _is_text_file(src):
                payload = _apply_substitutions(
                    src.read_text(encoding="utf-8"), subs
                ).encode()
            else:
                payload = src.read_bytes()
            zf.writestr(info, payload)


def _run_post_generate(target: Path, command: list[str]) -> None:
    script_rel = _safe_relative_path(command[0], "post_generate script")
    script = (target / script_rel).resolve()
    if not script.is_relative_to(target) or not script.is_file():
        _die(f"post_generate script is missing or escapes the bundle: {script_rel}")
    try:
        subprocess.run(
            [sys.executable, str(script), *command[1:]],
            cwd=target,
            check=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _die(f"post_generate command failed: {exc}")


def _walk_templates(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fname in filenames:
            if fname in _SKIP_FILE_NAMES:
                continue
            if any(fname.endswith(suf) for suf in _SKIP_FILE_SUFFIXES):
                continue
            yield Path(dirpath, fname)


def _ensure_exec(path: Path) -> None:
    if not path.exists():
        return
    st = path.stat()
    path.chmod(st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _preserve_exec(src: Path, dst: Path) -> None:
    src_st = src.stat()
    if src_st.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
        _ensure_exec(dst)


# ---------------------------------------------------------------------------
# Argument resolution: fills in every auto-generatable arg from the seed
# and category before validation and substitution.
# ---------------------------------------------------------------------------
def _resolve_args(args: argparse.Namespace) -> argparse.Namespace:
    # 1. Seed.  If unset, draw a fresh one and print it so runs are
    #    reproducible.
    if args.seed is None:
        args.seed = _pick_seed()
        print(f"[generate_bundle] seed={args.seed} (auto)")
    rng = _seeded_random(args.seed)

    # 2. Category.  If --random is set, pick one; else default to
    #    software-engineering.
    if args.random or args.category is None:
        args.category = rng.choice(sorted(_CATEGORIES.keys()))
    if args.category not in _CATEGORIES:
        _die(f"--category '{args.category}' not in {sorted(_CATEGORIES)}")

    # 2b. Archetype selection.  The default "auto" picks a domain-appropriate
    #     archetype at random (seeded) so bundles vary in shape instead of
    #     always being one type; "random" ignores the affinity; an explicit
    #     name is honoured as-is.
    requested_archetype = args.archetype
    if args.archetype in (_ARCHETYPE_AUTO, _ARCHETYPE_RANDOM):
        args.archetype = _select_archetype(args.category, args.seed, args.archetype)
    args.archetype_auto = requested_archetype in (_ARCHETYPE_AUTO, _ARCHETYPE_RANDOM)
    manifest = _load_archetype_manifest(args.archetype)

    raw_authors = list(args.authors) if args.authors else []
    if not raw_authors:
        _die(
            "--author is required: QC FC-S18 fails an empty [task].authors. "
            "Pass --author 'Full Name <name@ethara.ai>'."
        )
    args.authors = _validate_author_entries(raw_authors)

    # 3. Every other identifying arg is auto-generated if missing.
    #    Order matters: --format-tag, --format-ext, --name, --title,
    #    --description, --keywords all consume from the RNG so the same
    #    seed always produces the same output.
    is_format_recovery = args.archetype == _DEFAULT_ARCHETYPE
    if is_format_recovery:
        if args.format_tag is None:
            args.format_tag = _auto_format_tag(rng, args.category)
        if args.format_ext is None:
            args.format_ext = _auto_format_ext(rng, args.category)
    else:
        args.format_tag = "TASK"
        args.format_ext = ".dat"
    if args.name is None:
        # Consume the historical fallback draws so later seed-derived fields
        # remain reproducible, but name the directory from the actual task
        # subject (the explicit title or selected archetype).
        _auto_name(rng, args.category, args.seed)
        stem = _slugify(args.title) if args.title else args.archetype
        args.name = _numbered_name(stem, args.out)
    if args.title is None:
        args.title = _auto_title(args.name)
    description_from_cli = args.description is not None
    keywords_from_cli = args.keywords is not None
    if args.description is None:
        args.description = manifest["default_description"]
    if args.keywords is None:
        args.keywords = ",".join(manifest["default_keywords"])

    # 4. Derived format parameters (never CLI-visible).
    if is_format_recovery:
        # format-recovery previously fell back to generated description and
        # keywords because its manifest lacked defaults.  Consume those legacy
        # draws when the corresponding CLI values are absent so fixed-seed
        # format-recovery grammar fields keep their historical RNG positions.
        if not description_from_cli:
            rng.choice(_CATEGORIES[args.category]["verb_pool"])
            rng.choice(_CATEGORIES[args.category]["noun_pool"])
        if not keywords_from_cli:
            pool = list(_CATEGORIES[args.category]["keyword_pool"])
            rng.shuffle(pool)
        args.magic = _auto_magic(rng, args.category)
        args.version = _auto_version(rng)
        args.container_noun = _auto_container_noun(rng, args.category)
        args.producer_system = _auto_producer(rng, args.category)
    else:
        args.magic = b""
        args.version = 0
        args.container_noun = ""
        args.producer_system = ""

    # 5. Slim task.toml defaults shared by the current archetypes; per-task
    #    overrides come in through CLI flags.
    if args.docker_image is None:
        args.docker_image = f"terminal-bench/{args.name}:latest"
    else:
        print(
            "[generate_bundle] WARNING: --docker-image is a compatibility "
            "no-op; the slim task.toml schema does not emit it",
            file=sys.stderr,
        )
    if args.tags is None:
        args.tags = args.keywords
    args.archetype_manifest = manifest
    args.artifacts_toml = json.dumps(manifest["artifacts"])
    args.mcp_servers_toml = "[]"
    if args.estimated_duration_sec is None:
        args.estimated_duration_sec = 7200.0
    if args.expert_time_estimate_min is None:
        args.expert_time_estimate_min = 480.0
    if args.junior_time_estimate_min is None:
        args.junior_time_estimate_min = 1440.0
    if args.verifier_timeout_sec is None:
        args.verifier_timeout_sec = 2700.0
    if args.agent_timeout_sec is None:
        args.agent_timeout_sec = 7200.0
    if args.build_timeout_sec is None:
        args.build_timeout_sec = 900.0
    if args.cpus is None:
        args.cpus = 2
    if args.memory_mb is None:
        args.memory_mb = 4096
    if args.storage_mb is None:
        args.storage_mb = 10240

    return args


def _validate_args(args: argparse.Namespace) -> None:
    if not _NAME_RE.match(args.name):
        _die(f"--name '{args.name}' violates {_NAME_RE.pattern}")
    if args.archetype == _DEFAULT_ARCHETYPE:
        if not _TAG_RE.match(args.format_tag):
            _die(f"--format-tag '{args.format_tag}' violates {_TAG_RE.pattern}")
        if not _EXT_RE.match(args.format_ext):
            _die(f"--format-ext '{args.format_ext}' violates {_EXT_RE.pattern}")
        if len(args.magic) != 5:
            _die(f"MAGIC bytes must be length 5, got {len(args.magic)}")
    if not args.title.strip():
        _die("--title cannot be blank")
    if not args.description.strip():
        _die("--description cannot be blank")
    if not args.keywords.strip():
        _die("--keywords cannot be blank")


# ---------------------------------------------------------------------------
# TRUTH.md second pass.
#
# TRUTH.md is the author/verifier-side golden-trajectory document: it names the
# planted defects, the load-bearing deliverables, the grading contract, the root
# cause, the reference solution shape, the recommended agent trajectory, the
# pitfalls, and the provenance of the instance.  Every generated bundle carries
# one at solution/TRUTH.md, next to the oracle it describes, exactly as the
# hand-authored reference bundles do.
#
# The narrative lives in ``templates/<archetype>/solution/TRUTH.md`` and is
# filled by the ordinary first-pass substitution table.  A handful of facts,
# however, are only
# knowable *after* the bundle tree exists on disk -- the sha256 of the emitted
# solution/solve.sh, the Channel A weight totals, the rubric shape, the declared
# artifact list.  Those are resolved here, in a second pass, from the generated
# files themselves so TRUTH.md can never drift from the bundle it describes.
# ---------------------------------------------------------------------------
_TRUTH_FILENAME = "TRUTH.md"
_TRUTH_TOKEN_RE = re.compile(r"\{\{[A-Z0-9_]+\}\}")

_LOCKED_WEIGHTS = frozenset({5, 3, 1, -1, -3, -5})
_ANNOTATION_KEYS = ["mode", "type", "evaluation_target", "importance"]
_JUDGE_HEADER = {
    "judge": "openai/gpt-5.6-sol",
    "mode": "batched",
    "timeout": 300,
    "atif-trajectory": "/logs/agent/trajectory.json",
    "weight": 1.0,
}


def _check_channel_weights(label: str, weights: dict[str, int]) -> None:
    bad = {n: w for n, w in weights.items() if type(w) is not int or w not in _LOCKED_WEIGHTS}
    if bad:
        _die(f"{label}: weights off the locked {{5,3,1,-1,-3,-5}} scale: {bad}")
    positive = sum(w for w in weights.values() if w > 0)
    negative = -sum(w for w in weights.values() if w < 0)
    if positive <= 0 or negative <= 0:
        _die(f"{label}: needs at least one positive and one negative weight")
    if negative > positive:
        _die(f"{label}: sum |negative| {negative} exceeds sum positive {positive}")


def _judge_criteria(target: Path) -> list[dict[str, Any]]:
    """Load tests/judge.toml and fail scaffold if its header or weights drift."""
    path = target / "tests" / "judge.toml"
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        _die(f"tests/judge.toml could not be read: {exc}")
    header = raw.get("judge") or {}
    drift = {k: header.get(k) for k, v in _JUDGE_HEADER.items() if header.get(k) != v}
    drift.update({k: header[k] for k in header if k not in _JUDGE_HEADER})
    if list(header) != list(_JUDGE_HEADER):
        drift["key order"] = list(header)
    if drift:
        _die(f"tests/judge.toml [judge] drifts from the pinned header: {drift}")
    criteria = raw.get("criterion") or []
    if len(criteria) < 8:
        _die(f"tests/judge.toml carries {len(criteria)} criteria; QC requires at least 8")
    for c in criteria:
        keys = list((c.get("annotations") or {}).keys())
        if keys != _ANNOTATION_KEYS:
            _die(
                f"tests/judge.toml {c.get('id')} [criterion.annotations] keys must be exactly "
                f"{_ANNOTATION_KEYS} (type holds the category; QC J6), got {keys}"
            )
    _check_channel_weights(
        "tests/judge.toml", {str(c.get("id")): c.get("weight") for c in criteria}
    )
    return criteria


def _test_registrations(target: Path) -> dict[str, int]:
    """Read the criteria.<name>(weight=W) registrations from tests/test_output.py."""
    path = target / "tests" / "test_output.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    weights: dict[str, int] = {}
    for node in tree.body:
        call = node.value if isinstance(node, ast.Expr) else None
        if (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "criteria"
        ):
            for kw in call.keywords:
                if kw.arg == "weight":
                    weights[call.func.attr] = ast.literal_eval(kw.value)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "criterion":
            for kw in node.keywords:
                text = kw.value.value if isinstance(kw.value, ast.Constant) else ""
                text = text if isinstance(text, str) else ""
                if kw.arg == "description" and ("{" in text or "}" in text):
                    _die(
                        f"tests/test_output.py line {node.lineno}: rewardkit runs "
                        "str.format on @criterion descriptions, so a brace aborts "
                        "the verifier; reword the description without braces"
                    )
    if not weights:
        _die("tests/test_output.py registers no criteria.<name>(weight=W)")
    _check_channel_weights("tests/test_output.py", weights)
    return weights


_SHIPPED_DATA_TOKEN = "{{SHIPPED_DATA}}"


_SHIPPED_DIR_TOKEN = re.compile(r"\{\{SHIPPED:([A-Za-z0-9._-]+)\}\}")


def _shipped_blobs(directory: Path) -> str:
    blobs = {
        path.relative_to(directory).as_posix(): base64.b64encode(
            zlib.compress(path.read_bytes(), 9)
        ).decode("ascii")
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }
    return json.dumps(blobs, indent=4)


def _embed_shipped_data(target: Path, manifest: ArchetypeManifest) -> None:
    """Inline the agent's input directories into test_output.py.

    The verifier is a separate container built from tests/ alone, so no input
    directory exists at grade time. ``{{SHIPPED_DATA}}`` becomes the archetype's
    primary input (its ``datagen_input``) and ``{{SHIPPED:<dir>}}`` becomes the
    named input directory, each a {relative path: base64(zlib(bytes))} map.
    """
    tests_py = target / "tests" / "test_output.py"
    text = tests_py.read_text(encoding="utf-8")
    env = target / "environment"
    declared = {item["dir"] for item in manifest["inputs"]}
    if _SHIPPED_DATA_TOKEN in text:
        text = text.replace(_SHIPPED_DATA_TOKEN, _shipped_blobs(env / manifest["datagen_input"]))
    for name in sorted(set(_SHIPPED_DIR_TOKEN.findall(text))):
        if name not in declared:
            _die(f"tests/test_output.py embeds {{{{SHIPPED:{name}}}}} but {name!r} is not a declared input")
        text = text.replace(f"{{{{SHIPPED:{name}}}}}", _shipped_blobs(env / name))
    tests_py.write_text(text, encoding="utf-8", newline="\n")


def _dockerfile_copies(dockerfile: Path) -> dict[str, str]:
    """Input directory -> image path, for every COPY/ADD of a build-context dir."""
    found: dict[str, str] = {}
    workdir = "/"
    for raw in dockerfile.read_text(encoding="utf-8").splitlines():
        head = raw.strip().split(None, 1)
        if len(head) < 2:
            continue
        if head[0].upper() == "WORKDIR":
            workdir = head[1].strip()
        if head[0].upper() not in {"COPY", "ADD"} or "--from" in head[1]:
            continue
        args = [a for a in head[1].split() if not a.startswith("--")]
        if len(args) != 2:
            continue
        src, dest = args[0].strip("./"), args[1]
        if not dest.startswith("/"):
            dest = workdir.rstrip("/") + "/" + dest
        found[src] = dest.rstrip("/")
    return found


def _check_input_layout(target: Path, manifest: ArchetypeManifest) -> None:
    """environment/ holds the Dockerfile and exactly the declared input dirs (QC S3/S4)."""
    env = target / "environment"
    declared = {item["dir"]: item["mount"] for item in manifest["inputs"]}
    present = {p.name for p in env.iterdir()}
    extra = sorted(present - set(declared) - {"Dockerfile"})
    missing = sorted(set(declared) - present)
    if extra or missing:
        _die(f"environment/ must hold Dockerfile + declared inputs {sorted(declared)}; "
             f"extra {extra}, missing {missing}")
    copies = _dockerfile_copies(env / "Dockerfile")
    for name, mount in declared.items():
        if not any(p.is_file() for p in (env / name).rglob("*")):
            _die(f"input directory environment/{name}/ is empty")
        if copies.get(name) != mount:
            _die(f"environment/Dockerfile must `COPY {name} {mount}` (found {copies.get(name)!r})")


def _write_reward_toml(target: Path) -> None:
    """Emit tests/reward.toml: each channel counts 0.5 / its positive total."""
    test_pos = sum(w for w in _test_registrations(target).values() if w > 0)
    judge_pos = sum(
        int(c["weight"]) for c in _judge_criteria(target) if int(c["weight"]) > 0
    )
    (target / "tests" / "reward.toml").write_text(
        "[[reward]]\n"
        'name = "reward"\n'
        'aggregation = "weighted-sum"\n'
        f"weights = {{ test_output = {0.5 / test_pos!r}, judge = {0.5 / judge_pos!r} }}\n"
        "\n"
        "[scoring.test_output]\n"
        'aggregation = "weighted-sum"\n',
        encoding="utf-8",
        newline="\n",
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _die(f"TRUTH.md second pass could not read {label} ({path.name}): {exc}")


def _truth_bullets(lines: list[str]) -> str:
    """Join bullet lines, or emit an explicit 'none' bullet.

    Never returns an empty string: an empty substitution would leave a dangling
    section in TRUTH.md that reads as a generator bug.
    """
    return "\n".join(lines) if lines else "- (none declared by this archetype)"


def _truth_weight_facts(target: Path) -> dict[str, str]:
    weights = _test_registrations(target)

    positives = {n: w for n, w in weights.items() if w > 0}
    negatives = {n: w for n, w in weights.items() if w < 0}
    positive_total = sum(positives.values())
    negative_total = sum(negatives.values())
    floor = max(-1.0, negative_total / positive_total)
    positive_lines = [f"- `{n}` (weight {w})" for n, w in positives.items()]
    negative_lines = [f"- `{n}` (weight {w})" for n, w in negatives.items()]

    return {
        "{{TRUTH_POSITIVE_COUNT}}": str(len(positives)),
        "{{TRUTH_NEGATIVE_COUNT}}": str(len(negatives)),
        "{{TRUTH_TEST_COUNT}}": str(len(weights)),
        "{{TRUTH_POSITIVE_TOTAL}}": str(positive_total),
        "{{TRUTH_NEGATIVE_TOTAL}}": str(negative_total),
        "{{TRUTH_REWARD_FLOOR}}": f"{floor:.3f}",
        "{{TRUTH_REWARD_RANGE}}": (
            f"{negative_total}/{positive_total} = {floor:.3f} to +1.000"
        ),
        "{{TRUTH_CHANNEL_A_SUMMARY}}": (
            f"{len(positives)} positive and {len(negatives)} negative tests"
        ),
        "{{TRUTH_POSITIVE_TEST_LIST}}": _truth_bullets(positive_lines),
        "{{TRUTH_NEGATIVE_TEST_LIST}}": _truth_bullets(negative_lines),
    }


def _truth_rubric_facts(target: Path) -> dict[str, str]:
    criteria = _judge_criteria(target)
    lines: list[str] = []
    weights = [int(c["weight"]) for c in criteria]
    positive_total = sum(w for w in weights if w > 0)
    negative_total = sum(w for w in weights if w < 0)
    positive = sum(1 for w in weights if w > 0)
    negative = len(weights) - positive
    for c, w in zip(criteria, weights):
        target_field = (c.get("annotations") or {}).get("evaluation_target", "trajectory")
        lines.append(f"- **{c['id']}** ({w:+d}, {target_field}): {str(c['description']).strip()}")

    return {
        "{{TRUTH_RUBRIC_COUNT}}": str(len(criteria)),
        "{{TRUTH_RUBRIC_POSITIVE_COUNT}}": str(positive),
        "{{TRUTH_RUBRIC_NEGATIVE_COUNT}}": str(negative),
        "{{TRUTH_RUBRIC_POSITIVE_TOTAL}}": str(positive_total),
        "{{TRUTH_RUBRIC_NEGATIVE_TOTAL}}": str(negative_total),
        "{{TRUTH_RUBRIC_SUMMARY}}": (
            f"{len(criteria)} criteria ({positive} positive / {negative} negative), "
            f"positive total {positive_total}"
        ),
        "{{TRUTH_RUBRIC_LIST}}": _truth_bullets(lines),
    }


def _truth_bundle_facts(target: Path, manifest: ArchetypeManifest) -> dict[str, str]:
    solve_sh = target / "solution" / "solve.sh"
    solve_py = target / "solution" / "solve.py"
    if not solve_sh.is_file() or not solve_py.is_file():
        _die("TRUTH.md second pass requires solution/solve.sh and solution/solve.py")

    task_toml = target / "task.toml"
    try:
        declared = tomllib.loads(task_toml.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        _die(f"TRUTH.md second pass could not read task.toml: {exc}")
    artifacts = [str(item) for item in declared.get("artifacts", [])]
    if not artifacts:
        _die("task.toml declares no artifacts for TRUTH.md to describe")
    artifact_lines = [f"- `{item}`" for item in artifacts]

    data_files: list[str] = []
    for item in manifest["inputs"]:
        input_dir = target / "environment" / item["dir"]
        if input_dir.is_dir():
            data_files += sorted(
                f"{item['mount']}/{path.relative_to(input_dir).as_posix()}"
                for path in input_dir.rglob("*")
                if path.is_file()
            )
    data_lines = [f"- `{item}`" for item in data_files]

    return {
        "{{TRUTH_SOLVE_SH_SHA256}}": _sha256_file(solve_sh),
        "{{TRUTH_SOLVE_PY_SHA256}}": _sha256_file(solve_py),
        "{{TRUTH_SOLVE_PY_LINES}}": str(
            len(solve_py.read_text(encoding="utf-8").splitlines())
        ),
        "{{TRUTH_ARTIFACT_COUNT}}": str(len(artifacts)),
        "{{TRUTH_ARTIFACT_LIST}}": _truth_bullets(artifact_lines),
        "{{TRUTH_DATA_FILE_COUNT}}": str(len(data_files)),
        "{{TRUTH_DATA_FILE_LIST}}": _truth_bullets(data_lines),
    }


def _truth_folded(prose: str) -> str:
    # break_on_hyphens=False keeps "polarity-inverted" intact; a YAML folded
    # scalar joins wrapped lines with a space, which would otherwise produce
    # "polarity- inverted" in the rendered value.
    return textwrap.fill(
        prose,
        width=76,
        initial_indent="  ",
        subsequent_indent="  ",
        break_on_hyphens=False,
    )


def _truth_provenance_block(
    args: argparse.Namespace, facts: dict[str, str]
) -> dict[str, str]:
    verified_by = (
        "Not yet measured. The expected figures are exactly 1.000 on each of "
        "five oracle runs and exactly 0.000 on a no-op run, on the test channel "
        "in tests/test_output.py only; the judged channel has no oracle score."
    )
    caveat = (
        f"The test channel carries {facts['{{TRUTH_POSITIVE_COUNT}}']} positive "
        f"checks worth {facts['{{TRUTH_POSITIVE_TOTAL}}']} weight and "
        f"{facts['{{TRUTH_NEGATIVE_COUNT}}']} negative checks worth "
        f"{facts['{{TRUTH_NEGATIVE_TOTAL}}']} weight, so on its own it ranges "
        f"{facts['{{TRUTH_REWARD_RANGE}}']}. The judged channel carries "
        f"{facts['{{TRUTH_RUBRIC_COUNT}}']} criteria worth "
        f"{facts['{{TRUTH_RUBRIC_POSITIVE_TOTAL}}']} positive points. "
        "tests/reward.toml divides each channel's weighted sum by its positive "
        "total and gives each half of the reward, so the combined reward runs "
        "from -1.000 to +1.000 with no clamp."
    )
    lines = [
        "```yaml",
        "uuid: null  # task.toml carries no canary_guid or uuid field",
        f"instance_id: {args.name}",
        f"task_name: terminal-bench/{args.name}",
        f"fix_patch_sha256: {facts['{{TRUTH_SOLVE_SH_SHA256}}']}"
        "  # sha256 of solution/solve.sh",
        f"solve_py_sha256: {facts['{{TRUTH_SOLVE_PY_SHA256}}']}"
        f"  # informational; solve.py is {facts['{{TRUTH_SOLVE_PY_LINES}}']} lines",
        "language: python",
        "golden_score_measured: null  # not measured for this instance",
        "golden_score_channel_a_pct: null",
        "golden_score_channel_b_pct: null",
        "golden_score_runs: 0",
        "golden_score_trial_id: null  # no calibration trial has been run yet",
        "golden_score_verified_by: >",
        _truth_folded(verified_by),
        "caveat: >",
        _truth_folded(caveat),
        "```",
    ]
    return {"{{TRUTH_PROVENANCE_BLOCK}}": "\n".join(lines)}


def _write_truth_md(target: Path, args: argparse.Namespace) -> None:
    """Resolve the second-pass ``{{TRUTH_*}}`` tokens in the emitted TRUTH.md."""
    truth = target / "solution" / _TRUTH_FILENAME
    if not truth.is_file():
        _die(
            f"archetype '{args.archetype}' does not ship a {_TRUTH_FILENAME} template; "
            f"every bundle must carry one at templates/{args.archetype}/solution/"
            f"{_TRUTH_FILENAME}"
        )

    facts: dict[str, str] = {}
    facts.update(_truth_weight_facts(target))
    facts.update(_truth_rubric_facts(target))
    facts.update(_truth_bundle_facts(target, args.archetype_manifest))
    facts.update(_truth_provenance_block(args, facts))

    text = _apply_substitutions(truth.read_text(encoding="utf-8"), facts)
    leftover = sorted(set(_TRUTH_TOKEN_RE.findall(text)))
    if leftover:
        _die(
            f"{_TRUTH_FILENAME} still carries unresolved tokens after the second "
            f"pass: {', '.join(leftover)}"
        )
    if not text.endswith("\n"):
        text += "\n"
    truth.write_text(text, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Main scaffold path.  Kept small so callers can import scaffold_bundle().
# ---------------------------------------------------------------------------
def scaffold_bundle(args: argparse.Namespace) -> Path:
    args = _resolve_args(args)
    _validate_args(args)

    template_dir = _archetype_dir(args.archetype)
    if not template_dir.is_dir():
        known = ", ".join(_discover_archetypes()) or "<none>"
        _die(f"unknown archetype '{args.archetype}'; available: {known}")

    subs = _build_substitutions(args)

    out_root = Path(args.out).expanduser().resolve()
    if not out_root.is_dir():
        _die(f"--out '{out_root}' is not an existing directory")

    target = out_root / args.name
    if target.exists():
        if not args.force:
            _die(
                f"target '{target}' already exists; use --force to overwrite",
                code=1,
            )
        shutil.rmtree(target)

    target.mkdir(parents=True)

    source_archives = args.archetype_manifest.get("source_archives", [])
    archive_sources = {
        _safe_relative_path(item["source"], "source archive input")
        for item in source_archives
    }
    archive_outputs = [
        _rewrite_path(
            _safe_relative_path(item["output"], "source archive output"), subs
        )
        for item in source_archives
    ]
    emitted_paths: list[tuple[str, ...]] = []

    def register_output(path: Path) -> None:
        if path.is_absolute() or ".." in path.parts:
            _die(f"template output path is unsafe after substitution: {path}")
        key = tuple(part.casefold() for part in path.parts)
        for existing in emitted_paths:
            if key == existing[: len(key)] or existing == key[: len(existing)]:
                _die(f"template output path collides with another output: {path}")
        emitted_paths.append(key)

    for archive_output in archive_outputs:
        register_output(archive_output)
    for src in _walk_templates(template_dir):
        rel = src.relative_to(template_dir)
        if rel.parts[0] == "cheat":
            continue
        if any(rel == source or source in rel.parents for source in archive_sources):
            continue
        rel_out = _rewrite_path(rel, subs)
        register_output(rel_out)
        dst = target / rel_out
        dst.parent.mkdir(parents=True, exist_ok=True)

        if _is_text_file(src):
            text = src.read_text(encoding="utf-8")
            # newline="\n" is load-bearing: write_text() defaults to
            # newline=None, which translates "\n" to os.linesep (CRLF on
            # Windows).  CRLF in tests/test.sh breaks bash, and the bundle
            # then scores nothing regardless of agent quality.
            dst.write_text(
                _apply_substitutions(text, subs), encoding="utf-8", newline="\n"
            )
        else:
            shutil.copy2(src, dst)

        _preserve_exec(src, dst)

    _run_datagen(template_dir, target, args, subs)

    for archive in source_archives:
        _write_source_archive(template_dir, target, archive, subs)

    post_generate = args.archetype_manifest.get("post_generate")
    if post_generate:
        _run_post_generate(target, post_generate)

    _ensure_exec(target / "solution" / "solve.sh")
    _ensure_exec(target / "tests" / "test.sh")

    _check_input_layout(target, args.archetype_manifest)
    _embed_shipped_data(target, args.archetype_manifest)
    _write_reward_toml(target)
    _write_truth_md(target, args)

    return target


def _run_datagen(
    template_dir: Path, target: Path, args: argparse.Namespace, subs: dict[str, str]
) -> None:
    """Run the archetype's datagen.py, which writes the seeded input files.

    datagen may add entries to ``subs``; source archives are rendered afterwards,
    so archived sources can use values the data generator chose.
    """
    script = template_dir / _DATAGEN
    if not script.is_file():
        return
    namespace: dict[str, Any] = {"__name__": f"datagen_{args.archetype.replace('-', '_')}"}
    exec(compile(script.read_text(encoding="utf-8"), str(script), "exec"), namespace)
    generate = namespace.get("generate")
    if not callable(generate):
        _die(f"{script} must define generate(data_dir, seed, subs)")
    data_dir = target / "environment" / args.archetype_manifest["datagen_input"]
    data_dir.mkdir(parents=True, exist_ok=True)
    generate(data_dir, _derive_seed(args.seed, "data"), subs)


def _positive_int(raw: str) -> int:
    value = int(raw)
    if value <= 0:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {raw!r}")
    return value


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="generate_bundle.py",
        description=(
            "Scaffold a Harbor input bundle from templates/. "
            "In v2 every identifying argument except --out is optional; the "
            "generator will auto-synthesize a unique random task if omitted."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--out",
        required=True,
        help="Directory to scaffold into.  The bundle is created at "
        "<out>/<name>/.  Typically points at harness/Tasks_INPUT/.",
    )
    p.add_argument(
        "--category",
        choices=sorted(_CATEGORIES.keys()),
        default=None,
        help=(
            "One of the 16 human categories.  See CATEGORIES.md.  "
            "Defaults to 'software-engineering' when --random is not set."
        ),
    )
    p.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Deterministic seed for randomization.  Omit for a fresh "
        "random seed (which is printed).",
    )
    p.add_argument(
        "--random",
        action="store_true",
        help="Pick a random category too, on top of the random seed.",
    )
    p.add_argument(
        "--name",
        default=None,
        help="Bundle directory name.  Auto-synthesized when omitted.  "
        "Regex: %s" % _NAME_RE.pattern,
    )
    p.add_argument(
        "--title",
        default=None,
        help="Human-readable task title (defaults to Title-Cased --name).",
    )
    p.add_argument(
        "--format-tag",
        default=None,
        help="Short uppercase tag identifying the invented format "
        "(auto-picked from the category pool when omitted).  "
        "Regex: %s" % _TAG_RE.pattern,
    )
    p.add_argument(
        "--format-ext",
        default=None,
        help="Lowercase file extension for the invented format including "
        "the leading dot (auto-picked when omitted).  Regex: %s" % _EXT_RE.pattern,
    )
    p.add_argument(
        "--description",
        default=None,
        help="One-sentence task description (auto-synthesized when omitted).",
    )
    p.add_argument(
        "--keywords",
        default=None,
        help="Comma-separated keyword list for task.toml (auto-synthesized when omitted).",
    )
    p.add_argument(
        "--tags",
        default=None,
        help="Comma-separated tag list for [metadata].tags (defaults to --keywords).",
    )
    p.add_argument(
        "--docker-image",
        default=None,
        help=(
            "Legacy compatibility option retained for callers; the current "
            "slim task.toml template does not emit docker_image."
        ),
    )
    p.add_argument(
        "--estimated-duration-sec",
        type=float,
        default=None,
        help="[metadata].estimated_duration_sec (default: 7200.0).",
    )
    p.add_argument(
        "--expert-time-min",
        dest="expert_time_estimate_min",
        type=float,
        default=None,
        help="[metadata].expert_time_estimate_min (default: 480.0).",
    )
    p.add_argument(
        "--junior-time-min",
        dest="junior_time_estimate_min",
        type=float,
        default=None,
        help="[metadata].junior_time_estimate_min (default: 1440.0).",
    )
    p.add_argument(
        "--verifier-timeout-sec",
        type=float,
        default=None,
        help="[verifier].timeout_sec (default: 2700.0).",
    )
    p.add_argument(
        "--agent-timeout-sec",
        type=float,
        default=None,
        help="[agent].timeout_sec (default: 7200.0).",
    )
    p.add_argument(
        "--build-timeout-sec",
        type=float,
        default=None,
        help="[environment].build_timeout_sec (default: 900.0).",
    )
    p.add_argument(
        "--cpus",
        dest="cpus",
        type=_positive_int,
        default=None,
        help="[environment].cpus (default: 2).",
    )
    p.add_argument(
        "--memory-mb",
        dest="memory_mb",
        type=_positive_int,
        default=None,
        help="[environment].memory_mb (default: 4096).",
    )
    p.add_argument(
        "--storage-mb",
        dest="storage_mb",
        type=_positive_int,
        default=None,
        help="[environment].storage_mb (default: 10240).",
    )
    p.add_argument(
        "--author",
        dest="authors",
        action="append",
        default=None,
        metavar="NAME <EMAIL>",
        help="Contributor for [task].authors.  Repeatable.  Must be in the form "
        "'Full Name <email@example.com>', where the name is two or more "
        "capitalised words (e.g. 'Ram Lakhan') and the email's local part is "
        "built from those words.  Harbor 0.24 QC FC-S18 rejects anything else.",
    )
    p.add_argument(
        "--archetype",
        default=_ARCHETYPE_AUTO,
        help="Task archetype to scaffold (selects templates/<archetype>/).  "
        "Use 'auto' (default) to pick a domain-appropriate archetype at "
        "random so bundles vary in shape, 'random' to pick from any archetype "
        "ignoring the domain, or an explicit name.  Available: "
        + (", ".join(_discover_archetypes()) or "<none>")
        + ".",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing <out>/<name>/ tree.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    target = scaffold_bundle(args)

    print(f"[generate_bundle] scaffolded: {target}")
    print(f"[generate_bundle] category: {args.category}")
    suffix = " (auto)" if getattr(args, "archetype_auto", False) else ""
    print(f"[generate_bundle] archetype: {args.archetype}{suffix}")
    print(f"[generate_bundle] authors:  {args.authors if args.authors else '(none)'}")
    print(f"[generate_bundle] name:     {args.name}")
    print(f"[generate_bundle] tag:      {args.format_tag}  ext: {args.format_ext}")
    print(f"[generate_bundle] magic:    {args.magic!r}  version: {args.version}")
    print(f"[generate_bundle] seed:     {args.seed}")
    print("[generate_bundle] next steps:")
    print(
        "  1. python3 '{parent}/validate_bundle.py' '{target}'".format(
            parent=_REPO_ROOT, target=target
        )
    )
    print("  2. python3 Input_Bundle_QC/exe_copy.py <bundle> /tmp/step10run   # tests-only copy")
    print("  3. harbor run --path /tmp/step10run --agent oracle -y   # expect exactly 1.000, five runs")
    print("  4. harbor run --path /tmp/step10run --agent nop -y      # expect exactly 0.000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
