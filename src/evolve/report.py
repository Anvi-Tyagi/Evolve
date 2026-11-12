"""Small helpers shared by the markdown reports."""


def md_table(rows, headers) -> str:
    """Render rows as a GitHub-flavoured markdown table (or '_None._' if empty)."""
    if not rows:
        return "_None._\n"
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out) + "\n"
