"""migrakit: upgrade partner records to their canonical schema through a migration graph."""

from .core.executor import execute_plan
from .core.fingerprint import record_fingerprint
from .core.planner import plan_migration, state_signature
from .errors import CODES, MigrationError
from .parser.contracts import Registry, load_contracts
from .parser.identity import resolve_partner
from .pipeline import run_pipeline
from .report.summary import build_summary

__all__ = [
    "CODES",
    "MigrationError",
    "Registry",
    "build_summary",
    "execute_plan",
    "load_contracts",
    "plan_migration",
    "record_fingerprint",
    "resolve_partner",
    "run_pipeline",
    "state_signature",
]
