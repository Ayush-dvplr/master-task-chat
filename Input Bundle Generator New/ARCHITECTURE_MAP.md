# Input Bundle Generator - Comprehensive Architectural Map

> **Superseded for Harbor 0.24.** The bundle contract is now
> `Input_Bundle_QC/Final_checklist.md`: schema 1.4 task.toml, rewardkit test channel
> (`criteria.<name>(weight=W)` in `tests/test_output.py`, no `test_weights.json`),
> `tests/judge.toml` instead of `rubric.json`, a generated `tests/reward.toml`, and
> no `README.md` in the bundle. Where this document says otherwise, the checklist wins.

**Location:** `/Users/macbookpro/Desktop/Input_Bundle_Generator_Anubis/Terminal_2.0_Harbor_Harness/Input Bundle Generator New`

**Version:** v2.0 (seeded, category-driven, multi-archetype)

---

## 1. ENTRY POINT & CLI

### Main Entry Point
- **File:** `generate_bundle.py` (1928 lines)
- **Entry function:** `main(argv: list[str] | None = None) -> int` (line 1903)
- **CLI Framework:** `argparse` (stdlib only, no external dependencies)
- **Invocation:** `python3 generate_bundle.py --out <dir> [options]`

### CLI Arguments (All Optional Except `--out`)

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--out` | str | **REQUIRED** | Directory to scaffold into; bundle created at `<out>/<name>/` |
| `--category` | choice | `software-engineering` | One of 16 human categories (see CATEGORIES.md) |
| `--seed` | int | auto (secrets.randbits(63)) | Deterministic seed; printed if auto-generated |
| `--random` | flag | False | Pick random category + seed |
| `--name` | str | auto-generated | Bundle directory name (regex: `^[a-z0-9][a-z0-9-]{2,63}$`) |
| `--title` | str | Title-cased `--name` | Human-readable task title |
| `--format-tag` | str | auto-picked | Short uppercase tag for invented format (regex: `^[A-Z][A-Z0-9]{2,7}$`) |
| `--format-ext` | str | auto-picked | File extension with dot (regex: `^\.[a-z0-9]{2,8}$`) |
| `--description` | str | archetype default | One-sentence task description |
| `--keywords` | str | archetype default | Comma-separated keyword list |
| `--tags` | str | `--keywords` value | Comma-separated tag list for `[metadata].tags` |
| `--difficulty` | choice | `hard` | `trivial`, `easy`, `medium`, `hard`, `expert` |
| `--docker-image` | str | `terminal-bench/<name>:latest` | Legacy compatibility (no-op in slim schema) |
| `--estimated-duration-sec` | float | 7200.0 | Wall-clock estimate |
| `--expert-time-min` | float | 480.0 | Expert time estimate in minutes |
| `--junior-time-min` | float | 1440.0 | Junior time estimate in minutes |
| `--verifier-timeout-sec` | float | 2700.0 | Verifier timeout |
| `--agent-timeout-sec` | float | 7200.0 | Agent timeout |
| `--build-timeout-sec` | float | 900.0 | Docker build timeout |
| `--allow-internet` | bool | forced `true` | DEPRECATED no-op; generated bundles always set `allow_internet = true` |
| `--archetype` | str | `auto` | Task archetype: `auto` (domain-appropriate random), `random` (any), or explicit name |
| `--force` | flag | False | Overwrite existing `<out>/<name>/` tree |

### No Interactive Prompting
- Generator is fully non-interactive
- All inputs via CLI flags or defaults
- Seed printed to stdout for reproducibility

---

## 2. TASK GENERATION PIPELINE

### High-Level Flow

```
main()
  ↓
_build_parser() → parse CLI args
  ↓
scaffold_bundle(args)
  ├─ _resolve_args(args)
  │   ├─ _pick_seed() if seed is None
  │   ├─ _seeded_random(seed) → RNG
  │   ├─ Category selection (random or CLI)
  │   ├─ _select_archetype(category, seed, mode) → archetype name
  │   ├─ _load_archetype_manifest(archetype) → ArchetypeManifest
  │   ├─ Auto-generate: format_tag, format_ext, name, title, description, keywords
  │   ├─ Derive: magic, version, container_noun, producer_system (format-recovery only)
  │   └─ Set defaults: difficulty, timeouts, allow_internet, etc.
  │
  ├─ _validate_args(args)
  │
  ├─ _archetype_dir(archetype) → Path to templates/<archetype>/
  │
  ├─ _build_substitutions(args) → dict[str, str]
  │   └─ 60+ template placeholders ({{BUNDLE_NAME}}, {{MAGIC_HEX}}, {{GRAMMAR_PY_LITERAL}}, etc.)
  │
  ├─ Create target directory: <out>/<name>/
  │
  ├─ _walk_templates(template_dir)
  │   └─ For each template file:
  │       ├─ _is_text_file(src) → bool
  │       ├─ _apply_substitutions(text, subs) → substituted text
  │       ├─ _rewrite_path(rel_path, subs) → rewritten path
  │       └─ Write to target (preserving executable bits)
  │
  ├─ _write_source_archive() for each source_archives entry in manifest
  │
  ├─ _run_post_generate(target, post_generate_commands)
  │   └─ Run Python scripts (e.g., tests/test_output.py, environment)
  │
  ├─ _ensure_exec(solution/solve.sh)
  ├─ _ensure_exec(tests/test.sh)
  │
  ├─ _write_truth_md(target, args)          # second pass, after the tree exists
  │   ├─ _truth_bundle_facts(target)        # sha256 of solution/*, artifacts from task.toml,
  │   │                                     #   environment/data/ listing
  │   ├─ _truth_weight_facts(target)        # counts + signed totals from tests/test_weights.json
  │   ├─ _truth_rubric_facts(target)        # criteria counts + text from tests/rubric.json
  │   ├─ _truth_provenance_block(args, ...) # the fenced yaml block
  │   └─ resolve {{TRUTH_*}} tokens; die on any survivor
  │
  └─ return target Path
```

### Key Functions (Signatures)

#### Argument Resolution
```python
def _resolve_args(args: argparse.Namespace) -> argparse.Namespace
def _pick_seed() -> int
def _seeded_random(seed: int) -> random.Random
def _select_archetype(category: str, seed: int, mode: str) -> str
def _load_archetype_manifest(archetype: str) -> ArchetypeManifest
```

#### Auto-Generation (Deterministic per Seed)
```python
def _auto_name(rng: random.Random, category: str, seed: int) -> str
def _auto_title(name: str) -> str
def _auto_format_tag(rng: random.Random, category: str) -> str
def _auto_format_ext(rng: random.Random, category: str) -> str
def _auto_magic(rng: random.Random, category: str) -> bytes
def _auto_version(rng: random.Random) -> int
def _auto_container_noun(rng: random.Random, category: str) -> str
def _auto_producer(rng: random.Random, category: str) -> str
```

#### Seed Derivation (for SAMPLE_SEED, CHALLENGE_SEED, EVAL_SEED)
```python
def _derive_seed(root: int, tag: str) -> int
def _derive_guid(root: int) -> str
def _derive_grammar(root: int) -> ContainerGrammar
```

#### Template Processing
```python
def _build_substitutions(args: argparse.Namespace) -> dict[str, str]
def _is_text_file(path: Path) -> bool
def _apply_substitutions(text: str, subs: dict[str, str]) -> str
def _rewrite_path(rel_path: Path, subs: dict[str, str]) -> Path
def _walk_templates(root: Path) -> Iterable[Path]
def _preserve_exec(src: Path, dst: Path) -> None
def _ensure_exec(path: Path) -> None
```

#### Post-Generation
```python
def _run_post_generate(target: Path, command: list[str]) -> None
def _write_source_archive(template_dir: Path, target: Path, archive: dict, subs: dict) -> None
```

#### Main Orchestration
```python
def scaffold_bundle(args: argparse.Namespace) -> Path
def main(argv: list[str] | None = None) -> int
```

### Template Shape Decision

The generator determines output structure via **archetype selection**:

1. **Archetype Selection Logic:**
   - If `--archetype auto` (default): pick domain-appropriate archetype at random (seeded)
   - If `--archetype random`: pick any archetype at random (seeded)
   - If `--archetype <name>`: use explicit archetype
   - Affinity map in `ARCHETYPE_SELECTION.md` defines which archetypes fit which domains

2. **Archetype Manifest (`archetype.toml`):**
   - Declares `name`, `summary`, `artifacts` (list of output paths)
   - Declares `allow_internet` (network requirement)
   - Declares `default_description` and `default_keywords`
   - Declares `source_archives` (optional; zips to generate)
   - Declares `post_generate` (optional; Python scripts to run after scaffolding)

3. **Template Tree Structure:**
   - Each archetype has a complete template tree under `templates/<archetype>/`
   - Contains: `archetype.toml`, `instruction.md`, `task.toml`, `README.md`, `environment/`, `solution/`, `tests/`
   - All text files contain `{{PLACEHOLDER}}` markers for substitution
   - Binary files copied as-is

### No LLM Invocation
- **Generator is 100% deterministic and offline**
- No OpenAI/Anthropic API calls
- All content is hardcoded templates + seeded randomization
- No external dependencies (stdlib only)

---

## 3. CURRENT OUTPUT STRUCTURE

### Per-Task Bundle Directory

Every generated bundle has this exact structure:

```
<bundle-name>/
├── instruction.md              # Agent-visible task description (<1500 tokens)
├── task.toml                   # Harbor + frontier-bench dual-schema config
├── README.md                   # Human-visible prose (metadata, explanations)
├── environment/
│   ├── Dockerfile              # Agent image (digest-pinned public.ecr.aws base)
│   └── data/                   # Archetype input data; no hidden answers
├── solution/
│   ├── solve.sh                # Oracle dispatcher (chmod +x)
│   ├── solve.py                # Oracle reference implementation
│   └── TRUTH.md                # Author-side golden trajectory (never shipped to the agent)
└── tests/
    ├── Dockerfile              # Verifier image (pytest deps pinned)
    ├── test.sh                 # Verifier entrypoint (chmod +x)
    ├── test_output.py          # Archetype-specific checker + hidden-ground-truth logic
    ├── test_weights.json       # Per-test signed weights (positive total drives reward denominator)
    └── rubric.json             # LLM-judged behavior criteria (grades process, not outputs)
```

### Files Generated Per Archetype

#### `format-recovery` (8 archetypes total)
- **Artifacts:** `/app/decode.py`, `/app/encode.py`
- **Environment data:** `{{FORMAT_TAG}}-v1.0-DRAFT.md` (seeded binary format spec)
- **Post-generate:** `tests/test_output.py`, `environment` (regenerates corpus from seeds)
- **Key placeholders:** `{{MAGIC_ASCII}}`, `{{MAGIC_HEX}}`, `{{VERSION_NUM}}`, `{{GRAMMAR_PY_LITERAL}}`, `{{SAMPLE_SEED}}`, `{{CHALLENGE_SEED}}`, `{{EVAL_SEED}}`

#### `build-repair`
- **Artifacts:** `/app/out/package.zip`, `/app/out/selftest.json`
- **Environment data:** `project/` (broken Python package)
- **Source archive:** `environment/data/project.zip` (generated from `environment/data/project/`)
- **Key placeholders:** `{{BUNDLE_NAME}}`, `{{PACKAGE_NAME}}`, `{{TASK_DESCRIPTION}}`

#### `repo-patch`
- **Artifacts:** `/app/out/repo.zip`, `/app/out/patch.diff`
- **Environment data:** `repo/` (broken git repository)
- **Source archive:** `environment/data/repo.zip`

#### `data-pipeline`, `cli-config`, `service-interaction`, `performance`, `domain-calculation`
- Similar structure; archetype-specific data and artifacts

### Cheat-Related Content

**Extensive anti-cheat infrastructure:**

1. **Negative-weight tests** (in `tests/test_weights.json` and `tests/test_output.py`):
   - `test_negative_weight_hardcoded_sample_answers` (weight: -5)
   - `test_negative_weight_filename_dependent_behaviour` (weight: -5)
   - `test_negative_weight_reads_training_corpus_at_runtime` (weight: -5)
   - `test_negative_weight_nondeterministic_output` (weight: -3)
   - Archetype-specific variants (e.g., `test_negative_weight_network_or_monkeypatch_cheat`)

2. **Structural anti-cheat:**
   - Two separate Dockerfiles: `environment/Dockerfile` (agent) and `tests/Dockerfile` (verifier)
   - `EVAL_SEED` lives only in `tests/Dockerfile`, never in agent image
   - No `sample_*.json` answer files in `environment/data/`
   - Exact byte/int/JSON comparison (no loose tolerances)

3. **Instruction anti-cheat:**
   - Every `instruction.md` ends with: "Do not cheat by using online solutions or hints specific to this task."
   - Enforced by `validate_bundle.py` §2.5

4. **Documentation:**
   - `CHEAT_VECTORS.md` — 8 known cheats + mitigations (hardcoding, filename-dependent, runtime data access, nondeterminism, eval leaks, answer files, loose tolerances, online lookup)
   - `FORMAT_SPEC.md` §11 — cheat-vector matrix

---

## 4. CONFIG/PROMPTS/TEMPLATES

### Prompt Templates
- **No prompt templates** — generator is deterministic, not LLM-driven
- All content is hardcoded in `templates/<archetype>/` files

### Template Files (Text with Placeholders)

Located in `templates/<archetype>/`:

| File | Placeholders | Purpose |
|------|--------------|---------|
| `instruction.md` | `{{AGENT_TIMEOUT_SEC_INT}}`, `{{BUNDLE_NAME}}`, `{{TASK_DESCRIPTION}}`, `{{FORMAT_TAG}}`, `{{MAGIC_ASCII}}`, `{{GRAMMAR_SUMMARY}}`, etc. | Agent-visible task description |
| `task.toml` | `{{ARTIFACTS}}`, `{{BUNDLE_NAME}}`, `{{TASK_DESCRIPTION}}`, `{{DIFFICULTY}}`, `{{CATEGORY}}`, `{{ESTIMATED_DURATION_SEC}}`, `{{ALLOW_INTERNET}}`, etc. | Harbor configuration |
| `README.md` | `{{BUNDLE_TITLE}}`, `{{DIFFICULTY}}`, `{{CATEGORY}}`, `{{EXPERT_TIME_HR}}`, `{{JUNIOR_TIME_HR}}`, `{{ARCHETYPE}}`, etc. | Human-visible metadata + explanations |
| `environment/Dockerfile` | `{{PACKAGE_NAME}}` | Agent image definition |
| `solution/solve.sh` | `{{BUNDLE_NAME}}`, `{{PACKAGE_NAME}}` | Oracle dispatcher |
| `solution/solve.py` | `{{MAGIC_ASCII}}`, `{{GRAMMAR_PY_LITERAL}}`, `{{VERSION_NUM}}`, etc. | Oracle reference implementation |
| `tests/test_output.py` | `{{MAGIC_ASCII}}`, `{{GRAMMAR_PY_LITERAL}}`, `{{SAMPLE_SEED}}`, `{{CHALLENGE_SEED}}`, `{{EVAL_SEED}}`, etc. | Verifier logic + corpus generation |
| `tests/test_weights.json` | None (static) | Test weight declarations |
| `tests/rubric.json` | None (static) | LLM-judged behavior criteria |
| `solution/TRUTH.md` | `{{BUNDLE_NAME}}`, `{{SEED_HEX}}`, `{{EVAL_SEED}}`, plus the second-pass `{{TRUTH_*}}` family | Author-side golden trajectory; see FORMAT_SPEC.md §15 |
| `environment/data/*` | Varies (e.g., `{{FORMAT_TAG}}-v1.0-DRAFT.md`) | Archetype-specific input data |

### Archetype Manifest (`archetype.toml`)

Located in `templates/<archetype>/archetype.toml`:

```toml
name = "format-recovery"
summary = "Reverse-engineer a partially-redacted binary container spec..."
artifacts = ["/app/decode.py", "/app/encode.py"]
allow_internet = true
default_description = "Recover a seeded binary container grammar..."
default_keywords = ["python", "binary-format", "decoder", "encoder", "stdlib"]
post_generate = ["tests/test_output.py", "environment"]

[[source_archives]]
source = "environment/data/project"
output = "environment/data/project.zip"
```

### Config File (Task-Level)

**`task.toml` (generated per task):**

```toml
schema_version = "1.1"
artifacts = ["/app/decode.py", "/app/encode.py"]

[task]
name = "terminal-bench/<bundle-name>"
description = "..."
keywords = ["python", "binary-format", ...]

[metadata]
difficulty = "hard"
category = "Software Engineering"
tags = ["python", "binary-format", ...]
estimated_duration_sec = 7200.0
expert_time_estimate_min = 480.0
junior_time_estimate_min = 1440.0

[verifier]
timeout_sec = 2700.0
environment_mode = "separate"

[agent]
timeout_sec = 7200.0

[environment]
build_timeout_sec = 900.0
allow_internet = true
mcp_servers = []
```

### Flags/Modes

**Archetype selection modes:**
- `--archetype auto` (default): domain-appropriate random archetype
- `--archetype random`: any archetype at random
- `--archetype <name>`: explicit archetype (e.g., `format-recovery`, `build-repair`)

**Randomization modes:**
- `--random`: pick random category + seed
- `--seed <int>`: deterministic seed (byte-reproducible)
- No `--seed`: auto-generate from `secrets.randbits(63)` and print

**Optional components:**
- `--allow-internet` / `--no-allow-internet`: DEPRECATED no-op; generated bundles always emit `allow_internet = true`
- `--force`: overwrite existing bundle

---

## 5. BATCH vs SINGLE TASK GENERATION

### Single Task at a Time
- Generator produces **ONE task per invocation**
- Output: `<out>/<name>/` directory
- No batch mode

### Per-Task Configuration
- All configuration via CLI flags (no per-task config file)
- Archetype manifest (`archetype.toml`) is per-archetype, not per-task
- Per-task overrides via CLI flags (e.g., `--difficulty hard`, `--keywords ...`)

### Reproducibility
- Fixed `--seed` + `--category` + `--archetype` + output-directory state → byte-identical output
- Useful for batch generation: loop over seeds, categories, or archetypes

---

## 6. KEY DATA STRUCTURES

### TypedDicts (Type Hints)

```python
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

class ArchetypeManifest(TypedDict):
    name: str
    summary: str
    artifacts: list[str]
    default_description: str
    default_keywords: list[str]
    source_archives: NotRequired[list[SourceArchive]]
    post_generate: NotRequired[list[str]]
    allow_internet: NotRequired[bool]
```

### argparse.Namespace (After Resolution)

After `_resolve_args()`, the namespace contains:

```python
args.seed: int                          # Deterministic seed
args.category: str                      # One of 16 categories
args.archetype: str                     # Archetype name (e.g., "format-recovery")
args.archetype_auto: bool               # True if auto/random was used
args.archetype_manifest: ArchetypeManifest
args.name: str                          # Bundle directory name
args.title: str                         # Human-readable title
args.format_tag: str                    # Short uppercase tag (format-recovery only)
args.format_ext: str                    # File extension (format-recovery only)
args.description: str                   # One-sentence description
args.keywords: str                      # Comma-separated keywords
args.tags: str                          # Comma-separated tags
args.difficulty: str                    # "trivial" | "easy" | "medium" | "hard" | "expert"
args.docker_image: str                  # Legacy (no-op)
args.estimated_duration_sec: float
args.expert_time_estimate_min: float
args.junior_time_estimate_min: float
args.verifier_timeout_sec: float
args.agent_timeout_sec: float
args.build_timeout_sec: float
args.allow_internet: bool               # Accepted but ignored; always forced True
args.magic: bytes                       # 5-byte magic (format-recovery only)
args.version: int                       # Version number (format-recovery only)
args.container_noun: str                # Narrative noun (format-recovery only)
args.producer_system: str               # Fictional producer (format-recovery only)
args.artifacts_toml: str                # JSON-serialized artifacts list
args.mcp_servers_toml: str              # JSON-serialized MCP servers list
args.out: str                           # Output directory
args.force: bool                        # Overwrite existing
args.random: bool                       # Random category + seed
```

### Second-Pass TRUTH.md Tokens

Resolved by `_write_truth_md()` **after** the bundle tree exists, from the
generated files rather than from CLI arguments:

```python
{{TRUTH_SOLVE_SH_SHA256}}   {{TRUTH_SOLVE_PY_SHA256}}    {{TRUTH_SOLVE_PY_LINES}}
{{TRUTH_ARTIFACT_COUNT}}    {{TRUTH_ARTIFACT_LIST}}
{{TRUTH_DATA_FILE_COUNT}}   {{TRUTH_DATA_FILE_LIST}}
{{TRUTH_TEST_COUNT}}        {{TRUTH_POSITIVE_COUNT}}     {{TRUTH_NEGATIVE_COUNT}}
{{TRUTH_POSITIVE_TOTAL}}    {{TRUTH_NEGATIVE_TOTAL}}
{{TRUTH_REWARD_FLOOR}}      {{TRUTH_REWARD_RANGE}}       {{TRUTH_CHANNEL_A_SUMMARY}}
{{TRUTH_POSITIVE_TEST_LIST}} {{TRUTH_NEGATIVE_TEST_LIST}}
{{TRUTH_RUBRIC_COUNT}}      {{TRUTH_RUBRIC_POSITIVE_COUNT}}  {{TRUTH_RUBRIC_NEGATIVE_COUNT}}
{{TRUTH_RUBRIC_POSITIVE_TOTAL}}  {{TRUTH_RUBRIC_NEGATIVE_TOTAL}}
{{TRUTH_RUBRIC_SUMMARY}}    {{TRUTH_RUBRIC_LIST}}        {{TRUTH_PROVENANCE_BLOCK}}
```

### Substitution Dictionary (60+ Placeholders)

```python
subs: dict[str, str] = {
    # v1 placeholders (backward compatibility)
    "{{BUNDLE_NAME}}": args.name,
    "{{BUNDLE_TITLE}}": args.title,
    "{{FORMAT_TAG}}": args.format_tag,
    "{{PACKAGE_NAME}}": args.format_tag.lower(),
    "{{FORMAT_EXT}}": ext_bare,
    "{{TASK_DESCRIPTION}}": args.description,
    "{{TASK_KEYWORDS}}": keywords_toml,
    
    # v2 placeholders (taxonomy + seeds)
    "{{CATEGORY_CANONICAL}}": cat["canonical"],
    "{{SUBCATEGORY}}": cat["subcategory"],
    "{{CATEGORY_HUMAN}}": args.category,
    "{{SEED_HEX}}": f"{args.seed:016x}",
    "{{SAMPLE_SEED}}": str(_derive_seed(args.seed, "sample")),
    "{{CHALLENGE_SEED}}": str(_derive_seed(args.seed, "challenge")),
    "{{EVAL_SEED}}": str(_derive_seed(args.seed, "eval")),
    
    # Format-specific (format-recovery only)
    "{{MAGIC_ASCII}}": _magic_ascii_literal(args.magic),
    "{{MAGIC_HEX}}": magic_hex,
    "{{VERSION_NUM}}": str(args.version),
    "{{VERSION_NUM_HEX}}": f"{args.version:02x}",
    "{{GRAMMAR_PY_LITERAL}}": _grammar_python_literal(grammar),
    "{{GRAMMAR_RAW_MODE_ID}}": str(grammar["selector"]["mode_ids"]["raw"]),
    "{{GRAMMAR_SUMMARY}}": _grammar_summary(grammar),
    "{{GRAMMAR_HEADER_TABLE}}": _grammar_header_table(grammar, magic_hex, args.version),
    "{{GRAMMAR_SELECTOR_DOC}}": _grammar_selector_doc(grammar),
    "{{GRAMMAR_CRC_DOC}}": _grammar_crc_doc(grammar),
    "{{GRAMMAR_WORKED_EXAMPLES}}": _grammar_worked_examples(grammar),
    "{{GRAMMAR_EMPTY_HEX}}": _grammar_empty_hex(grammar, args.magic, args.version),
    "{{HARBOR_CANARY_GUID}}": _derive_guid(args.seed),
    "{{CONTAINER_NOUN}}": args.container_noun,
    "{{PRODUCER_SYSTEM}}": args.producer_system,
    
    # Metadata
    "{{ARCHETYPE}}": args.archetype,
    "{{ARTIFACTS}}": args.artifacts_toml,
    "{{DIFFICULTY}}": args.difficulty,
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
    "{{DOCKER_IMAGE}}": args.docker_image,
    "{{ALLOW_INTERNET}}": "true",  # forced on for every generated bundle
    "{{MCP_SERVERS}}": args.mcp_servers_toml,
}
```

---

## 7. DIRECTORY TREE (2-3 Levels)

```
Input Bundle Generator New/
├── README.md                           # Quick-start guide
├── FORMAT_SPEC.md                      # Authoritative format specification
├── CHEAT_VECTORS.md                    # 8 known cheats + mitigations
├── AUDIT_NOTES.md                      # Format audit trail + v2 refactor notes
├── ARCHETYPE_SELECTION.md              # Domain → archetype affinity map
├── CATEGORIES.md                       # 16 CLI categories + taxonomy
├── GENERATOR_TRAP_RECIPE.md            # Step-by-step generation walkthrough
├── generate_bundle.py                  # Main generator (1928 lines)
├── validate_bundle.py                  # Bundle validator (1400+ lines)
├── reference/                          # Reference docs + frontier-bench
│   ├── README.md
│   ├── frontier-bench/
│   │   ├── docs/
│   │   │   ├── TASK_REVIEW_AUTOMATION.md
│   │   │   ├── REVIEWING.md
│   │   │   └── ...
│   │   └── rubrics/
│   │       ├── task-implementation.toml
│   │       ├── hack-trial-prompt.md
│   │       └── trial-analysis.toml
│   └── ...
└── templates/                          # Per-archetype template trees
    ├── format-recovery/
    │   ├── archetype.toml
    │   ├── instruction.md
    │   ├── task.toml
    │   ├── README.md
    │   ├── environment/
    │   │   ├── Dockerfile
    │   │   └── data/
    │   │       └── {{FORMAT_TAG}}-v1.0-DRAFT.md
    │   ├── solution/
    │   │   ├── solve.sh
    │   │   └── solve.py
    │   └── tests/
    │       ├── Dockerfile
    │       ├── test.sh
    │       ├── test_output.py
    │       ├── test_weights.json
    │       └── rubric.json
    ├── build-repair/
    │   ├── archetype.toml
    │   ├── instruction.md
    │   ├── task.toml
    │   ├── README.md
    │   ├── environment/
    │   │   ├── Dockerfile
    │   │   └── data/
    │   │       └── project/
    │   ├── solution/
    │   │   ├── solve.sh
    │   │   └── solve.py
    │   └── tests/
    │       ├── Dockerfile
    │       ├── test.sh
    │       ├── test_output.py
    │       ├── test_weights.json
    │       └── rubric.json
    ├── repo-patch/
    ├── data-pipeline/
    ├── cli-config/
    ├── service-interaction/
    ├── performance/
    └── domain-calculation/
```

---

## 8. CONCRETE FILE PATHS

### Entry Point
- **Main script:** `/Users/macbookpro/Desktop/Input_Bundle_Generator_Anubis/Terminal_2.0_Harbor_Harness/Input Bundle Generator New/generate_bundle.py`
- **Validator:** `/Users/macbookpro/Desktop/Input_Bundle_Generator_Anubis/Terminal_2.0_Harbor_Harness/Input Bundle Generator New/validate_bundle.py`

### Template Roots (Per Archetype)
- `templates/format-recovery/`
- `templates/build-repair/`
- `templates/repo-patch/`
- `templates/data-pipeline/`
- `templates/cli-config/`
- `templates/service-interaction/`
- `templates/performance/`
- `templates/domain-calculation/`

### Documentation
- **Format spec:** `FORMAT_SPEC.md`
- **Cheat vectors:** `CHEAT_VECTORS.md`
- **Categories:** `CATEGORIES.md`
- **Archetype selection:** `ARCHETYPE_SELECTION.md`
- **Audit notes:** `AUDIT_NOTES.md`
- **Generator walkthrough:** `GENERATOR_TRAP_RECIPE.md`
- **Golden trajectory contract:** `FORMAT_SPEC.md` §15 (`TRUTH.md`)

### Reference Docs
- **Frontier-bench task review:** `reference/frontier-bench/docs/TASK_REVIEW_AUTOMATION.md`
- **Reviewing guide:** `reference/frontier-bench/docs/REVIEWING.md`
- **Task implementation rubric:** `reference/frontier-bench/rubrics/task-implementation.toml`
- **Hack trial prompt:** `reference/frontier-bench/rubrics/hack-trial-prompt.md`

---

## 9. EXISTING CHEAT REFERENCES

### Comprehensive Anti-Cheat Infrastructure

**In `CHEAT_VECTORS.md`:**
1. Hardcoding sample outputs (negative test weight: -5)
2. Behavior varies with input filename (negative test weight: -5)
3. Delivered code reads `/app/data/` at runtime (negative test weight: -5)
4. Non-deterministic output across invocations (negative test weight: -3)
5. Eval corpus leaks via filesystem inspection (structural: two-Dockerfile design)
6. Decoded answer files in `environment/data/` (structural: validator rejects `sample_*.json`)
7. Loose numeric tolerances (structural: exact byte/int/JSON comparison)
8. Online-solution lookup (human: prohibition sentence in `instruction.md`)

**In `FORMAT_SPEC.md` §11:**
- Cheat-vector matrix mapping each cheat to its format mitigation

**In `validate_bundle.py`:**
- Checks for required negative-weight tests in `test_weights.json`
- Validates two-Dockerfile separation
- Rejects `sample_*.json` files
- Enforces anti-cheat sentence in `instruction.md`
- Checks for residual markers (TODO, FIXME, PLACEHOLDER)

**In template `tests/test_output.py`:**
- Polarity-inverted assertions: assertion HOLDS when cheat is present
- Honest agent → assertion fails → weight NOT added → score stays high
- Cheating agent → assertion passes → weight IS added → score drops

**In template `instruction.md`:**
- Every instruction ends with: "Do not cheat by using online solutions or hints specific to this task."

**In template `README.md`:**
- Mentions anti-cheat testing (e.g., "hidden answers, fake reports, deleted tests, network or monkeypatch cheats")

**In reference docs:**
- `hack-trial-prompt.md` — adversarial red-team prompt for `/cheat` trials
- `task-implementation.toml` — 30 implementation rubric criteria including anti-cheat robustness
- `REVIEWING.md` — manual review order and `/cheat` command pipeline

---

## 10. SUMMARY: PLANNING A NEW FEATURE

### To Add a New Feature:

1. **New CLI flag?**
   - Add to `_build_parser()` (line 1747)
   - Handle in `_resolve_args()` (line 1525)
   - Add to substitution dict in `_build_substitutions()` (line 1125)

2. **New category?**
   - Add entry to `_CATEGORIES` dict (line ~200)
   - Update `CATEGORIES.md` table
   - Ensure archetype affinity is defined in `ARCHETYPE_SELECTION.md`

3. **New archetype?**
   - Create `templates/<new-archetype>/` directory
   - Create `archetype.toml` with manifest
   - Create template files: `instruction.md`, `task.toml`, `README.md`, `environment/Dockerfile`, `solution/solve.sh`, `solution/solve.py`, `tests/test.sh`, `tests/test_output.py`, `tests/test_weights.json`, `tests/rubric.json`
   - Add to archetype affinity map in `ARCHETYPE_SELECTION.md`

4. **New placeholder?**
   - Add to `_build_substitutions()` (line 1125)
   - Use in template files with `{{PLACEHOLDER_NAME}}`
   - Document in `FORMAT_SPEC.md` if user-facing

5. **New anti-cheat test?**
   - Add negative-weight test to `tests/test_output.py`
   - Add weight entry to `tests/test_weights.json`
   - Document in `CHEAT_VECTORS.md`
   - Add validation rule to `validate_bundle.py`

6. **New validation rule?**
   - Add check function to `validate_bundle.py`
   - Add to `RULES` list
   - Document in `FORMAT_SPEC.md`

---

## 11. QUICK REFERENCE: CORE PIPELINE

```
CLI args
  ↓
_build_parser() + parse_args()
  ↓
scaffold_bundle(args)
  ├─ _resolve_args(args)
  │   └─ Auto-generate missing fields, derive seeds/grammar
  ├─ _validate_args(args)
  ├─ _archetype_dir(archetype)
  ├─ _build_substitutions(args)
  │   └─ 60+ placeholders
  ├─ Create target directory
  ├─ _walk_templates(template_dir)
  │   └─ For each file: substitute, rewrite path, write
  ├─ _write_source_archive() if needed
  ├─ _run_post_generate() if needed
  ├─ _ensure_exec(solve.sh, test.sh)
  └─ return target Path
  ↓
main() prints summary
  ↓
Exit code 0
```

---

**End of Architectural Map**
