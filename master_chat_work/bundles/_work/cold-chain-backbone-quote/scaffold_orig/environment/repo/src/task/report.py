from .core import VERSION


def render_report(totals):
    return {"version": VERSION, "accounts": totals, "grand_total": sum(totals)}
