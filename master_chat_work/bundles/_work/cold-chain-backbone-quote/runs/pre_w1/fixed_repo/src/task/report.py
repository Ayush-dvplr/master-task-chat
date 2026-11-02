"""Build the four book documents from parsed projects and their networks."""
from __future__ import annotations

from .core import Network, best_network, site_lines
from .parser import Project


def share_bp(total: int, quote: int) -> int:
    return total * 10000 // quote


def project_report(project: Project, network: Network) -> dict:
    lines = site_lines(project, network.links)
    quote = network.quote
    corridors: dict[str, int] = {}
    sites = {}
    for p, total in sorted(lines.items()):
        if p == 0:
            continue
        corridor = project.corridors[p]
        corridors[corridor] = corridors.get(corridor, 0) + total
        sites[project.ids[p]] = {"corridor": corridor, "total": total, "share_bp": share_bp(total, quote)}
    return {
        "depot": {"total": lines[0], "share_bp": share_bp(lines[0], quote)},
        "corridors": {
            name: {"total": total, "share_bp": share_bp(total, quote)} for name, total in sorted(corridors.items())
        },
        "sites": dict(sorted(sites.items())),
    }


def build(book: dict) -> dict[str, dict]:
    projects: dict[str, Project] = book["projects"]
    networks = {pid: best_network(projects[pid]) for pid in sorted(projects)}
    core = {
        "projects": {
            pid: {"quote": net.quote, "links": list(net.links), "sites": list(net.sites)}
            for pid, net in networks.items()
        }
    }
    parser = {
        "accepted": sorted(projects),
        "rejected": dict(sorted(book["rejected"].items())),
        "projects": {pid: projects[pid].stats() for pid in sorted(projects)},
    }
    reports = {pid: project_report(projects[pid], net) for pid, net in networks.items()}
    corridor_totals: dict[str, int] = {}
    for entry in reports.values():
        for name, row in entry["corridors"].items():
            corridor_totals[name] = corridor_totals.get(name, 0) + row["total"]
    summary = {
        "book_total": sum(net.quote for net in networks.values()),
        "projects_quoted": len(networks),
        "projects_rejected": len(book["rejected"]),
        "depot_total": sum(entry["depot"]["total"] for entry in reports.values()),
        "corridor_totals": dict(sorted(corridor_totals.items())),
    }
    return {
        "module_core.json": core,
        "module_parser.json": parser,
        "module_report.json": {"projects": reports},
        "summary.json": summary,
    }
