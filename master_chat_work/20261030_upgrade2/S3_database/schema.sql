-- DRAFT ONLY. Proposed path: master_chat_tasks/pipeline.sqlite.
-- Apply only after an explicit migration plan and Ayush's build approval.
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = FULL;

BEGIN IMMEDIATE;
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE source_records (
  source_path TEXT NOT NULL, source_ordinal TEXT NOT NULL,
  content_sha256 TEXT NOT NULL, raw_json TEXT NOT NULL CHECK(json_valid(raw_json)),
  imported_at TEXT NOT NULL, PRIMARY KEY(source_path, source_ordinal)
);
CREATE INDEX source_records_hash ON source_records(content_sha256);

CREATE TABLE tasks (
  slug TEXT PRIMARY KEY, stage TEXT, stage_since TEXT, kind TEXT, tree_sha TEXT,
  next_action TEXT, updated_at TEXT, pipeline_json TEXT NOT NULL CHECK(json_valid(pipeline_json)),
  task_json TEXT NOT NULL CHECK(json_valid(task_json))
);
CREATE INDEX tasks_stage ON tasks(stage, updated_at);
CREATE TABLE stage_history (
  id INTEGER PRIMARY KEY, slug TEXT NOT NULL REFERENCES tasks(slug),
  from_stage TEXT, to_stage TEXT NOT NULL, changed_at TEXT NOT NULL,
  source_sha TEXT, reason TEXT, source_record TEXT,
  UNIQUE(slug, changed_at, to_stage, source_sha)
);
CREATE INDEX stage_history_task_time ON stage_history(slug, changed_at DESC);

CREATE TABLE pending_items (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT '', prompt TEXT NOT NULL DEFAULT '', send_back TEXT NOT NULL DEFAULT '',
  seq INTEGER NOT NULL DEFAULT 100, priority TEXT NOT NULL DEFAULT 'medium',
  status TEXT NOT NULL DEFAULT 'open', owner TEXT NOT NULL DEFAULT 'Ayush', note TEXT NOT NULL DEFAULT '',
  created_ist TEXT, updated_ist TEXT, closed_ist TEXT
);
CREATE INDEX pending_open_order ON pending_items(status, seq, id);
CREATE TABLE pending_history (
  id INTEGER PRIMARY KEY, item_id TEXT NOT NULL REFERENCES pending_items(id),
  source_rowid INTEGER UNIQUE, ist TEXT, change_text TEXT NOT NULL
);
CREATE INDEX pending_history_item ON pending_history(item_id, id);

CREATE TABLE sessions (
  sha TEXT PRIMARY KEY CHECK(length(sha)=7), slug TEXT NOT NULL,
  step TEXT NOT NULL, kind TEXT, prompt_path TEXT NOT NULL, result_path TEXT NOT NULL,
  status TEXT NOT NULL, pending_id TEXT REFERENCES pending_items(id),
  issued_at TEXT NOT NULL, started_at TEXT, updated_at TEXT, note TEXT NOT NULL DEFAULT '',
  board_json TEXT NOT NULL CHECK(json_valid(board_json))
);
CREATE INDEX sessions_slug_time ON sessions(slug, issued_at DESC);
CREATE INDEX sessions_status_time ON sessions(status, issued_at DESC);
CREATE TABLE session_results (
  sha TEXT PRIMARY KEY REFERENCES sessions(sha), payload_sha256 TEXT NOT NULL,
  status TEXT, verdict TEXT, report_path TEXT, result_json TEXT NOT NULL CHECK(json_valid(result_json)),
  imported_at TEXT NOT NULL
);
CREATE TABLE inbox_merges (
  sha TEXT PRIMARY KEY REFERENCES sessions(sha), schema_version INTEGER NOT NULL,
  inbox_path TEXT NOT NULL, file_sha256 TEXT NOT NULL, result_sha256 TEXT NOT NULL,
  merged_at TEXT NOT NULL, outcome TEXT NOT NULL CHECK(outcome IN ('applied','partial','blocked'))
);
CREATE TABLE inbox_conflicts (
  id INTEGER PRIMARY KEY, sha TEXT NOT NULL, inbox_path TEXT NOT NULL,
  file_sha256 TEXT NOT NULL, observed_at TEXT NOT NULL, reason TEXT NOT NULL,
  resolution TEXT, resolved_at TEXT
);
CREATE INDEX inbox_conflicts_sha ON inbox_conflicts(sha, observed_at DESC);

CREATE TABLE runs (
  id INTEGER PRIMARY KEY, slug TEXT NOT NULL, event TEXT NOT NULL,
  session_sha TEXT REFERENCES sessions(sha), source_path TEXT NOT NULL,
  source_ordinal TEXT NOT NULL, tree_sha TEXT, report_path TEXT, valid INTEGER,
  artefact_reason TEXT, happened_at TEXT, tests REAL, rubric REAL, combined REAL,
  run_json TEXT NOT NULL CHECK(json_valid(run_json)),
  UNIQUE(source_path, source_ordinal)
);
CREATE INDEX runs_task_time ON runs(slug, happened_at DESC);
CREATE INDEX runs_valid_event ON runs(valid, event, happened_at DESC);
CREATE TABLE queue_runs (
  task TEXT NOT NULL, attempt INTEGER NOT NULL, source_path TEXT NOT NULL,
  status TEXT, started_at TEXT, finished_at TEXT, job_dir TEXT, route TEXT,
  run_json TEXT NOT NULL CHECK(json_valid(run_json)),
  PRIMARY KEY(task, attempt, source_path)
);

CREATE TABLE qc_rounds (
  sha TEXT PRIMARY KEY REFERENCES sessions(sha), slug TEXT NOT NULL,
  mode TEXT, status TEXT, verdict TEXT, report_path TEXT NOT NULL,
  fail_count INTEGER, minor_count INTEGER, warn_count INTEGER,
  kit_sha TEXT, rewards_json TEXT CHECK(rewards_json IS NULL OR json_valid(rewards_json)),
  ql_rows_json TEXT CHECK(ql_rows_json IS NULL OR json_valid(ql_rows_json)),
  result_json TEXT NOT NULL CHECK(json_valid(result_json))
);
CREATE INDEX qc_rounds_task ON qc_rounds(slug, sha);
CREATE TABLE qc_findings (
  id INTEGER PRIMARY KEY, qc_sha TEXT NOT NULL REFERENCES qc_rounds(sha),
  finding_id TEXT, severity TEXT, title TEXT, evidence TEXT,
  ruling TEXT, report_line INTEGER, raw_text TEXT,
  UNIQUE(qc_sha, finding_id)
);
CREATE INDEX qc_findings_round_severity ON qc_findings(qc_sha, severity);

CREATE TABLE decisions (
  id INTEGER PRIMARY KEY, source_path TEXT NOT NULL, source_line INTEGER NOT NULL,
  ist TEXT, actor TEXT, slug TEXT, decision_text TEXT, verbatim TEXT,
  raw_json TEXT NOT NULL CHECK(json_valid(raw_json)), UNIQUE(source_path,source_line)
);
CREATE INDEX decisions_task_time ON decisions(slug, ist DESC);
CREATE TABLE feedback (
  id INTEGER PRIMARY KEY, source_path TEXT NOT NULL, source_line INTEGER NOT NULL,
  ist TEXT, actor TEXT, class TEXT, verbatim TEXT, action TEXT,
  raw_json TEXT NOT NULL CHECK(json_valid(raw_json)), UNIQUE(source_path,source_line)
);
CREATE TABLE lessons (
  id INTEGER PRIMARY KEY, source_path TEXT NOT NULL, source_line INTEGER NOT NULL,
  ist TEXT, kind TEXT, lesson TEXT, status TEXT,
  raw_json TEXT NOT NULL CHECK(json_valid(raw_json)), UNIQUE(source_path,source_line)
);
CREATE TABLE levers (
  lever_id TEXT PRIMARY KEY, name TEXT NOT NULL, family TEXT, status TEXT,
  first_task TEXT, lever_json TEXT NOT NULL CHECK(json_valid(lever_json))
);
CREATE INDEX levers_status_family ON levers(status, family);
CREATE TABLE task_levers (
  slug TEXT NOT NULL REFERENCES tasks(slug), lever_id TEXT NOT NULL REFERENCES levers(lever_id),
  source TEXT, PRIMARY KEY(slug, lever_id)
);
CREATE TABLE exceptions (
  id INTEGER PRIMARY KEY, slug TEXT, scope TEXT NOT NULL, rule TEXT NOT NULL,
  permitted_by TEXT NOT NULL, verbatim TEXT, decision_id INTEGER REFERENCES decisions(id),
  valid_from TEXT, valid_until TEXT, active INTEGER NOT NULL DEFAULT 1,
  evidence_path TEXT, raw_json TEXT CHECK(raw_json IS NULL OR json_valid(raw_json))
);
CREATE INDEX exceptions_task_active ON exceptions(slug, active);

CREATE TABLE ideas (
  id INTEGER PRIMARY KEY, source_path TEXT NOT NULL, source_line INTEGER NOT NULL,
  idea_id TEXT, verdict TEXT, raw_json TEXT NOT NULL CHECK(json_valid(raw_json)),
  UNIQUE(source_path,source_line)
);
CREATE TABLE peer_tasks (
  slug TEXT PRIMARY KEY, verdict TEXT, repo_head TEXT,
  raw_json TEXT NOT NULL CHECK(json_valid(raw_json))
);
CREATE TABLE questions (
  id TEXT PRIMARY KEY, status TEXT, owner TEXT, asked_ist TEXT,
  closed_ist TEXT, question TEXT, answer TEXT, raw_json TEXT NOT NULL CHECK(json_valid(raw_json))
);
CREATE TABLE auto_runs (
  run_dir TEXT PRIMARY KEY, label TEXT, started TEXT, ended TEXT,
  state_json TEXT NOT NULL CHECK(json_valid(state_json))
);
CREATE TABLE auto_events (
  run_dir TEXT NOT NULL REFERENCES auto_runs(run_dir), line_no INTEGER NOT NULL,
  ist TEXT, event TEXT, sha TEXT, raw_json TEXT NOT NULL CHECK(json_valid(raw_json)),
  PRIMARY KEY(run_dir,line_no)
);
CREATE INDEX auto_events_sha_time ON auto_events(sha,ist);

CREATE VIEW active_sessions AS
  SELECT sha, slug, step, status, pending_id, issued_at, prompt_path, result_path
  FROM sessions WHERE status IN ('issued','running') ORDER BY issued_at DESC;
CREATE VIEW task_status AS
  SELECT t.slug,t.stage,t.kind,t.tree_sha,t.next_action,
    (SELECT r.tests FROM runs r WHERE r.slug=t.slug AND r.valid=1 ORDER BY r.happened_at DESC,r.id DESC LIMIT 1) AS latest_tests,
    (SELECT r.rubric FROM runs r WHERE r.slug=t.slug AND r.valid=1 ORDER BY r.happened_at DESC,r.id DESC LIMIT 1) AS latest_rubric,
    (SELECT r.combined FROM runs r WHERE r.slug=t.slug AND r.valid=1 ORDER BY r.happened_at DESC,r.id DESC LIMIT 1) AS latest_combined
  FROM tasks t;
COMMIT;
