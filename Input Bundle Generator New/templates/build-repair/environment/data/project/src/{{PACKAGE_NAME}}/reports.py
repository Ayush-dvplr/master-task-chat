from __future__ import annotations

from .core import summarize

DEFAULT_LABEL = "{{CONTAINER_NOUN}}/{{PRODUCER_SYSTEM}}"


def render_report(entries: list[dict]) -> str:
    summary = summarize(entries)
    lines = [f"{{FORMAT_TAG}} manifest report: {summary['count']} entries"]
    lines.append(f"average={summary['average']:.2f}")
    for item in summary["items"]:
        lines.append(f"- {item['name']}: {item['bucket']} ({item['score']})")
    return "\n".join(lines)
