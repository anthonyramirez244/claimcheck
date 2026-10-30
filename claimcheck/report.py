"""Render a Report as Markdown (for people) or JSON (for other tools)."""
from __future__ import annotations

import json
from dataclasses import asdict

from .pipeline import Report

ICON = {
    "SUPPORTED": "OK", "WARNING": "CHECK", "MISMATCH": "FIX", "UNSUPPORTED": "FIX",
    "ATTRIBUTION": "FIX", "NEEDS_REVIEW": "ASK",
}


def to_markdown(rep: Report) -> str:
    d = rep.draft
    orgs = sorted({f.org_name for f in rep.facts})
    out = [f"# Claim check: {d.title}", ""]
    out.append(f"- Draft: `{d.path}`")
    out.append(f"- Publisher: `{d.voice}` | Featured nonprofit: `{d.featured_org}`")
    out.append(f"- Fact sheets: {', '.join(orgs)} ({len(rep.facts)} facts)")
    out.append(f"- Model step: {rep.llm_mode}" + (" (recorded replies, not a live model)" if rep.llm_mode == "mock" else ""))
    out.append("")

    if not rep.results:
        out += ["## Verdict: READY", "", "No numeric claims were found, so there was nothing to verify.",
                "A person should still read it for claims the checker can't see (names, programs, quotes).", ""]
        return "\n".join(out)

    n = len(rep.blocking)
    out.append(f"## Verdict: {'READY' if rep.ready else f'BLOCKED ({n} issue' + ('s' if n != 1 else '') + ')'}")
    out.append("")
    counts = {}
    for r in rep.results:
        counts[r.status] = counts.get(r.status, 0) + 1
    out.append("Claims found: " + ", ".join(f"{v} {k.lower().replace('_', ' ')}" for k, v in sorted(counts.items())))
    out.append("")

    out.append("| ID | Line | Claim | Status | Fact | Note |")
    out.append("|---|---|---|---|---|---|")
    for r in rep.results:
        note = " ".join(r.notes).replace("|", "/")
        fact = r.fact.id if r.fact else ("; ".join(r.candidates) if r.candidates else "none")
        out.append(f"| {r.claim.id} | {r.claim.line} | {r.claim.literal} | {ICON[r.status]} {r.status} | {fact} | {note} |")
    out.append("")

    if rep.blocking:
        out += ["## Fix before publishing", ""]
        for r in rep.blocking:
            out.append(f"**{r.claim.id} (line {r.claim.line}): {r.status}**")
            out.append(f"> {r.claim.sentence}")
            for note in r.notes:
                out.append(f"- {note}")
            if r.fact:
                out.append(f"- Fact on file: {r.fact.statement} (source: {r.fact.source})")
            out.append("")

    checks = [r for r in rep.results if r.status == "WARNING"]
    if checks:
        out += ["## Worth a quick look (not blocking)", ""]
        for r in checks:
            out.append(f"- {r.claim.id} (line {r.claim.line}) \"{r.claim.literal}\": {' '.join(r.notes)}")
        out.append("")
    return "\n".join(out)


def to_json(rep: Report) -> str:
    return json.dumps({
        "draft": rep.draft.path,
        "ready": rep.ready,
        "llm_mode": rep.llm_mode,
        "blocking_count": len(rep.blocking),
        "results": [asdict(r) for r in rep.results],
    }, indent=2)
